import sys
import unittest
from pathlib import Path

from requests.adapters import HTTPAdapter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from crawl_lastest_news.config import SiteConfig  # noqa: E402
from crawl_lastest_news.config import get_site_config  # noqa: E402
from crawl_lastest_news.site_crawler import (  # noqa: E402
    CategoryInfo,
    NewsSiteCrawler,
    RateLimitedHttpClient,
    SkipArticle,
)


class _FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get(self, url: str) -> str:
        return self._pages[url]


class _FakeClientWithFailures:
    def __init__(self, pages: dict[str, str], failures: set[str]) -> None:
        self._pages = pages
        self._failures = failures

    def get(self, url: str) -> str:
        import requests

        if url in self._failures:
            response = requests.Response()
            response.status_code = 502
            response.url = url
            raise requests.HTTPError(f"502 Server Error for url: {url}", response=response)
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

    def test_huengaynay_config_only_allows_htm_html_article_suffixes(self) -> None:
        cfg = get_site_config("huengaynay")
        self.assertEqual(cfg.allowed_article_url_suffixes, (".htm", ".html"))

    def test_normalize_url_strips_default_https_port(self) -> None:
        site = SiteConfig(
            key="moh",
            base_url="https://moh.gov.vn",
        )
        crawler = NewsSiteCrawler(
            site,
            session=object(),
        )
        normalized = crawler._normalize_url("https://moh.gov.vn:443/tin-noi-bat/-/asset_publisher/x/content/y")
        self.assertEqual(
            normalized,
            "https://moh.gov.vn/tin-noi-bat/-/asset_publisher/x/content/y",
        )


class HttpClientSSLConfigTests(unittest.TestCase):
    def test_rate_limited_http_client_mounts_custom_ssl_adapter_per_host(self) -> None:
        client = RateLimitedHttpClient(
            base_url="https://example.com",
            allow_weak_dh_ssl=True,
        )

        adapter = client._session.get_adapter("https://example.com/")
        other_adapter = client._session.get_adapter("https://other.com/")

        self.assertIsInstance(adapter, HTTPAdapter)
        self.assertTrue(hasattr(adapter, "ssl_context"))
        self.assertIsInstance(other_adapter, HTTPAdapter)
        self.assertFalse(hasattr(other_adapter, "ssl_context"))


