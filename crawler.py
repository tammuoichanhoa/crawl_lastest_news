from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag
from sqlalchemy.orm import Session

from .config import SiteConfig
from .db.models import Article, ArticleImage, ArticleVideo


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


class RateLimitedHttpClient:
    """Wrapper quanh requests.Session có delay giữa các request."""

    def __init__(
        self,
        *,
        delay_seconds: float = 0.5,
        timeout: int = 20,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._session = requests.Session()
        self._delay = max(float(delay_seconds), 0.0)
        self._timeout = max(int(timeout), 1)
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

    def get(self, url: str) -> str:
        self._respect_delay()
        response = self._session.get(url, headers=self._headers, timeout=self._timeout)
        response.raise_for_status()
        return response.text

    def _respect_delay(self) -> None:
        if self._delay <= 0:
            return
        now = time.time()
        if now < self._next_request_ts:
            time.sleep(self._next_request_ts - now)
        self._next_request_ts = time.time() + self._delay


def _normalize_internal_url(base_url: str, href: str) -> Optional[str]:
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
    if host != base_host and host != f"www.{base_host}":
        return None

    cleaned = parsed._replace(query="", fragment="")
    return urlunparse(cleaned)


def _slug_from_path(path: str) -> str:
    path = path.strip("/") or "root"
    first_segment = path.split("/")[0]
    return first_segment or "root"


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
    # Một số selector phổ biến
    candidates = [
        "article.fck_detail",
        "article#main-detail-body",
        "article.article",
        "div#main_detail",
        "div#content",
        "div.article-content",
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
        # Xử lý chuỗi kết thúc bằng 'Z'
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

    for selector in ("article", "#content", "#main_detail", ".article-content"):
        container = soup.select_one(selector)
        if not container:
            continue

        for img in container.find_all("img"):
            candidate = img.get("data-src") or img.get("src")
            url = _normalize_internal_url(base_url, candidate) if candidate else None
            if url and url not in seen_img:
                seen_img.add(url)
                images.append(url)

        for tag_name in ("video", "iframe", "source"):
            for node in container.find_all(tag_name):
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
        session: Session,
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

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "inserted": self._inserted,
            "skipped": self._skipped,
            "failed": self._failed,
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def crawl(self, *, max_articles: Optional[int] = None) -> None:
        """
        Quy trình:
        1. Lấy danh sách category từ trang chủ.
        2. Với mỗi category → lấy danh sách URL bài mới.
        3. Với mỗi bài → tải HTML, bóc tách thông tin, lưu DB.
        """
        LOGGER.info("=== Crawling site %s (%s) ===", self.site.key, self.site.base_url)
        categories = self._discover_categories()
        LOGGER.info(
            "Found %s categories for %s", len(categories), self.site.key
        )

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
                except Exception as exc:  # pylint: disable=broad-except
                    self._failed += 1
                    LOGGER.exception("Failed to crawl article %s: %s", url, exc)

    # ------------------------------------------------------------------ #
    # Category & article list discovery
    # ------------------------------------------------------------------ #
    def _discover_categories(self) -> List[CategoryInfo]:
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
            normalized = _normalize_internal_url(self.site.base_url, anchor["href"])
            if not normalized:
                continue

            parsed = urlparse(normalized)
            host = parsed.netloc.lower()
            if host != base_host and host != f"www.{base_host}":
                continue

            path = parsed.path or "/"

            if path in self.site.deny_exact_paths:
                continue

            # Chỉ giữ path 1 cấp hoặc 2 cấp; lấy segment đầu tiên làm slug
            slug = _slug_from_path(path)
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

            # Canonical URL cho category
            canonical = urlunparse(
                parsed._replace(path=category_path, query="", fragment="")
            )
            if canonical not in categories:
                categories[canonical] = CategoryInfo(url=canonical, slug=slug)
                if len(categories) >= self.site.max_categories:
                    break

        return list(categories.values())

    def _discover_category_articles(self, category: CategoryInfo) -> List[str]:
        try:
            html = self.client.get(category.url)
        except requests.RequestException as exc:
            LOGGER.warning(
                "Failed to fetch category page %s: %s", category.url, exc
            )
            return []
        soup = BeautifulSoup(html, "html.parser")

        article_urls: List[str] = []
        seen: Set[str] = set()

        def _register(href: str) -> None:
            normalized = _normalize_internal_url(self.site.base_url, href)
            if not normalized:
                return
            if normalized in seen:
                return
            seen.add(normalized)
            article_urls.append(normalized)

        # 1. Nếu có selector cấu hình, ưu tiên dùng trước
        if self.site.article_link_selector:
            for node in soup.select(self.site.article_link_selector):
                href = node.get("href")
                if href:
                    _register(href)

        # 2. Heuristic chung: trong <article> hoặc các thẻ title
        if not article_urls:
            for node in soup.find_all("article"):
                anchor = node.find("a", href=True)
                if anchor:
                    _register(anchor["href"])

        if not article_urls:
            for selector in ("h3 a[href]", "h2 a[href]"):
                for node in soup.select(selector):
                    href = node.get("href")
                    if href:
                        _register(href)

        # 3. Fallback cuối: mọi <a> nội bộ có path đủ dài (tránh menu)
        if not article_urls:
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"]
                normalized = _normalize_internal_url(self.site.base_url, href)
                if not normalized:
                    continue
                parsed = urlparse(normalized)
                if len(parsed.path or "") < 10:
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                article_urls.append(normalized)

        if self.site.max_articles_per_category and len(article_urls) > self.site.max_articles_per_category:
            article_urls = article_urls[: self.site.max_articles_per_category]

        return article_urls

    # ------------------------------------------------------------------ #
    # Article detail parsing & persistence
    # ------------------------------------------------------------------ #
    def _parse_article(self, html: str, *, url: str, category: CategoryInfo) -> ParsedArticle:
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title_node = (
            soup.select_one("h1.title-detail")
            or soup.select_one("h1.article-title")
            or soup.find("h1")
        )
        title = _text_or_none(title_node) or url

        # Description
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

        content = _extract_main_content(soup) or None

        # Category name: thử lấy từ breadcrumb
        category_name = None
        breadcrumb = soup.select_one("ul.breadcrumb, nav.breadcrumb")
        if breadcrumb:
            tokens: List[str] = []
            for li in breadcrumb.find_all("li"):
                text = li.get_text(strip=True)
                if text:
                    tokens.append(text)
            if tokens:
                category_name = tokens[-1]

        category_id = category.slug

        publish_date = _extract_publish_date(soup)
        tags = _extract_tags(soup)
        images, videos = _extract_images_and_videos(soup, base_url=self.site.base_url)

        return ParsedArticle(
            url=url,
            title=title,
            description=description,
            content=content,
            category_id=category_id,
            category_name=category_name,
            tags=tags,
            publish_date=publish_date,
            images=images,
            videos=videos,
        )

    def _save_article(self, parsed: ParsedArticle) -> None:
        existing = (
            self.session.query(Article.id)
            .filter(Article.url == parsed.url)
            .first()
        )
        if existing:
            self._skipped += 1
            return

        tags_str = self._join_tags(parsed.tags)

        article = Article(
            title=parsed.title,
            description=parsed.description,
            content=parsed.content,
            category_id=parsed.category_id,
            category_name=parsed.category_name,
            comments=None,
            tags=tags_str,
            url=parsed.url,
            publish_date=parsed.publish_date,
            article_name=self.site.resolved_article_name(),
        )
        self.session.add(article)
        self.session.flush()  # để có article.id cho images/videos

        for idx, img_url in enumerate(parsed.images, start=1):
            article.images.append(
                ArticleImage(
                    image_path=img_url,
                    sequence_number=idx,
                )
            )

        for idx, video_url in enumerate(parsed.videos, start=1):
            article.videos.append(
                ArticleVideo(
                    video_path=video_url,
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
        # Cột Article.tags dài 500 ký tự → cắt bớt nếu cần.
        return concatenated[:500]
