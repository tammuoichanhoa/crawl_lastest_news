from __future__ import annotations

import logging
import re
import ssl
import time
import unicodedata
from html import unescape
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import parse_qs, unquote as url_unquote, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from sqlalchemy.orm import Session

from .config import SiteConfig
from .db.models import Article, ArticleImage, ArticleVideo
from .crawler.article import (
    ArticleExtractor,
    _is_in_excluded_section,
    _prettify_slug,
    _render_moha_article_html,
    _render_mof_article_html,
)


LOGGER = logging.getLogger(__name__)

_MOHA_API_BASE = "https://api-portal.moha.gov.vn/api/Public"
_MOF_API_BASE = "https://www.mof.gov.vn/api"
_MOF_ROOT_SLUG = "bo-tai-chinh"
_MOHA_MENU_DETAIL_ID = "2794"
_MOHA_ID_RE = re.compile(r"---id(?P<id>\d+)", re.IGNORECASE)
_MOHA_FALLBACK_CATEGORIES = (
    ("12", "/chuyen-muc/tin-hoat-dong-cua-bo---id12", "Tin noi vu"),
    ("13", "/chuyen-muc/tin-tong-hop---id13", "Tin tong hop"),
    ("14", "/chuyen-muc/diem-tin-dia-phuong-nganh-noi-vu---id14", "Tin dia phuong - Co so"),
)


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


class _SiteSSLAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext) -> None:
        self.ssl_context = ssl_context
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)