class SiteCrawlerCategoryDiscoveryTests(unittest.TestCase):
    def test_discover_categories_can_keep_nested_paths_for_vpcp(self) -> None:
        site = SiteConfig(
            key="vpcp",
            base_url="https://vpcp.chinhphu.vn",
            home_path="/",
            canonicalize_category_paths=False,
            max_categories=10,
            allow_category_prefixes=(
                "/thong-tin-hoat-dong.htm",
                "/cong-ttdt-chinh-phu/",
            ),
            deny_category_prefixes=(
                "/video",
            ),
            deny_category_path_regexes=(
                r"^/.+-\d{8,}\.htm$",
            ),
        )

        home_url = "https://vpcp.chinhphu.vn/"
        html = """
        <html><body>
          <a href="/thong-tin-hoat-dong.htm">Thông tin hoạt động</a>
          <a href="/cong-ttdt-chinh-phu/thong-cao-bao-chi.htm">Thông cáo báo chí</a>
          <a href="/mot-bai-viet-115260109145352342.htm">Bài viết</a>
          <a href="/video.htm">Video</a>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),  # not used by _discover_categories
            client=_FakeClient({home_url: html}),
        )

        categories = crawler._discover_categories()
        self.assertEqual(
            [category.url for category in categories],
            [
                "https://vpcp.chinhphu.vn/thong-tin-hoat-dong.htm",
                "https://vpcp.chinhphu.vn/cong-ttdt-chinh-phu/thong-cao-bao-chi.htm",
            ],
        )

    def test_discover_categories_respects_deny_category_regexes(self) -> None:
        site = SiteConfig(
            key="bvhttdl",
            base_url="https://bvhttdl.gov.vn",
            home_path="/",
            category_path_pattern="/{slug}.htm",
            max_categories=10,
            allow_category_prefixes=(
                "/du-lich",
            ),
            deny_category_path_regexes=(
                r"^/.+-\d{14,17}\.htm$",
            ),
        )

        home_url = "https://bvhttdl.gov.vn/"
        html = """
        <html><body>
          <a href="/du-lich.htm">Du lịch</a>
          <a href="/du-lich-an-giang-voi-khat-vong-vuon-tam-quoc-te-20260120162634507.htm">Bài viết</a>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),  # not used by _discover_categories
            client=_FakeClient({home_url: html}),
        )

        categories = crawler._discover_categories()
        self.assertEqual([category.url for category in categories], ["https://bvhttdl.gov.vn/du-lich.htm"])

    def test_discover_categories_filters_cema_article_links(self) -> None:
        site = SiteConfig(
            key="cema",
            base_url="http://cema.gov.vn",
            home_path="/home.htm",
            canonicalize_category_paths=False,
            max_categories=10,
            allow_category_prefixes=(
                "/tin-tuc",
                "/tin-tuc-hoat-dong",
                "/thong-bao",
                "/chuyen-doi-so",
            ),
            deny_category_path_regexes=(
                r"^/tin-tuc/[^/]+/[^/]+/.+\.htm$",
                r"^/tin-tuc-hoat-dong/.+\.htm$",
                r"^/thong-bao/.+\.htm$",
                r"^/chuyen-doi-so/.+\.htm$",
            ),
        )

        home_url = "http://cema.gov.vn/home.htm"
        html = """
        <html><body>
          <a href="/tin-tuc.htm">Tin tức</a>
          <a href="/tin-tuc/tin-tuc-su-kien/thoi-su-chinh-tri.htm">Thời sự</a>
          <a href="/tin-tuc/tin-tuc-su-kien/thoi-su-chinh-tri/bai-viet.htm">Bài viết</a>
          <a href="/tin-tuc-hoat-dong.htm">Tin tức hoạt động</a>
          <a href="/tin-tuc-hoat-dong/bai-viet.htm">Bài viết</a>
          <a href="/thong-bao.htm">Thông báo</a>
          <a href="/thong-bao/bai-viet.htm">Bài viết</a>
          <a href="/chuyen-doi-so.htm">Chuyển đổi số</a>
          <a href="/chuyen-doi-so/bai-viet.htm">Bài viết</a>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),  # not used by _discover_categories
            client=_FakeClient({home_url: html}),
        )

        categories = crawler._discover_categories()
        self.assertEqual(
            [category.url for category in categories],
            [
                "http://cema.gov.vn/tin-tuc.htm",
                "http://cema.gov.vn/tin-tuc/tin-tuc-su-kien/thoi-su-chinh-tri.htm",
                "http://cema.gov.vn/tin-tuc-hoat-dong.htm",
                "http://cema.gov.vn/thong-bao.htm",
                "http://cema.gov.vn/chuyen-doi-so.htm",
            ],
        )

    def test_discover_categories_can_keep_discovered_paths_when_configured(self) -> None:
        site = SiteConfig(
            key="moh",
            base_url="https://moh.gov.vn",
            home_path="/",
            category_path_pattern="/web/guest/{slug}",
            canonicalize_category_paths=False,
            max_categories=10,
            deny_category_path_regexes=(
                r"/-/",
            ),
        )

        home_url = "https://moh.gov.vn/"
        html = """
        <html><body>
          <a href="/tin-noi-bat">Tin nổi bật</a>
          <a href="/web/guest/tin-tuc">Tin tức</a>
          <a href="/tin-noi-bat/-/asset_publisher/abc/content/xyz">Bài viết</a>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),  # not used by _discover_categories
            client=_FakeClient({home_url: html}),
        )

        categories = crawler._discover_categories()
        self.assertEqual(
            [category.url for category in categories],
            [
                "https://moh.gov.vn/tin-noi-bat",
                "https://moh.gov.vn/web/guest/tin-tuc",
            ],
        )

    def test_moh_category_discovery_can_extract_asset_publisher_urls(self) -> None:
        site = SiteConfig(
            key="moh",
            base_url="https://moh.gov.vn",
            allowed_article_path_regexes=(r"/-/",),
        )
        category = CategoryInfo(url="https://moh.gov.vn/tin-noi-bat", slug="tin-noi-bat")

        article_path = (
            "/tin-noi-bat/-/asset_publisher/3Yst7YhbkA5j/content/"
            "sang-nay-khai-mac-trong-the-ai-hoi-ai-bieu-toan-quoc-lan-thu-xiv-cua-ang"
        )
        html = f"""
        <html><body>
          <div onclick="location.href='{article_path}';">Click</div>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),
            client=_FakeClient({category.url: html}),
        )
        urls = crawler._discover_category_articles(category)
        self.assertEqual(urls, [f"https://moh.gov.vn{article_path}"])

    def test_discover_query_categories_can_extract_slug_from_web_guest_pattern(self) -> None:
        site = SiteConfig(
            key="thanhtra",
            base_url="https://thanhtra.gov.vn",
            home_path="/",
            keep_query_params=True,
            category_path_pattern="/web/guest/{slug}",
            max_categories=10,
            allow_category_prefixes=(
                "/web/guest/tin-tong-hop",
            ),
            deny_category_prefixes=(
                "/web/guest/xem-chi-tiet-tin-tuc",
            ),
        )

        home_url = "https://thanhtra.gov.vn/"
        html = """
        <html><body>
          <a href="/web/guest/tin-tong-hop">Tin tổng hợp</a>
          <a href="/web/guest/xem-chi-tiet-tin-tuc/-/asset_publisher//Content/foo?123">Bài viết</a>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),  # not used by _discover_categories
            client=_FakeClient({home_url: html}),
        )

        categories = crawler._discover_categories()
        self.assertEqual(
            [(category.slug, category.url) for category in categories],
            [("tin-tong-hop", "https://thanhtra.gov.vn/web/guest/tin-tong-hop")],
        )

    def test_moh_category_article_discovery_retries_without_web_guest_prefix(self) -> None:
        site = SiteConfig(
            key="moh",
            base_url="https://moh.gov.vn",
            allowed_article_path_regexes=(r"/-/",),
        )
        category = CategoryInfo(url="https://moh.gov.vn/web/guest/tin-noi-bat", slug="tin-noi-bat")

        article_path = (
            "/tin-noi-bat/-/asset_publisher/3Yst7YhbkA5j/content/"
            "sang-nay-khai-mac-trong-the-ai-hoi-ai-bieu-toan-quoc-lan-thu-xiv-cua-ang"
        )
        empty_html = "<html><body><p>no links here</p></body></html>"
        fallback_html = f"<html><body><a href=\"{article_path}\">link</a></body></html>"

        crawler = NewsSiteCrawler(
            site,
            session=object(),
            client=_FakeClient(
                {
                    category.url: empty_html,
                    "https://moh.gov.vn/tin-noi-bat": fallback_html,
                }
            ),
        )
        urls = crawler._discover_category_articles(category)
        self.assertEqual(urls, [f"https://moh.gov.vn{article_path}"])


