import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from crawl_lastest_news.config import SiteConfig  # noqa: E402
from crawl_lastest_news.site_crawler import (  # noqa: E402
    CategoryInfo,
    NewsSiteCrawler,
    SkipArticle,
)


class _FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get(self, url: str) -> str:
        return self._pages[url]


class SiteCrawlerUrlDiscoveryTests(unittest.TestCase):
    def test_fallback_discovery_still_applies_article_url_filters(self) -> None:
        site = SiteConfig(
            key="example",
            base_url="https://example.com",
            allowed_article_url_suffixes=(".html",),
            deny_article_prefixes=("/tag", "/search"),
        )

        category = CategoryInfo(url="https://example.com/cat", slug="cat")
        html = """
        <html><body>
          <div><a href="/tag/something.html">tag</a></div>
          <div><a href="/post/123456789">no suffix</a></div>
          <div><a href="/post/ok-123456789.html?utm=1#frag">ok</a></div>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),  # not used by _discover_category_articles
            client=_FakeClient({category.url: html}),
        )

        urls = crawler._discover_category_articles(category)
        self.assertEqual(urls, ["https://example.com/post/ok-123456789.html"])


class SiteCrawlerParseArticleTests(unittest.TestCase):
    def test_parse_article_skips_when_missing_content(self) -> None:
        site = SiteConfig(
            key="example",
            base_url="https://example.com",
        )
        crawler = NewsSiteCrawler(
            site,
            session=object(),
        )
        category = CategoryInfo(url="https://example.com/cat", slug="cat")

        html = """
        <html>
          <head>
            <meta property="article:section" content="Test"/>
          </head>
          <body></body>
        </html>
        """

        with self.assertRaises(SkipArticle) as ctx:
            crawler._parse_article(html, url="https://example.com/post.html", category=category)
        self.assertIn("Missing article content", str(ctx.exception))


class ArticleExtractorSiteConfigTests(unittest.TestCase):
    def test_nongnghiepmoitruong_prefers_div_content_article_body(self) -> None:
        from crawl_lastest_news.crawler.article import ArticleExtractor

        noise = "x " * 500
        html = f"""
        <html>
          <head>
            <meta property="article:section" content="Test"/>
          </head>
          <body>
            <article itemprop="articleBody">
              <p>KHỐI NHIỄU: {noise}</p>
            </article>
            <div class="content" itemprop="articleBody">
              <p>Đoạn 1 đúng.</p>
              <p>Đoạn 2 đúng.</p>
            </div>
          </body>
        </html>
        """

        extractor = ArticleExtractor("https://nongnghiepmoitruong.vn/post.html")
        data = extractor.extract(html)
        self.assertIsNotNone(data.content)
        self.assertIn("Đoạn 1 đúng.", data.content)
        self.assertIn("Đoạn 2 đúng.", data.content)
        self.assertNotIn("KHỐI NHIỄU", data.content)

    def test_daibieunhandan_video_prefers_c_video_detail(self) -> None:
        from crawl_lastest_news.crawler.article import ArticleExtractor

        noise = "x " * 500
        html = f"""
        <html>
          <head>
            <meta property="article:section" content="Test"/>
          </head>
          <body>
            <article itemprop="articleBody">
              <p>KHỐI NHIỄU: {noise}</p>
            </article>
            <div class="c-video-detail">
              <p>Nội dung video đúng.</p>
              <p>Đoạn 2.</p>
            </div>
          </body>
        </html>
        """

        extractor = ArticleExtractor("https://daibieunhandan.vn/video.html")
        data = extractor.extract(html)
        self.assertIsNotNone(data.content)
        self.assertIn("Nội dung video đúng.", data.content)
        self.assertIn("Đoạn 2.", data.content)
        self.assertNotIn("KHỐI NHIỄU", data.content)