class RateLimitedHttpClient:
    """Wrapper quanh requests.Session có delay giữa các request."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        delay_seconds: float = 0.5,
        timeout: int = 20,
        max_retries: int = 2,
        retry_backoff: float = 1.0,
        blocked_markers: Optional[Sequence[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        allow_legacy_ssl: bool = False,
        allow_weak_dh_ssl: bool = False,
    ) -> None:
        self._session = requests.Session()
        self._delay = max(float(delay_seconds), 0.0)
        self._timeout = max(int(timeout), 1)
        self._max_retries = max(int(max_retries), 0)
        self._retry_backoff = max(float(retry_backoff), 0.0)
        self._next_request_ts = 0.0
        self._blocked_markers = [
            marker.lower() for marker in (blocked_markers or []) if marker
        ]
        self._headers = {
            "User-Agent": (
                "latest-news-crawler/0.1 (+https://example.local)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if headers:
            self._headers.update(headers)
        self._configure_ssl(
            base_url=base_url,
            allow_legacy_ssl=allow_legacy_ssl,
            allow_weak_dh_ssl=allow_weak_dh_ssl,
        )

    def _configure_ssl(
        self,
        *,
        base_url: str | None,
        allow_legacy_ssl: bool,
        allow_weak_dh_ssl: bool,
    ) -> None:
        if not base_url:
            return
        if not (allow_legacy_ssl or allow_weak_dh_ssl):
            return

        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            return

        ssl_context = ssl.create_default_context()
        if allow_legacy_ssl:
            option = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", None)
            if option:
                ssl_context.options |= option

        if allow_weak_dh_ssl:
            for cipher_string in ("DEFAULT@SECLEVEL=1", "DEFAULT:@SECLEVEL=1"):
                try:
                    ssl_context.set_ciphers(cipher_string)
                    break
                except ssl.SSLError:
                    continue

        root_host = parsed.netloc.lower()
        if root_host.startswith("www."):
            root_host = root_host[4:]
        prefixes = (
            f"https://{root_host}/",
            f"https://www.{root_host}/",
        )
        adapter = _SiteSSLAdapter(ssl_context)
        for prefix in prefixes:
            self._session.mount(prefix, adapter)

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

    def post_json(
        self,
        url: str,
        *,
        json_data: Optional[Dict[str, object]] = None,
        params: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, object]:
        request_headers = {"Accept": "application/json, text/plain, */*"}
        if headers:
            request_headers.update(headers)
        response = self._request(
            url,
            params=params,
            headers=request_headers,
            method="post",
            json_data=json_data,
        )
        return response.json()

    def _request(
        self,
        url: str,
        *,
        params: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        method: str = "get",
        json_data: Optional[Dict[str, object]] = None,
    ) -> requests.Response:
        retry_statuses = {429, 500, 502, 503, 504}
        last_exc: Optional[Exception] = None
        request_headers = dict(self._headers)
        if headers:
            request_headers.update(headers)
        for attempt in range(self._max_retries + 1):
            self._respect_delay()
            try:
                method_normalized = method.lower()
                if method_normalized == "post":
                    response = self._session.post(
                        url,
                        headers=request_headers,
                        timeout=self._timeout,
                        params=params,
                        json=json_data,
                    )
                else:
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

            if self._blocked_markers:
                content = response.text.lower()
                if any(marker in content for marker in self._blocked_markers):
                    if attempt >= self._max_retries:
                        raise requests.HTTPError(
                            f"Blocked content marker detected for {url}"
                        )
                    self._sleep_retry(attempt, response=response)
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
    base_host = (base.hostname or "").lower()
    host = (parsed.hostname or "").lower()
    if not base_host or not host:
        return None

    root_host = base_host[4:] if base_host.startswith("www.") else base_host
    allowed_hosts = {
        base_host,
        root_host,
        f"www.{root_host}",
    }
    if host not in allowed_hosts and not host.endswith(f".{root_host}"):
        return None

    cleaned = parsed._replace(fragment="")
    if cleaned.port is not None:
        is_default_https = cleaned.scheme == "https" and cleaned.port == 443
        is_default_http = cleaned.scheme == "http" and cleaned.port == 80
        if is_default_https or is_default_http:
            cleaned = cleaned._replace(netloc=cleaned.hostname or cleaned.netloc)
    if not keep_query:
        cleaned = cleaned._replace(query="")
    return urlunparse(cleaned)


def _slug_from_path(path: str) -> str:
    path = url_unquote((path or "").strip()).strip("/") or "root"
    first_segment = path.split("/")[0]
    return first_segment or "root"


def _slug_from_category_path(path: str, pattern: str) -> str:
    path = url_unquote((path or "").strip())
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


def _moha_html_has_content(html: str) -> bool:
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    for selector in (
        "div.mh-detail-body",
        "div.mh-detail-content",
        "div.moha-article__content",
        "article.moha-article",
    ):
        node = soup.select_one(selector)
        if not node:
            continue
        text = node.get_text(" ", strip=True)
        if text and len(text) >= 50:
            return True
    return False


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
        if client:
            self.client = client
        else:
            self.client = RateLimitedHttpClient(
                base_url=site.base_url,
                delay_seconds=site.delay_seconds or 0.5,
                timeout=site.timeout_seconds or 20,
                max_retries=getattr(site, "max_retries", 2),
                retry_backoff=getattr(site, "retry_backoff", 1.0),
                blocked_markers=site.blocked_content_markers or None,
                headers=site.request_headers or None,
                allow_legacy_ssl=site.allow_legacy_ssl,
                allow_weak_dh_ssl=site.allow_weak_dh_ssl,
            )

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

    def _is_denied_category_path(self, path: str) -> bool:
        if not self.site.deny_category_path_regexes:
            return False
        return any(re.search(pattern, path) for pattern in self.site.deny_category_path_regexes)

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
                    html = self._fetch_article_html(url)
                    html = self._maybe_fetch_moha_article_html(url, html)
                    html = self._maybe_fetch_mof_article_html(url, html)
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

    def _fetch_article_html(self, url: str) -> str:
        try:
            return self.client.get(url)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if self.site.key == "moh" and (status_code is None or status_code >= 500):
                for fallback_url in self._moh_article_url_fallbacks(url):
                    try:
                        html = self.client.get(fallback_url)
                    except requests.RequestException:
                        continue
                    LOGGER.info(
                        "Fetched MOH article via fallback URL %s (original %s)",
                        fallback_url,
                        url,
                    )
                    return html
            raise
        except requests.RequestException:
            if self.site.key != "moh":
                raise
            for fallback_url in self._moh_article_url_fallbacks(url):
                try:
                    html = self.client.get(fallback_url)
                except requests.RequestException:
                    continue
                LOGGER.info(
                    "Fetched MOH article via fallback URL %s (original %s)",
                    fallback_url,
                    url,
                )
                return html
            raise

    def _moh_article_url_fallbacks(self, url: str) -> List[str]:
        parsed = urlparse(url)
        path = parsed.path or "/"
        variants: List[str] = []

        def add_path(candidate_path: str) -> None:
            if not candidate_path.startswith("/"):
                candidate_path = f"/{candidate_path}"
            candidate_url = urlunparse(parsed._replace(path=candidate_path))
            if candidate_url != url and candidate_url not in variants:
                variants.append(candidate_url)

        def strip_locale_segment(candidate_path: str) -> str | None:
            segments = [seg for seg in candidate_path.split("/") if seg]
            if not segments:
                return None
            locales = {"vi_vn", "vi-vn", "vi"}
            first = segments[0].lower()
            if first in locales:
                return "/" + "/".join(segments[1:]) if len(segments) > 1 else "/"
            if (
                len(segments) >= 3
                and segments[0] == "web"
                and segments[1] == "guest"
                and segments[2].lower() in locales
            ):
                remainder = segments[:2] + segments[3:]
                return "/" + "/".join(remainder) if remainder else "/"
            return None

        stripped = strip_locale_segment(path)
        if stripped is not None:
            add_path(stripped)

        if not path.startswith("/web/guest/") and path != "/web/guest":
            guest_path = "/web/guest" + (path if path.startswith("/") else f"/{path}")
            add_path(guest_path)
            stripped_guest = strip_locale_segment(guest_path)
            if stripped_guest is not None:
                add_path(stripped_guest)

        return variants

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
        if self.site.key == "moha":
            return self._discover_moha_categories()
        if self.site.key == "mof":
            return self._discover_mof_categories()
        if self.site.keep_query_params:
            return self._discover_query_categories()

        home_url = urljoin(self.site.base_url, self.site.home_path or "/")
        try:
            html = self.client.get(home_url)
        except requests.RequestException as exc:
            if (self.site.home_path or "/") not in ("", "/"):
                LOGGER.warning(
                    "Failed to fetch home page %s: %s. Retrying with root path.",
                    home_url,
                    exc,
                )
                fallback_url = urljoin(self.site.base_url, "/")
                try:
                    html = self.client.get(fallback_url)
                except requests.RequestException as fallback_exc:
                    LOGGER.exception(
                        "Failed to fetch fallback home page %s: %s",
                        fallback_url,
                        fallback_exc,
                    )
                    return []
            else:
                LOGGER.exception("Failed to fetch home page %s: %s", home_url, exc)
                return []
        soup = BeautifulSoup(html, "html.parser")

        base_parsed = urlparse(self.site.base_url)
        base_host = (base_parsed.hostname or base_parsed.netloc).lower()

        categories: Dict[str, CategoryInfo] = {}

        for anchor in soup.find_all("a", href=True):
            normalized = self._normalize_url(anchor["href"])
            if not normalized:
                continue

            parsed = urlparse(normalized)
            host = (parsed.hostname or parsed.netloc).lower()
            if not self._is_allowed_internal_host(host, base_host):
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

            path_for_filter = category_path if self.site.canonicalize_category_paths else path

            if self.site.allow_category_prefixes:
                if not any(
                    path_for_filter.startswith(prefix)
                    for prefix in self.site.allow_category_prefixes
                ):
                    continue

            if any(
                path_for_filter.startswith(prefix)
                for prefix in self.site.deny_category_prefixes
            ):
                continue
            if self._is_denied_category_path(path_for_filter):
                continue

            canonical_path = category_path if self.site.canonicalize_category_paths else path
            canonical = urlunparse(
                parsed._replace(path=canonical_path, query="", fragment="")
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
            if (self.site.home_path or "/") not in ("", "/"):
                LOGGER.warning(
                    "Failed to fetch home page %s: %s. Retrying with root path.",
                    home_url,
                    exc,
                )
                fallback_url = urljoin(self.site.base_url, "/")
                try:
                    html = self.client.get(fallback_url)
                except requests.RequestException as fallback_exc:
                    LOGGER.exception(
                        "Failed to fetch fallback home page %s: %s",
                        fallback_url,
                        fallback_exc,
                    )
                    return []
            else:
                LOGGER.exception("Failed to fetch home page %s: %s", home_url, exc)
                return []

        soup = BeautifulSoup(html, "html.parser")
        base_parsed = urlparse(self.site.base_url)
        base_host = (base_parsed.hostname or base_parsed.netloc).lower()
        categories: Dict[str, CategoryInfo] = {}

        for anchor in soup.find_all("a", href=True):
            normalized = self._normalize_url(anchor["href"])
            if not normalized:
                continue

            parsed = urlparse(normalized)
            host = (parsed.hostname or parsed.netloc).lower()
            if not self._is_allowed_internal_host(host, base_host):
                continue

            path = parsed.path or "/"
            if path in self.site.deny_exact_paths:
                continue

            if self.site.key == "moj" and "ItemID=" in parsed.query:
                # Skip article detail links when collecting category pages for MOJ.
                continue

            pattern_prefix, _, _ = self.site.category_path_pattern.partition("{slug}")
            normalized_prefix = pattern_prefix.rstrip("/")
            if normalized_prefix and path.rstrip("/") == normalized_prefix:
                continue

            slug = _slug_from_category_path(path, self.site.category_path_pattern)
            if parsed.query:
                params = parse_qs(parsed.query)
                urile = params.get("urile") or []
                if urile:
                    candidate = urile[0].split("/")[-1]
                    if candidate:
                        slug = candidate

            category_path = self.site.category_path_pattern.format(slug=slug)
            path_for_filter = category_path if self.site.canonicalize_category_paths else path

            if self.site.allow_category_prefixes:
                if not any(
                    path_for_filter.startswith(prefix)
                    for prefix in self.site.allow_category_prefixes
                ):
                    continue

            if any(
                path_for_filter.startswith(prefix)
                for prefix in self.site.deny_category_prefixes
            ):
                continue
            if self._is_denied_category_path(path_for_filter):
                continue

            canonical_path = category_path if self.site.canonicalize_category_paths else path
            canonical = urlunparse(parsed._replace(path=canonical_path, fragment=""))

            if canonical not in categories:
                categories[canonical] = CategoryInfo(
                    url=canonical,
                    slug=slug,
                    name=anchor.get_text(" ", strip=True) or None,
                )
                if len(categories) >= self.site.max_categories:
                    break

        return list(categories.values())

    def _discover_category_articles(self, category: CategoryInfo) -> List[str]:
        if self.site.key == "baodienbienphu":
            return self._discover_baodienbienphu_articles(category)
        if self.site.key == "moha":
            return self._discover_moha_articles(category)
        if self.site.key == "mof":
            return self._discover_mof_articles(category)

        def _discover_from_html(html: str) -> List[str]:
            soup = BeautifulSoup(html, "html.parser")

            candidates: List[str] = []
            seen: Set[str] = set()

            def _collect(raw_href: str) -> None:
                href = unescape((raw_href or "").strip())
                if not href:
                    return
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

            if self.site.key == "moh":
                for node in soup.select("[data-href], [data-url], [data-link]"):
                    for attr in ("data-href", "data-url", "data-link"):
                        value = node.get(attr)
                        if value:
                            _collect(value)

                for node in soup.find_all(onclick=True):
                    onclick = node.get("onclick") or ""
                    for match in re.findall(r"['\\\"]([^'\\\"]+)['\\\"]", onclick):
                        if "/-/" in match or "asset_publisher" in match:
                            _collect(match)

                normalized_html = html.replace("\\/", "/")
                for match in re.findall(
                    r"(https?://[^\\s\"'<>]+/-/asset_publisher/[^\\s\"'<>]+/content/[^\\s\"'<>]+)",
                    normalized_html,
                    flags=re.IGNORECASE,
                ):
                    _collect(match)
                for match in re.findall(
                    r"(/[^\\s\"'<>]+/-/asset_publisher/[^\\s\"'<>]+/content/[^\\s\"'<>]+)",
                    normalized_html,
                    flags=re.IGNORECASE,
                ):
                    _collect(match)

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

        try:
            html = self.client.get(category.url)
        except requests.RequestException as exc:
            fallback_suffixes = getattr(self.site, "category_fetch_fallback_strip_suffixes", ())
            fallback_suffixes = tuple(
                suffix.strip().lower()
                for suffix in (fallback_suffixes or ())
                if suffix and suffix.strip()
            )
            if (
                isinstance(exc, requests.HTTPError)
                and getattr(exc, "response", None) is not None
                and exc.response is not None
                and exc.response.status_code == 404
                and fallback_suffixes
            ):
                html = ""
                fallback_url = ""
                parsed = urlparse(category.url)
                path = parsed.path or "/"
                lowered_path = path.lower()
                for suffix in fallback_suffixes:
                    if lowered_path.endswith(suffix):
                        fallback_path = path[: -len(suffix)]
                        if not fallback_path:
                            break
                        fallback_url = urlunparse(
                            parsed._replace(path=fallback_path, query="", fragment="")
                        )
                        if fallback_url == category.url:
                            break
                        try:
                            html = self.client.get(fallback_url)
                            break
                        except requests.RequestException:
                            html = ""
                if html:
                    category = CategoryInfo(url=fallback_url, slug=category.slug, name=category.name)
                else:
                    LOGGER.warning("Failed to fetch category page %s: %s", category.url, exc)
                    return []
            else:
                LOGGER.warning("Failed to fetch category page %s: %s", category.url, exc)
                return []

        article_urls = _discover_from_html(html)

        if not article_urls and self.site.key == "moh":
            parsed = urlparse(category.url)
            path = parsed.path or "/"
            prefix = "/web/guest/"
            if path.startswith(prefix):
                fallback_path = "/" + path[len(prefix) :]
                fallback_url = urlunparse(parsed._replace(path=fallback_path, query="", fragment=""))
                if fallback_url != category.url:
                    try:
                        fallback_html = self.client.get(fallback_url)
                    except requests.RequestException:
                        return []
                    article_urls = _discover_from_html(fallback_html)

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

    def _discover_moha_categories(self) -> List[CategoryInfo]:
        api_url = f"{_MOHA_API_BASE}/MenuDetail"
        try:
            payload = self.client.get_json(api_url, params={"ID": _MOHA_MENU_DETAIL_ID})
        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch moha categories: %s", exc)
            return []

        if not isinstance(payload, dict):
            LOGGER.warning("Unexpected moha category payload: %s", payload)
            return []

        items = payload.get("childs")
        if not isinstance(items, list):
            data = payload.get("data")
            if isinstance(data, dict):
                items = data.get("childs")
            if not isinstance(items, list):
                items = payload.get("Childs") or payload.get("children")
        if not isinstance(items, list):
            items = []

        categories: List[CategoryInfo] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_url = str(item.get("URL") or "").strip()
            if not raw_url:
                continue
            category_id = self._extract_moha_id(raw_url)
            if not category_id:
                continue
            url = urljoin(self.site.base_url, raw_url)
            name = str(item.get("TenMenu") or "").strip() or None
            categories.append(CategoryInfo(url=url, slug=category_id, name=name))
            if self.site.max_categories and len(categories) >= self.site.max_categories:
                break

        if categories:
            return categories

        LOGGER.warning("No moha categories from API payload, using fallback IDs.")
        for category_id, path, name in _MOHA_FALLBACK_CATEGORIES:
            url = urljoin(self.site.base_url, path)
            categories.append(CategoryInfo(url=url, slug=category_id, name=name))
            if self.site.max_categories and len(categories) >= self.site.max_categories:
                break

        return categories

    def _discover_moha_articles(self, category: CategoryInfo) -> List[str]:
        api_url = f"{_MOHA_API_BASE}/PostsByCategory"
        max_articles = self.site.max_articles_per_category or 0
        limit = max_articles or 20

        try:
            payload = self.client.get_json(
                api_url,
                params={
                    "ID": category.slug,
                    "skip": 0,
                    "take": limit,
                    "requireTotalCount": "true",
                },
            )
        except requests.RequestException as exc:
            LOGGER.warning(
                "Failed to fetch moha articles for %s: %s",
                category.slug,
                exc,
            )
            return []

        if not isinstance(payload, dict):
            LOGGER.warning("Unexpected moha article payload for %s: %s", category.slug, payload)
            return []

        items = payload.get("data") or []
        if not isinstance(items, list) or not items:
            return []

        results: List[str] = []
        seen: Set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            article_id = item.get("ID")
            if not article_id:
                continue
            title = str(item.get("TieuDe") or "").strip()
            slug = self._slugify_moha_title(title) or "bai-viet"
            url = urljoin(self.site.base_url, f"/tin-tuc/{slug}---id{article_id}")
            if url in seen:
                continue
            seen.add(url)
            results.append(url)
            if max_articles and len(results) >= max_articles:
                break

        return results

    def _discover_mof_categories(self) -> List[CategoryInfo]:
        api_url = f"{_MOF_API_BASE}/articlecategory/getbyslug"
        name = None
        try:
            payload = self.client.get_json(api_url, params={"slug": _MOF_ROOT_SLUG})
        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch mof root category: %s", exc)
            payload = None

        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                name = str(data.get("name") or "").strip() or None

        url = urljoin(self.site.base_url, f"/{_MOF_ROOT_SLUG}")
        return [CategoryInfo(url=url, slug=_MOF_ROOT_SLUG, name=name)]

    def _discover_mof_articles(self, category: CategoryInfo) -> List[str]:
        api_url = f"{_MOF_API_BASE}/article/reads"
        max_articles = self.site.max_articles_per_category or 0
        limit = max_articles or 20
        payload: Dict[str, object]
        if category.slug and category.slug != _MOF_ROOT_SLUG:
            payload = {"categoryId": category.slug}
        else:
            payload = {"rootSlug": _MOF_ROOT_SLUG}

        try:
            response = self.client.post_json(
                api_url,
                params={"offset": 0, "limit": limit},
                json_data=payload,
            )
        except requests.RequestException as exc:
            LOGGER.warning(
                "Failed to fetch mof articles for %s: %s", category.slug, exc
            )
            return []

        if not isinstance(response, dict):
            LOGGER.warning("Unexpected mof article payload for %s: %s", category.slug, response)
            return []

        items = response.get("data") or []
        if not isinstance(items, list) or not items:
            return []

        results: List[str] = []
        seen: Set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            article_slug = str(item.get("slug") or "").strip()
            if not article_slug:
                continue
            root_slug = str(item.get("rootCategorySlug") or _MOF_ROOT_SLUG).strip()
            category_slug = str(item.get("categorySlug") or "tin-tuc").strip()
            url = urljoin(
                self.site.base_url,
                f"/{root_slug}/{category_slug}/{article_slug}",
            )
            if url in seen:
                continue
            seen.add(url)
            results.append(url)
            if max_articles and len(results) >= max_articles:
                break

        return results

    def _maybe_fetch_moha_article_html(self, url: str, html: str) -> str:
        if self.site.key != "moha":
            return html
        if not self._should_use_moha_api(url, html):
            return html
        article_id = self._extract_moha_id(url)
        if not article_id:
            return html
        try:
            payload = self.client.get_json(
                f"{_MOHA_API_BASE}/PostDetail",
                params={"ID": article_id},
            )
        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch moha article %s: %s", url, exc)
            return html
        api_html = _render_moha_article_html(payload)
        if api_html and _moha_html_has_content(api_html):
            return api_html
        return html

    def _maybe_fetch_mof_article_html(self, url: str, html: str) -> str:
        if self.site.key != "mof":
            return html
        if not self._should_use_mof_api(url, html):
            return html
        slug = self._extract_mof_slug(url)
        if not slug:
            return html
        try:
            payload = self.client.get_json(
                f"{_MOF_API_BASE}/article/getbyslug",
                params={"slug": slug},
            )
        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch mof article %s: %s", url, exc)
            return html
        api_html = _render_mof_article_html(payload)
        return api_html or html

    def _should_use_moha_api(self, url: str, html: str) -> bool:
        if not self._extract_moha_id(url):
            return False
        parsed = urlparse(url)
        domain = (parsed.hostname or parsed.netloc).lower()
        if not (domain == "moha.gov.vn" or domain.endswith(".moha.gov.vn")):
            return False
        if '<div id="root"></div>' in html:
            return True
        return not _moha_html_has_content(html)

    def _should_use_mof_api(self, url: str, html: str) -> bool:
        if not self._extract_mof_slug(url):
            return False
        parsed = urlparse(url)
        domain = (parsed.hostname or parsed.netloc).lower()
        if not (domain == "mof.gov.vn" or domain.endswith(".mof.gov.vn")):
            return False
        if '<div id="app"></div>' in html or '<div id="app">' in html:
            return True
        return "<title>" in html and "</title>" in html and "<div id=\"app\"" in html

    @staticmethod
    def _extract_moha_id(url: str) -> str | None:
        match = _MOHA_ID_RE.search(url or "")
        if not match:
            return None
        return match.group("id")

    @staticmethod
    def _extract_mof_slug(url: str) -> str | None:
        path = urlparse(url).path or ""
        parts = [segment for segment in path.split("/") if segment]
        if not parts:
            return None
        slug = parts[-1].strip()
        if slug in {"mof", "btc", _MOF_ROOT_SLUG, "search", "content"}:
            return None
        return slug or None

    @staticmethod
    def _slugify_moha_title(title: str) -> str | None:
        if not title:
            return None
        lowered = title.lower()
        normalized = unicodedata.normalize("NFD", lowered)
        stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        stripped = stripped.replace("đ", "d")
        stripped = re.sub(r"[^0-9a-z-\\s]", "", stripped)
        stripped = re.sub(r"(\\s+)", "-", stripped)
        stripped = re.sub(r"-+", "-", stripped)
        stripped = stripped.strip("-")
        return stripped or None

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
            suffix.strip().lower().lstrip(".")
            for suffix in suffixes
            if suffix and suffix.strip()
        ]
        if not normalized_suffixes:
            return True
        parsed = urlparse(url)
        host = (parsed.hostname or parsed.netloc).lower()
        if host.startswith("www."):
            host = host[4:]
        return any(host == suffix or host.endswith(f".{suffix}") for suffix in normalized_suffixes)

    def _is_allowed_internal_host(self, host: str, base_host: str) -> bool:
        if not host:
            return False
        host = host.lower()
        base_host = base_host.lower()
        if host.startswith("www."):
            host = host[4:]
        if base_host.startswith("www."):
            base_host = base_host[4:]
        if host == base_host:
            return True

        suffixes = getattr(self.site, "allowed_internal_host_suffixes", ())
        if not suffixes:
            return False
        normalized_suffixes = [
            suffix.strip().lower().lstrip(".")
            for suffix in suffixes
            if suffix and suffix.strip()
        ]
        if not normalized_suffixes:
            return False
        return any(host == suffix or host.endswith(f".{suffix}") for suffix in normalized_suffixes)

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

        forced_category_id = getattr(self.site, "forced_category_id", None)
        forced_category_name = getattr(self.site, "forced_category_name", None)
        if forced_category_id:
            data.category_id = forced_category_id
        if forced_category_name:
            data.category_name = forced_category_name

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
        if content and len(content.strip()) < 50:
            raise SkipArticle(f"Missing article content for {url}")
        if not content or not content.strip():
            content = None

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
                "thanhtra",
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

        if forced_category_id:
            category_id = forced_category_id
        if forced_category_name:
            category_name = forced_category_name

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
