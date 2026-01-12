from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag
from sqlalchemy.orm import Session

from .config import SiteConfig
from .db.models import Article, ArticleImage, ArticleVideo
from .crawler.article import ArticleExtractor, _is_in_excluded_section, _prettify_slug


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ParsedArticle:
    """Kết quả bóc tách 1 bài báo từ HTML."""

    url: str
    title: str
    description: Optional[str]
    content: Optional[str]
    category_id: Optional[str]
    category_name: Optional[str]
    tags: Sequence[str]
    publish_date: Optional[datetime]
    images: Sequence[str]
    videos: Sequence[str]


@dataclass(slots=True)
class CategoryInfo:
    url: str
    slug: str
    name: Optional[str] = None


class SkipArticle(Exception):
    """Raised when a crawled article should be ignored."""


class RateLimitedHttpClient:
    """Wrapper quanh requests.Session có delay giữa các request."""

    def __init__(
        self,
        *,
        delay_seconds: float = 0.5,
        timeout: int = 20,
        max_retries: int = 2,
        retry_backoff: float = 1.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._session = requests.Session()
        self._delay = max(float(delay_seconds), 0.0)
        self._timeout = max(int(timeout), 1)
        self._max_retries = max(int(max_retries), 0)
        self._retry_backoff = max(float(retry_backoff), 0.0)
        self._next_request_ts = 0.0
        self._headers = {
            "User-Agent": (
                "latest-news-crawler/0.1 (+https://example.local)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if headers:
            self._headers.update(headers)

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        response = self._request(url, params=params, headers=headers)
        return response.text

    def get_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, object]:
        request_headers = {"Accept": "application/json, text/plain, */*"}
        if headers:
            request_headers.update(headers)
        response = self._request(url, params=params, headers=request_headers)
        return response.json()

    def _request(
        self,
        url: str,
        *,
        params: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        retry_statuses = {429, 500, 502, 503, 504}
        last_exc: Optional[Exception] = None
        request_headers = dict(self._headers)
        if headers:
            request_headers.update(headers)
        for attempt in range(self._max_retries + 1):
            self._respect_delay()
            try:
                response = self._session.get(
                    url,
                    headers=request_headers,
                    timeout=self._timeout,
                    params=params,
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    raise
                self._sleep_retry(attempt)
                continue

            if response.status_code in retry_statuses and attempt < self._max_retries:
                self._sleep_retry(attempt, response=response)
                continue

            response.raise_for_status()
            return response

        if last_exc:
            raise last_exc
        raise requests.HTTPError(f"Failed to fetch {url}")

    def _sleep_retry(self, attempt: int, response: Optional[requests.Response] = None) -> None:
        retry_after = 0.0
        if response is not None:
            retry_after_value = response.headers.get("Retry-After")
            if retry_after_value and retry_after_value.isdigit():
                retry_after = float(retry_after_value)
        backoff = self._retry_backoff * (2 ** attempt)
        time.sleep(max(backoff, retry_after))

    def _respect_delay(self) -> None:
        if self._delay <= 0:
            return
        now = time.time()
        if now < self._next_request_ts:
            time.sleep(self._next_request_ts - now)
        self._next_request_ts = time.time() + self._delay


def _normalize_internal_url(
    base_url: str,
    href: str,
    *,
    keep_query: bool = False,
) -> Optional[str]:
    """Chuẩn hoá link nội bộ: join với base_url, bỏ query/fragment, chỉ giữ đúng host."""
    href = (href or "").strip()
    if not href or href.lower().startswith(("javascript:", "mailto:", "tel:")):
        return None

    candidate = urljoin(base_url, href)
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return None

    base = urlparse(base_url)
    base_host = base.netloc.lower()
    host = parsed.netloc.lower()

    root_host = base_host[4:] if base_host.startswith("www.") else base_host
    allowed_hosts = {
        base_host,
        root_host,
        f"www.{root_host}",
    }
    if host not in allowed_hosts and not host.endswith(f".{root_host}"):
        return None

    cleaned = parsed._replace(fragment="")
    if not keep_query:
        cleaned = cleaned._replace(query="")
    return urlunparse(cleaned)


def _slug_from_path(path: str) -> str:
    path = path.strip("/") or "root"
    first_segment = path.split("/")[0]
    return first_segment or "root"


def _slug_from_category_path(path: str, pattern: str) -> str:
    prefix, _, suffix = pattern.partition("{slug}")
    if not prefix and not suffix:
        return _slug_from_path(path)

    candidate = path
    if prefix:
        normalized_prefix = prefix
        if not normalized_prefix.endswith("/"):
            normalized_prefix = normalized_prefix.rstrip("/") + "/"
        if candidate.startswith(normalized_prefix):
            candidate = candidate[len(normalized_prefix) :]

    if suffix and candidate.endswith(suffix):
        candidate = candidate[: -len(suffix)]

    candidate = candidate.strip("/")
    if not candidate:
        return _slug_from_path(path)
    return candidate.split("/")[0]


def _text_or_none(node: Optional[Tag]) -> Optional[str]:
    if not node:
        return None
    text = node.get_text(" ", strip=True)
    return text or None


def _extract_main_content(soup: BeautifulSoup) -> str:
    """
    Heuristic chung để lấy nội dung bài:
    - ưu tiên các selector thường gặp ở VNExpress/Tuổi Trẻ,
    - fallback: <article>, sau đó toàn bộ <body>.
    """
    candidates = [
        "article.fck_detail",
        "article#main-detail-body",
        "article.article",
        "div#main_detail",
        "div#content",
        "div.article-content",
        "div.b-maincontent",
    ]
    for selector in candidates:
        node = soup.select_one(selector)
        if node:
            paragraphs = [
                p.get_text(" ", strip=True)
                for p in node.find_all(["p", "div"])
                if p.get_text(strip=True)
            ]
            if paragraphs:
                return "\n".join(paragraphs)

    node = soup.find("article")
    if node:
        text = node.get_text("\n", strip=True)
        return text

    body = soup.body
    if body:
        text = body.get_text("\n", strip=True)
        return text
    return ""


def _extract_publish_date(soup: BeautifulSoup) -> Optional[datetime]:
    """Cố gắng lấy ngày publish từ các thẻ meta chuẩn (ISO 8601)."""
    meta = (
        soup.find("meta", attrs={"itemprop": "datePublished"})
        or soup.find("meta", attrs={"property": "article:published_time"})
        or soup.find("meta", attrs={"name": "pubdate"})
    )
    if not meta:
        return None
    value = (meta.get("content") or "").strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _extract_tags(soup: BeautifulSoup) -> List[str]:
    """Heuristic chung để lấy tags."""
    containers = soup.select(
        "div.tags, div.list-tag, ul.list-tag, ul.tag, section.wrap-tag, "
        "div.box-keyword, div.tag, section.tags"
    )
    tags: List[str] = []
    seen: Set[str] = set()

    for container in containers:
        for anchor in container.find_all("a"):
            text = anchor.get_text(strip=True)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            tags.append(text)

    if not tags:
        for anchor in soup.select("a[rel='tag']"):
            text = anchor.get_text(strip=True)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            tags.append(text)

    if not tags:
        for meta_name in ("news_keywords", "keywords"):
            meta_tag = soup.find("meta", attrs={"name": meta_name})
            if not meta_tag or not meta_tag.get("content"):
                continue
            for token in meta_tag["content"].split(","):
                text = token.strip()
                if not text:
                    continue
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                tags.append(text)
            if tags:
                break

    return tags


def _extract_images_and_videos(soup: BeautifulSoup, base_url: str) -> tuple[List[str], List[str]]:
    """Lấy các link ảnh/video trong nội dung chính."""
    images: List[str] = []
    videos: List[str] = []
    seen_img: Set[str] = set()
    seen_video: Set[str] = set()
    blocked_image_urls = {"https://bqn.1cdn.vn/assets/images/grey.gif"}

    for selector in ("article", "#content", "#main_detail", ".article-content", ".b-maincontent"):
        container = soup.select_one(selector)
        if not container:
            continue

        for img in container.find_all("img"):
            if _is_in_excluded_section(img):
                continue
            candidate = (
                img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy-src")
                or img.get("src")
            )
            url = _normalize_internal_url(base_url, candidate) if candidate else None
            if url and url not in seen_img and url not in blocked_image_urls:
                seen_img.add(url)
                images.append(url)

        for tag_name in ("video", "iframe", "source"):
            for node in container.find_all(tag_name):
                if _is_in_excluded_section(node):
                    continue
                candidate = node.get("src") or node.get("data-src")
                url = _normalize_internal_url(base_url, candidate) if candidate else None
                if url and url not in seen_video:
                    seen_video.add(url)
                    videos.append(url)

        if images or videos:
            break

    return images, videos


class NewsSiteCrawler:
    """Crawler tổng quát cho 1 trang báo, dùng cấu hình `SiteConfig`."""

    def __init__(
        self,
        site: SiteConfig,
        session: Optional[Session],
        *,
        client: Optional[RateLimitedHttpClient] = None,
    ) -> None:
        self.site = site
        self.session = session
        self.client = client or RateLimitedHttpClient()

        self._seen_article_urls: Set[str] = set()
        self._inserted = 0
        self._skipped = 0
        self._failed = 0

    def _normalize_url(self, href: str) -> Optional[str]:
        return _normalize_internal_url(
            self.site.base_url,
            href,
            keep_query=self.site.keep_query_params,
        )

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "inserted": self._inserted,
            "skipped": self._skipped,
            "failed": self._failed,
        }

    def crawl(self, *, max_articles: Optional[int] = None) -> None:
        LOGGER.info("=== Crawling site %s (%s) ===", self.site.key, self.site.base_url)
        categories = self._discover_categories()
        LOGGER.info("Found %s categories for %s", len(categories), self.site.key)

        for category in categories:
            LOGGER.info("Processing category %s (%s)", category.slug, category.url)
            article_urls = self._discover_category_articles(category)
            LOGGER.info(
                "  -> found %s article URLs in category %s",
                len(article_urls),
                category.slug,
            )
            for url in article_urls:
                if max_articles is not None and self._inserted >= max_articles:
                    LOGGER.info(
                        "Reached max_articles=%s for site %s, stopping.",
                        max_articles,
                        self.site.key,
                    )
                    return
                if url in self._seen_article_urls:
                    continue
                self._seen_article_urls.add(url)
                try:
                    html = self.client.get(url)
                    parsed = self._parse_article(html, url=url, category=category)
                    self._save_article(parsed)
                    self._inserted += 1
                except SkipArticle as exc:
                    self._skipped += 1
                    LOGGER.info("Skipping article %s: %s", url, exc)
                except requests.RequestException as exc:
                    self._failed += 1
                    LOGGER.warning("Failed to fetch article %s: %s", url, exc)
                except Exception as exc:
                    self._failed += 1
                    LOGGER.exception("Failed to crawl article %s: %s", url, exc)

    def collect_category_article_links(self) -> Dict[str, List[str]]:
        """Thu thập link bài viết cho từng category (không lưu DB)."""
        categories = self._discover_categories()
        results: Dict[str, List[str]] = {}
        for category in categories:
            results[category.url] = self._discover_category_articles(category)
        return results

    def _discover_categories(self) -> List[CategoryInfo]:
        if self.site.key == "baodienbienphu":
            return self._discover_baodienbienphu_categories()
        if self.site.keep_query_params:
            return self._discover_query_categories()

        home_url = urljoin(self.site.base_url, self.site.home_path or "/")
        try:
            html = self.client.get(home_url)
        except requests.RequestException as exc:
            LOGGER.exception("Failed to fetch home page %s: %s", home_url, exc)
            return []
        soup = BeautifulSoup(html, "html.parser")

        base_parsed = urlparse(self.site.base_url)
        base_host = base_parsed.netloc.lower()

        categories: Dict[str, CategoryInfo] = {}

        for anchor in soup.find_all("a", href=True):
            normalized = self._normalize_url(anchor["href"])
            if not normalized:
                continue

            parsed = urlparse(normalized)
            host = parsed.netloc.lower()
            if host != base_host and host != f"www.{base_host}":
                continue

            path = parsed.path or "/"

            if path in self.site.deny_exact_paths:
                continue

            pattern_prefix, _, _ = self.site.category_path_pattern.partition("{slug}")
            normalized_prefix = pattern_prefix.rstrip("/")
            if normalized_prefix and path.rstrip("/") == normalized_prefix:
                continue

            slug = _slug_from_category_path(path, self.site.category_path_pattern)
            category_path = self.site.category_path_pattern.format(slug=slug)

            if self.site.allow_category_prefixes:
                if not any(
                    category_path.startswith(prefix)
                    for prefix in self.site.allow_category_prefixes
                ):
                    continue

            if any(
                category_path.startswith(prefix)
                for prefix in self.site.deny_category_prefixes
            ):
                continue

            canonical = urlunparse(
                parsed._replace(path=category_path, query="", fragment="")
            )
            if canonical not in categories:
                categories[canonical] = CategoryInfo(
                    url=canonical,
                    slug=slug,
                    name=anchor.get_text(" ", strip=True) or None,
                )
                if len(categories) >= self.site.max_categories:
                    break

        return list(categories.values())

    def _discover_query_categories(self) -> List[CategoryInfo]:
        home_url = urljoin(self.site.base_url, self.site.home_path or "/")
        try:
            html = self.client.get(home_url)
        except requests.RequestException as exc:
            LOGGER.exception("Failed to fetch home page %s: %s", home_url, exc)
            return []

        soup = BeautifulSoup(html, "html.parser")
        base_host = urlparse(self.site.base_url).netloc.lower()
        categories: Dict[str, CategoryInfo] = {}

        for anchor in soup.find_all("a", href=True):
            normalized = self._normalize_url(anchor["href"])
            if not normalized:
                continue

            parsed = urlparse(normalized)
            host = parsed.netloc.lower()
            if host != base_host and host != f"www.{base_host}":
                continue

            path = parsed.path or "/"
            if path in self.site.deny_exact_paths:
                continue

            if self.site.allow_category_prefixes:
                if not any(path.startswith(prefix) for prefix in self.site.allow_category_prefixes):
                    continue

            if any(path.startswith(prefix) for prefix in self.site.deny_category_prefixes):
                continue

            slug = _slug_from_path(path)
            if parsed.query:
                params = parse_qs(parsed.query)
                urile = params.get("urile") or []
                if urile:
                    candidate = urile[0].split("/")[-1]
                    if candidate:
                        slug = candidate

            if normalized not in categories:
                categories[normalized] = CategoryInfo(
                    url=normalized,
                    slug=slug,
                    name=anchor.get_text(" ", strip=True) or None,
                )
                if len(categories) >= self.site.max_categories:
                    break

        return list(categories.values())

    def _discover_category_articles(self, category: CategoryInfo) -> List[str]:
        if self.site.key == "baodienbienphu":
            return self._discover_baodienbienphu_articles(category)

        try:
            html = self.client.get(category.url)
        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch category page %s: %s", category.url, exc)
            return []
        soup = BeautifulSoup(html, "html.parser")

        candidates: List[str] = []
        seen: Set[str] = set()

        def _collect(href: str) -> None:
            normalized = self._normalize_url(href)
            if not normalized:
                return
            if normalized in seen:
                return
            seen.add(normalized)
            candidates.append(normalized)

        if self.site.article_link_selector:
            for node in soup.select(self.site.article_link_selector):
                href = node.get("href")
                if href:
                    _collect(href)

        for node in soup.find_all("article"):
            anchor = node.find("a", href=True)
            if anchor:
                _collect(anchor["href"])

        for selector in ("h3 a[href]", "h2 a[href]"):
            for node in soup.select(selector):
                href = node.get("href")
                if href:
                    _collect(href)

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            normalized = self._normalize_url(href)
            if not normalized:
                continue
            parsed = urlparse(normalized)
            if len(parsed.path or "") < 10:
                continue
            _collect(normalized)

        article_urls = [
            url
            for url in candidates
            if not self._is_denied_article_url(url)
            and self._has_allowed_article_suffix(url)
            and self._has_allowed_article_path(url)
            and self._is_allowed_article_host(url)
        ]

        if self.site.max_articles_per_category and len(article_urls) > self.site.max_articles_per_category:
            article_urls = article_urls[: self.site.max_articles_per_category]

        return article_urls

    def _discover_baodienbienphu_categories(self) -> List[CategoryInfo]:
        api_url = "https://api-dienbien.baodienbienphu.vn/api/web/menu-get-list"
        try:
            payload = self.client.get_json(api_url)
        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch baodienbienphu categories: %s", exc)
            return []

        if not isinstance(payload, dict) or payload.get("status") != 1:
            LOGGER.warning("Unexpected baodienbienphu category payload: %s", payload)
            return []

        data = payload.get("data") or {}
        items = data.get("list") if isinstance(data, dict) else []
        if not isinstance(items, list):
            return []

        categories: Dict[str, CategoryInfo] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("menu_slug") or "").strip()
            if not slug or slug in categories:
                continue
            url = urljoin(self.site.base_url, f"/tin-tuc/{slug}")
            categories[slug] = CategoryInfo(url=url, slug=slug)

        results = list(categories.values())
        if self.site.max_categories and len(results) > self.site.max_categories:
            results = results[: self.site.max_categories]
        return results

    def _discover_baodienbienphu_articles(self, category: CategoryInfo) -> List[str]:
        api_url = (
            "https://api-dienbien.baodienbienphu.vn/api/"
            "web/article-get-news-by-category-slug"
        )
        max_articles = self.site.max_articles_per_category or 0
        limit = max_articles or 12

        try:
            payload = self.client.get_json(
                api_url,
                params={
                    "category_slug": category.slug,
                    "limit": limit,
                },
            )
        except requests.RequestException as exc:
            LOGGER.warning(
                "Failed to fetch baodienbienphu articles for %s: %s",
                category.slug,
                exc,
            )
            return []

        if not isinstance(payload, dict) or payload.get("status") != 1:
            LOGGER.warning(
                "Unexpected baodienbienphu article payload for %s: %s",
                category.slug,
                payload,
            )
            return []

        data = payload.get("data") or {}
        items = data.get("list") if isinstance(data, dict) else []
        if not isinstance(items, list) or not items:
            return []

        results: List[str] = []
        seen: Set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            article_slug = str(item.get("article_slug") or "").strip()
            category_slug = str(item.get("category_slug") or category.slug).strip()
            article_type_slug = str(item.get("article_type_slug") or "tin-bai").strip()
            if not article_slug or not category_slug:
                continue
            url = urljoin(
                self.site.base_url,
                f"/{article_type_slug}/{category_slug}/{article_slug}",
            )
            if url in seen:
                continue
            seen.add(url)
            results.append(url)
            if max_articles and len(results) >= max_articles:
                break

        return results

    def _is_denied_article_url(self, url: str) -> bool:
        prefixes = getattr(self.site, "deny_article_prefixes", ())
        if not prefixes:
            return False
        parsed = urlparse(url)
        path = parsed.path or "/"
        for prefix in prefixes:
            if not prefix:
                continue
            normalized_prefix = prefix if prefix.startswith("/") else f"/{prefix}"
            if path.startswith(normalized_prefix):
                return True
        return False

    def _is_allowed_article_host(self, url: str) -> bool:
        suffixes = getattr(self.site, "allowed_article_host_suffixes", ())
        if not suffixes:
            return True
        normalized_suffixes = [
            suffix.strip().lower()
            for suffix in suffixes
            if suffix and suffix.strip()
        ]
        if not normalized_suffixes:
            return True
        host = urlparse(url).netloc.lower()
        return any(host.endswith(suffix) for suffix in normalized_suffixes)

    def _has_allowed_article_suffix(self, url: str) -> bool:
        suffixes = getattr(self.site, "allowed_article_url_suffixes", ())
        if not suffixes:
            return True
        normalized_suffixes = [
            suffix.strip().lower()
            for suffix in suffixes
            if suffix and suffix.strip()
        ]
        if not normalized_suffixes:
            return True
        return any(url.lower().endswith(suffix) for suffix in normalized_suffixes)

    def _has_allowed_article_path(self, url: str) -> bool:
        patterns = getattr(self.site, "allowed_article_path_regexes", ())
        if not patterns:
            return True
        path = urlparse(url).path or "/"
        for pattern in patterns:
            if not pattern:
                continue
            try:
                if re.search(pattern, path):
                    return True
            except re.error:
                LOGGER.warning("Invalid allowed_article_path_regex: %s", pattern)
        return False

    def _parse_article(self, html: str, *, url: str, category: CategoryInfo) -> ParsedArticle:
        soup = BeautifulSoup(html, "html.parser")

        skip_locale, locale_value = self._should_skip_locale(soup)
        if skip_locale:
            raise SkipArticle(
                f"Unsupported locale '{locale_value}' for article {url}",
            )

        extractor = ArticleExtractor(url)
        data = extractor.extract(html)

        title = data.title or url
        placeholder_title = f"{self.site.base_url.rstrip('/')}/404"
        if title and title.strip().lower() == placeholder_title.lower():
            raise SkipArticle(f"Placeholder 404 page for article {url}")

        description = data.description or data.summary
        if not description:
            desc_node: Optional[Tag] = None
            if getattr(self.site, "description_selectors", None):
                for selector in self.site.description_selectors:
                    node = soup.select_one(selector)
                    if node:
                        desc_node = node
                        break
            if desc_node is None:
                desc_node = (
                    soup.select_one("p.description")
                    or soup.select_one("p.sapo")
                    or soup.select_one("h2.sapo")
                    or soup.select_one("h2.detail-sapo")
                )
            description = _text_or_none(desc_node)

        content = data.content or _extract_main_content(soup) or None
        if not content or len(content.strip()) < 50:
            raise SkipArticle(f"Missing article content for {url}")

        # Nếu bản thân trang bài không có category_id và category_name
        # (do ArticleExtractor không trích được từ HTML) thì bỏ qua.
        # Những URL này thường là trang thể loại/bộ sưu tập, không phải bài báo cụ thể.
        if not (data.category_id or data.category_name):
            # Riêng với một số site, ta fallback dùng slug category từ trang danh sách.
            # - vov: trang bài thường không có meta category rõ ràng.
            # - vnexpress: ArticleExtractor chưa trích được category, nhưng slug từ trang
            #   danh sách đã phản ánh đúng chuyên mục (thoi-su, kinh-doanh, ...).
            if self.site.key in (
                "vov",
                "vnexpress",
                "baocaobang",
                "baodienbienphu",
                "modgov",
            ):
                data.category_id = category.slug
                data.category_name = category.name or _prettify_slug(category.slug)
            else:
                raise SkipArticle(
                    f"Missing category id and name for article {url}",
                )

        category_id = data.category_id or category.slug
        category_name = data.category_name
        if not category_name:
            breadcrumb = soup.select_one("ul.breadcrumb, nav.breadcrumb")
            if breadcrumb:
                tokens: List[str] = []
                for li in breadcrumb.find_all("li"):
                    text = li.get_text(strip=True)
                    if text:
                        tokens.append(text)
                if tokens:
                    category_name = tokens[-1]

        if self.site.key == "vietbao":
            normalized_category_id = (category_id or "").strip().lower()
            has_category_name = bool((category_name or "").strip())
            if not has_category_name or normalized_category_id in ("", "root"):
                raise SkipArticle(f"Missing category for vietbao article {url}")

        publish_date = data.publish_date or _extract_publish_date(soup)

        if data.tags:
            tags_list: List[str] = [
                part.strip() for part in data.tags.split(",") if part.strip()
            ]
        else:
            tags_list = _extract_tags(soup)

        images = list(data.images)
        videos = list(data.videos)
        if not images and not videos:
            images, videos = _extract_images_and_videos(soup, base_url=self.site.base_url)

        return ParsedArticle(
            url=url,
            title=title,
            description=description,
            content=content,
            category_id=category_id,
            category_name=category_name,
            tags=tags_list,
            publish_date=publish_date,
            images=images,
            videos=videos,
        )

    def _should_skip_locale(self, soup: BeautifulSoup) -> tuple[bool, Optional[str]]:
        allowed = getattr(self.site, "allowed_locales", ())
        if not allowed:
            return False, None

        normalized_allowed = tuple(
            token.strip().lower().replace("_", "-")
            for token in allowed
            if token and token.strip()
        )
        if not normalized_allowed:
            return False, None

        locales = []
        html_tag = soup.find("html")
        if html_tag:
            for attr in ("lang", "xml:lang"):
                value = html_tag.get(attr)
                if value:
                    locales.append(value)
                    break

        for attrs in (
            {"property": "og:locale"},
            {"property": "article:language"},
            {"name": "language"},
            {"name": "dc.language"},
            {"http-equiv": "content-language"},
        ):
            meta = soup.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                locales.append(meta["content"])

        normalized_locales = [
            token.strip().lower().replace("_", "-")
            for token in locales
            if token and token.strip()
        ]
        if not normalized_locales:
            return False, None

        for locale in normalized_locales:
            for allowed_locale in normalized_allowed:
                if locale.startswith(allowed_locale):
                    return False, None

        return True, normalized_locales[0]

    def _save_article(self, parsed: ParsedArticle) -> None:
        if self.session is None:
            raise RuntimeError("Session is required to save articles.")
        existing = (
            self.session.query(Article.id)
            .filter(Article.url == parsed.url)
            .first()
        )
        if existing:
            self._skipped += 1
            return

        tags_str = self._join_tags(parsed.tags)
        title = self._trim_to_column_length(parsed.title, Article.title)
        category_id = self._trim_to_column_length(parsed.category_id, Article.category_id)
        category_name = self._trim_to_column_length(
            parsed.category_name, Article.category_name
        )
        tags_str = self._trim_to_column_length(tags_str, Article.tags)
        url = self._trim_to_column_length(parsed.url, Article.url)
        article_name = self._trim_to_column_length(
            self.site.resolved_article_name(), Article.article_name
        )

        article = Article(
            title=title,
            description=parsed.description,
            content=parsed.content,
            category_id=category_id,
            category_name=category_name,
            comments=None,
            tags=tags_str,
            url=url,
            publish_date=parsed.publish_date,
            article_name=article_name,
        )
        self.session.add(article)
        self.session.flush()

        for idx, img_url in enumerate(parsed.images, start=1):
            image_path = self._trim_to_column_length(
                img_url,
                ArticleImage.image_path,
            )
            if not image_path:
                LOGGER.debug(
                    "Skipping empty image URL for article %s (seq=%s)",
                    article.id,
                    idx,
                )
                continue
            article.images.append(
                ArticleImage(
                    image_path=image_path,
                    sequence_number=idx,
                )
            )

        max_videos_per_article = 5

        for idx, video_url in enumerate(parsed.videos[:max_videos_per_article], start=1):
            video_path = self._trim_to_column_length(
                video_url,
                ArticleVideo.video_path,
            )
            if not video_path:
                LOGGER.debug(
                    "Skipping empty video URL for article %s (seq=%s)",
                    article.id,
                    idx,
                )
                continue
            article.videos.append(
                ArticleVideo(
                    video_path=video_path,
                    sequence_number=idx,
                )
            )

    @staticmethod
    def _join_tags(tags: Sequence[str]) -> Optional[str]:
        cleaned: List[str] = []
        seen: Set[str] = set()
        for tag in tags:
            value = (tag or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        if not cleaned:
            return None
        concatenated = ", ".join(cleaned)
        return concatenated[:500]

    @staticmethod
    def _trim_to_column_length(value: Optional[str], column_attr) -> Optional[str]:
        if value is None:
            return None
        column = column_attr.property.columns[0]
        max_length = getattr(column.type, "length", None)
        if not max_length or len(value) <= max_length:
            return value
        LOGGER.debug(
            "Truncating value for %s from %d to %d characters",
            column.key,
            len(value),
            max_length,
        )
        return value[:max_length]