class SbvUrlFilteringTests(unittest.TestCase):
    def test_sbv_category_article_discovery_accepts_html_and_numeric_suffix(self) -> None:
        site = SiteConfig(
            key="sbv",
            base_url="https://sbv.gov.vn",
            allowed_article_path_regexes=(
                r"/-/",
                r"/chi-tiet",
                r"\.(?:html|htm|aspx)$",
                r"-\d+/?$",
            ),
        )
        category = CategoryInfo(url="https://sbv.gov.vn/vi/tin-tuc", slug="tin-tuc")
        html = """
        <html><body>
          <a href="/vi/chi-tiet/some-article">ok-chi-tiet</a>
          <a href="/vi/bai-viet-12345">ok-numeric</a>
          <a href="/vi/tin-tuc/some-post.html">ok-html</a>
          <a href="/vi/tin-tuc/">category</a>
        </body></html>
        """

        crawler = NewsSiteCrawler(
            site,
            session=object(),
            client=_FakeClient({category.url: html}),
        )
        urls = crawler._discover_category_articles(category)
        self.assertEqual(
            urls,
            [
                "https://sbv.gov.vn/vi/chi-tiet/some-article",
                "https://sbv.gov.vn/vi/bai-viet-12345",
                "https://sbv.gov.vn/vi/tin-tuc/some-post.html",
            ],
        )


class SiteCrawlerParseArticleTests(unittest.TestCase):
    def test_parse_article_allows_missing_content(self) -> None:
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

        data = crawler._parse_article(html, url="https://example.com/post.html", category=category)
        self.assertIsNone(data.content)

    def test_parse_article_can_force_category_for_moh(self) -> None:
        site = SiteConfig(
            key="moh",
            base_url="https://moh.gov.vn",
            forced_category_id="yte",
            forced_category_name="yte",
        )
        crawler = NewsSiteCrawler(
            site,
            session=object(),
        )
        category = CategoryInfo(url="https://moh.gov.vn/tin-tuc", slug="tin-tuc", name="Tin tức")

        html = """
        <html>
          <head><title>Tiêu đề</title></head>
          <body>
            <article>
              <p>Nội dung đủ dài để không bị bỏ qua khi kiểm tra độ dài. Nội dung tiếp theo.</p>
            </article>
          </body>
        </html>
        """

        data = crawler._parse_article(html, url="https://moh.gov.vn/web/guest/-/tin-chi-tiet", category=category)
        self.assertEqual(data.category_id, "yte")
        self.assertEqual(data.category_name, "yte")

    def test_moh_fetch_article_html_can_strip_locale_on_502(self) -> None:
        site = SiteConfig(
            key="moh",
            base_url="https://moh.gov.vn",
        )
        url = "https://moh.gov.vn/vi_VN/tin-tong-hop/-/asset_publisher/x/content/y"
        fallback_url = "https://moh.gov.vn/tin-tong-hop/-/asset_publisher/x/content/y"

        crawler = NewsSiteCrawler(
            site,
            session=object(),
            client=_FakeClientWithFailures(
                {
                    fallback_url: "<html>ok</html>",
                },
                failures={url},
            ),
        )

        html = crawler._fetch_article_html(url)
        self.assertEqual(html, "<html>ok</html>")


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

    def test_moh_breadcrumb_category_extractor(self) -> None:
        from crawl_lastest_news.crawler.article import ArticleExtractor

        html = """
        <html>
          <head>
            <meta property="og:title" content="Tiêu đề bài"/>
          </head>
          <body>
            <nav class="breadcrumb">
              <ol>
                <li><a href="/">Trang chủ</a></li>
                <li><a href="/web/guest/tin-tuc">Tin tức</a></li>
                <li><span>Tiêu đề bài</span></li>
              </ol>
            </nav>
            <div class="journal-content-article">
              <p>Đoạn 1.</p>
              <p>Đoạn 2.</p>
            </div>
          </body>
        </html>
        """

        extractor = ArticleExtractor("https://moh.gov.vn/web/guest/-/tin-chi-tiet")
        data = extractor.extract(html)
        self.assertEqual(data.category_id, "tin-tuc")
        self.assertEqual(data.category_name, "Tin tức")

    def test_thanhtra_excludes_other_assets_from_content(self) -> None:
        from crawl_lastest_news.crawler.article import ArticleExtractor

        html = """
        <html>
          <head>
            <meta property="article:section" content="Test"/>
          </head>
          <body>
            <div class="article">
              <p>Nội dung đúng 1.</p>
              <p>Nội dung đúng 2.</p>
            </div>
            <div class="other_assets">
              <p>Bài viết liên quan A</p>
              <p>Bài viết liên quan B</p>
            </div>
          </body>
        </html>
        """

        extractor = ArticleExtractor("https://thanhtra.gov.vn/xem-chi-tiet-tin-tuc/-/asset_publisher//Content/foo?123")
        data = extractor.extract(html)
        self.assertIsNotNone(data.content)
        self.assertIn("Nội dung đúng 1.", data.content)
        self.assertIn("Nội dung đúng 2.", data.content)
        self.assertNotIn("Bài viết liên quan", data.content)
