from __future__ import annotations

"""
Khai báo cấu hình cho nhiều trang báo.

Ý tưởng:
- Mỗi trang báo (vnexpress, tuoitre, ...) được mô tả bằng một `SiteConfig`
  gồm base_url, các rule lọc category, số lượng bài tối đa, v.v.
- Phần logic crawl/parse HTML sẽ ở `crawler.py` và đọc cấu hình từ đây.

Bạn có thể thêm/sửa cấu hình cho trang mới mà không phải sửa code crawler.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple


@dataclass(slots=True)
class SiteConfig:
    """Cấu hình crawl cho 1 trang báo."""

    # Tên ngắn dùng trong CLI / logging, ví dụ: "vnexpress"
    key: str
    # Base URL, ví dụ "https://vnexpress.net"
    base_url: str

    # Đường dẫn trang chủ tương đối (mặc định "/")
    home_path: str = "/"

    # Mẫu path canonical cho category, dùng slug:
    # ví dụ "/{slug}" (mặc định), hoặc "/{slug}.htm" cho một số site như Tuổi Trẻ.
    category_path_pattern: str = "/{slug}"

    # Nếu True (mặc định), crawler sẽ chuẩn hoá URL category theo `category_path_pattern`.
    # Một số site (vd. Liferay) có thể link category ở nhiều dạng path khác nhau; khi đó
    # có thể tắt để giữ nguyên path discover được trên trang chủ.
    canonicalize_category_paths: bool = True

    # Tên nguồn báo lưu trong cột Article.article_name (ví dụ: "vnexpress")
    article_name: str | None = None

    # Giới hạn số lượng category & số lượng bài / category để tránh crawl quá nhiều.
    max_categories: int = 20
    max_articles_per_category: int = 100

    # Các rule lọc category trên trang chủ:
    # - chỉ lấy link nội bộ có path bắt đầu bằng 1 trong các prefix này (nếu không rỗng)
    # - loại trừ các path bắt đầu bằng 1 trong các prefix này.
    allow_category_prefixes: Tuple[str, ...] = field(default_factory=tuple)
    deny_category_prefixes: Tuple[str, ...] = field(default_factory=tuple)

    # Một số path không phải category (video, podcast, ...) sẽ bỏ qua.
    deny_exact_paths: Tuple[str, ...] = field(default_factory=tuple)

    # Loại bỏ các category có path khớp regex (nếu rỗng sẽ bỏ qua lọc).
    deny_category_path_regexes: Tuple[str, ...] = field(default_factory=tuple)

    # Selector ưu tiên để tìm link bài viết trong trang category (nếu rỗng sẽ dùng heuristic chung).
    article_link_selector: str | None = None

    # Các selector ưu tiên để lấy description/sapo của bài viết (nếu rỗng sẽ dùng heuristic chung).
    description_selectors: Tuple[str, ...] = field(default_factory=tuple)

    # Chỉ chấp nhận các locale/language cụ thể (ví dụ: ("vi", "vi-vn")).
    allowed_locales: Tuple[str, ...] = field(default_factory=tuple)

    # Cho phép crawl category (internal link) trên các host phụ/alias.
    # Mặc định chỉ chấp nhận base_host (từ base_url) và biến thể www.
    allowed_internal_host_suffixes: Tuple[str, ...] = field(default_factory=tuple)

    # Nếu fetch category bị 404, thử fallback bằng cách strip các suffix này khỏi path
    # (ví dụ "/tin-tuc.htm" -> "/tin-tuc"). Hữu ích với site thay đổi canonical URL.
    category_fetch_fallback_strip_suffixes: Tuple[str, ...] = field(default_factory=tuple)

    # Chỉ chấp nhận các host bài viết có hậu tố (suffix) nhất định, ví dụ: (".vn",)
    allowed_article_host_suffixes: Tuple[str, ...] = field(default_factory=tuple)

    # Chỉ lấy link bài viết có đuôi (suffix) cụ thể, ví dụ: (".html",)
    allowed_article_url_suffixes: Tuple[str, ...] = field(default_factory=tuple)

    # Chỉ lấy link bài viết có path khớp regex (nếu rỗng sẽ bỏ qua lọc theo path).
    allowed_article_path_regexes: Tuple[str, ...] = field(default_factory=tuple)

    # Loại bỏ các bài viết có path bắt đầu bằng những prefix này.
    deny_article_prefixes: Tuple[str, ...] = field(default_factory=tuple)

    # Giữ lại query string khi chuẩn hóa URL (mặc định loại bỏ).
    keep_query_params: bool = False

    # Override timeout (giây) cho request nếu site chậm phản hồi.
    timeout_seconds: int | None = None

    # Delay giữa các request (giây), dùng để hạn chế rate limit/anti-bot.
    delay_seconds: float | None = None

    # Số lần retry cho HTTP 429/5xx và các lỗi mạng tạm thời.
    max_retries: int = 2

    # Hệ số backoff giữa các lần retry: sleep = retry_backoff * 2**attempt.
    retry_backoff: float = 1.0

    # Các marker text báo hiệu bị chặn, dùng để retry.
    blocked_content_markers: Tuple[str, ...] = field(default_factory=tuple)

    # Header bổ sung cho request (ví dụ User-Agent đặc thù).
    request_headers: Dict[str, str] = field(default_factory=dict)

    # Một số site cấu hình TLS lỗi thời có thể gây lỗi handshake trên OpenSSL mới.
    # Bật các flag này chỉ khi thật sự cần cho site tương ứng.
    allow_legacy_ssl: bool = False
    allow_weak_dh_ssl: bool = False

    # Nếu cấu hình, sẽ ép category_id/category_name của mọi bài viết về giá trị này
    # (dùng khi hệ thống downstream cần phân loại cố định theo nguồn).
    forced_category_id: str | None = None
    forced_category_name: str | None = None

    def resolved_article_name(self) -> str:
        """Giá trị cuối cùng để ghi vào Article.article_name."""
        if self.article_name:
            return self.article_name
        # Mặc định dùng key nếu không cấu hình riêng.
        return self.key


def _vnexpress_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://vnexpress.net.

    - Category thường có path dạng /thoi-su, /the-gioi, ...
    - Dùng heuristic: chỉ lấy các path 1 cấp ("/abc") và không nằm trong danh sách deny.
    - Ở trang category, VNExpress dùng thẻ <article class="item-news">,
      nên ta khai báo article_link_selector để crawler ưu tiên selector này.
    """

    return SiteConfig(
        key="vnexpress",
        base_url="https://vnexpress.net",
        home_path="/",
        article_name="vnexpress",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/goc-nhin",
            "/the-gioi",
            "/kinh-doanh",
            "/giai-tri",
            "/the-thao",
            "/phap-luat",
            "/giao-duc",
            "/suc-khoe",
            "/doi-song",
            "/du-lich",
            "/khoa-hoc",
            "/so-hoa",
            "/oto-xe-may",
            "/y-kien",
            "/tam-su",
        ),
        deny_category_prefixes=(
            "/video",
            "/podcast",
            "/infographics",
            "/interactive",
        ),
        deny_exact_paths=(
            "/",
        ),
        deny_category_path_regexes=(
            r"^/chuyen-muc/.+-\\d{4,}\\.htm$",
        ),
        allowed_article_url_suffixes=(),
        article_link_selector="article.item-news a[href]",
    )


def _tuoitre_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://tuoitre.vn.

    - Category thường có path dạng /thoi-su.htm, /kinh-doanh.htm, ...
    - Heuristic: ưu tiên path 1 cấp và kết thúc bằng ".htm".
    """

    return SiteConfig(
        key="tuoitre",
        base_url="https://tuoitre.vn",
        home_path="/",
        category_path_pattern="/{slug}.htm",
        article_name="tuoitre",
        description_selectors=(
            "h2.detail-sapo[data-role='sapo']",
            "h2.detail-sapo",
        ),
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/the-gioi",
            "/kinh-doanh",
            "/giai-tri",
            "/the-thao",
            "/phap-luat",
            "/giao-duc",
            "/suc-khoe",
            "/doi-song",
            "/du-lich",
            "/khoa-hoc",
            "/cong-nghe",
        ),
        deny_category_prefixes=(
            "/podcast",
            "/video",
        ),
        deny_exact_paths=(
            "/",
        ),
        # Tuổi Trẻ thường dùng <h3 class="title-news"><a ...>
        article_link_selector="h3.title-news a[href], h2.title-news a[href]",
    )


def _nguoilaodong_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://nld.com.vn (Báo Người Lao Động).

    Hiện tại trang chủ trả về trang captcha chống DDoS, nên tạm thời dùng
    cấu hình mặc định và heuristic chung, chỉ giới hạn đuôi URL bài viết
    là ".htm" theo các link đã thu thập được trong dữ liệu xuất.
    """

    return _default_site_config(
        "nguoilaodong",
        "https://nld.com.vn",
        allowed_article_url_suffixes=(".htm",),
    )


def _laodong_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://laodong.vn (Báo Lao Động).

    - Bài viết chi tiết có URL đuôi ".ldo" theo các link đã thu thập được
      trong exported_data.
    - Các chuyên mục chính có path dạng /thoi-su, /xa-hoi, /kinh-doanh, ...
    """

    return _default_site_config(
        "laodong",
        "https://laodong.vn",
        allowed_article_url_suffixes=(".ldo",),
        allow_category_prefixes=(
            "/thoi-su",
            "/xa-hoi",
            "/kinh-doanh",
            "/bat-dong-san",
            "/van-hoa",
            "/phap-luat",
            "/giao-duc",
            "/y-te",
            "/cong-doan",
            "/su-kien-binh-luan",
        ),
    )


def _default_site_config(
    key: str,
    base_url: str,
    *,
    article_name: str | None = None,
    **overrides: Any,
) -> SiteConfig:
    """
    Cấu hình mặc định dùng chung cho các trang báo có cấu trúc đơn giản.

    Nếu cần tuỳ biến thêm (prefix category, selector description, ...), tạo hàm
    riêng thay vì dùng helper này.
    """

    return SiteConfig(
        key=key,
        base_url=base_url,
        home_path="/",
        article_name=article_name or key,
        deny_exact_paths=("/",),
        **overrides,
    )


def _genk_config() -> SiteConfig:
    return _default_site_config("genk", "https://genk.vn")


def _kenh14_config() -> SiteConfig:
    return _default_site_config("kenh14", "https://kenh14.vn")


def _mattran_config() -> SiteConfig:
    return _default_site_config("mattran", "https://mattran.org.vn")



def _thanhnien_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://thanhnien.vn.

    - Category chính có path dạng /thoi-su.htm, /the-gioi.htm, ...
    - Trang category và trang bài đều dùng đuôi .htm, nên giới hạn
      allowed_article_url_suffixes để tránh thu thập các URL không phải bài viết.
    - Ở trang category, danh sách bài dùng thẻ
      <a class="box-category-link-title" data-linktype="newsdetail" ...>,
      vì vậy khai báo article_link_selector để crawler ưu tiên selector này.
    """

    return SiteConfig(
        key="thanhnien",
        base_url="https://thanhnien.vn",
        home_path="/",
        article_name="thanhnien",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/thoi-su",
            "/the-gioi",
            "/kinh-te",
            "/doi-song",
            "/suc-khoe",
            "/gioi-tre",
            "/giao-duc",
            "/du-lich",
            "/van-hoa",
            "/giai-tri",
            "/the-thao",
            "/cong-nghe",
            "/xe",
            "/tieu-dung-thong-minh",
        ),
        deny_category_prefixes=(
            "/video",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_article_url_suffixes=(".htm",),
        article_link_selector="a.box-category-link-title[data-linktype='newsdetail']",
    )


def _nguoiquansat_config() -> SiteConfig:
    return _default_site_config("nguoiquansat", "https://nguoiquansat.vn")


def _tinnhanhchungkhoan_config() -> SiteConfig:
    return _default_site_config(
        "tinnhanhchungkhoan",
        "https://www.tinnhanhchungkhoan.vn",
    )


def _giadinh_suckhoedoisong_config() -> SiteConfig:
    return _default_site_config(
        "giadinh_suckhoedoisong",
        "https://giadinh.suckhoedoisong.vn",
    )


def _nhandan_config() -> SiteConfig:
    return SiteConfig(
        key="nhandan",
        base_url="https://nhandan.vn",
        home_path="/",
        article_name="nhandan",
        deny_exact_paths=("/",),
        deny_category_prefixes=(
            "/mua-bao.html",
            "/tin-moi.html",
            "/dia-phuong.html",
            "/chinhtri",
            "/binh-luan-phe-phan",
            "/xay-dung-dang",
            "/chungkhoan",
            "/thong-tin-hang-hoa",
            "/bhxh-va-cuoc-song",
            "/nguoi-tot-viec-tot",
            "/phapluat",
            "/binh-luan-quoc-te",
            "/chau-phi",
            "/trung-dong",
            "/chau-a-tbd",
            "/goc-tu-van",
            "/khoahoc-congnghe",
            "/phong-chong-toi-pham-cong-nghe-cao-2025",
            "/moi-truong",
            "/duong-day-nong",
            "/dieu-tra-qua-thu-ban-doc",
            "/factcheck",
            "/tri-thuc-chuyen-sau.html",
            "/54-dan-toc",
            "/e-magazine",
            "/multimedia",
            "/video-chinh-tri",
            "/video-kinh-te",
            "/video-van-hoa",
            "/video-xa-hoi",
            "/video-phap-luat",
            "/video-du-lich",
            "/video-the-gioi",
            "/video-the-thao",
            "/video-giao-duc",
            "/video-y-te",
            "/video-khcn",
            "/video-moi-truong",
            "/giaoduc-infographic",
            "/trung-du-va-mien-nui-bac-bo",
            "/dong-bang-song-hong",
            "/trang-bac-trung-bo-va-duyen-hai-trung-bo",
            "/trang-tay-nguyen",
            "/trang-dong-nam-bo",
            "/trang-dong-bang-song-cuu-long",
            "/chu-de.html",
            "/gioi-thieu.html",
        ),
    )


def _vietbao_config() -> SiteConfig:
    return SiteConfig(
        key="vietbao",
        base_url="https://vietbao.vn",
        home_path="/",
        article_name="vietbao",
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        deny_article_prefixes=(
            "/en",
            "/en/",
            "/zh-CN",
            "/zh-CN/",
            "/zh-cn",
            "/zh-cn/",
            "/cn",
            "/cn/",
            "/404",
        ),
    )


def _anninhthudo_config() -> SiteConfig:
    return _default_site_config("anninhthudo", "https://www.anninhthudo.vn")


def _cafebiz_config() -> SiteConfig:
    return _default_site_config(
        "cafebiz",
        "https://cafebiz.vn",
        allowed_locales=("vi", "vi-vn"),
        allowed_article_host_suffixes=(".vn",),
        description_selectors=(
            "h2.sapo",
            "p.sapo",
            "div.sapo",
        ),
    )


def _daibieunhandan_config() -> SiteConfig:
    return _default_site_config("daibieunhandan", "https://daibieunhandan.vn")


def _congly_config() -> SiteConfig:
    return _default_site_config("congly", "https://congly.vn")


def _nongnghiepmoitruong_config() -> SiteConfig:
    return SiteConfig(
        key="nongnghiepmoitruong",
        base_url="https://nongnghiepmoitruong.vn",
        home_path="/",
        article_name="nongnghiepmoitruong",
        deny_exact_paths=("/",),
        description_selectors=(
            "h2.main-intro.detail-intro",
        ),
    )


def _cafef_config() -> SiteConfig:
    return _default_site_config("cafef", "https://cafef.vn")


def _vtv_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://vtv.vn.

    Thực tế VTV có thể phục vụ nội dung qua cả vtv.gov.vn và vtv.vn, nên cấu hình
    cho phép host suffix của cả 2 domain để tránh bỏ sót link bài.
    """

    return _default_site_config(
        "vtv",
        "https://vtv.vn",
        allowed_locales=("vi", "vi-vn"),
        allowed_internal_host_suffixes=(
            "vtv.vn",
            "vtv.gov.vn",
        ),
        allowed_article_host_suffixes=(
            "vtv.vn",
            "vtv.gov.vn",
        ),
        allowed_article_url_suffixes=(
            ".htm",
            ".html",
        ),
    )


def _vtvgov_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://vtv.gov.vn.

    Tách key riêng để tránh nhầm với site https://vtv.vn.
    """

    return SiteConfig(
        key="vtvgov",
        base_url="https://vtv.gov.vn",
        home_path="/",
        category_path_pattern="/{slug}.htm",
        canonicalize_category_paths=False,
        article_name="vtv",
        max_categories=30,
        max_articles_per_category=80,
        # Cho phép "/" được coi như 1 category để crawl trực tiếp link bài
        # ngay trên trang chủ (vtv.gov.vn hiển thị nhiều link /news/* ở homepage).
        deny_exact_paths=(),
        deny_category_prefixes=(
            "/lien-he",
            "/gioi-thieu",
            "/dieu-khoan",
            "/login",
            "/danh-ba",
            "/thu-dien-tu",
            "/dang-ky",
            "/video",
            "/podcast",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_internal_host_suffixes=(
            "vtv.gov.vn",
            "vtv.vn",
        ),
        category_fetch_fallback_strip_suffixes=(
            ".htm",
            ".html",
        ),
        allowed_article_host_suffixes=(
            "vtv.gov.vn",
            "vtv.vn",
        ),
        # Link bài viết trên vtv.gov.vn thường không có đuôi .html/.htm
        # (ví dụ: https://vtv.gov.vn/news/tin-tuc-su-kien/<slug>), nên không lọc theo suffix.
        allowed_article_url_suffixes=(),
        allowed_article_path_regexes=(
            r"^/news/",
        ),
    )


def _vtcnews_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://vtcnews.vn.

    - Bài viết chi tiết có URL dạng \"...-ar<id>.html\".
    - Trang \"Tin mới hôm nay\" liệt kê các bài mới nhất toàn site.
    """

    return _default_site_config(
        "vtcnews",
        "https://vtcnews.vn",
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        # Danh sách bài viết sử dụng link có \"-ar<id>.html\".
        article_link_selector="a[href*='-ar'][href$='.html']",
    )


def _twentyfourh_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://www.24h.com.vn.

    - Category có path dạng /bong-da-c48.html, /kinh-doanh-c161.html, ...
    - Bài viết chi tiết có sapo trong h2#article_sapo và nội dung chính
      trong <article id="article_body" ...>.
    """

    return SiteConfig(
        key="24h",
        base_url="https://www.24h.com.vn",
        home_path="/",
        article_name="24h",
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        description_selectors=(
            "h2#article_sapo",
            "h2.cate-24h-foot-arti-deta-sum",
        ),
    )


def _tienphong_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://tienphong.vn.

    - Bài viết chi tiết có URL đuôi ".tpo" (ví dụ:
      "...-post1806382.tpo"), vì vậy giới hạn suffix này để tránh
      thu thập các trang không phải bài viết.
    - Sapo/description nằm trong div.article__sapo.cms-desc.
    """

    return _default_site_config(
        "tienphong",
        "https://tienphong.vn",
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".tpo",),
        description_selectors=(
            "div.article__sapo",
            "div.article__sapo.cms-desc",
        ),
    )


def _baolaocai_config() -> SiteConfig:
    return _default_site_config("baolaocai", "https://baolaocai.vn")


def _baolaichau_config() -> SiteConfig:
    """
    Cấu hình cho https://baolaichau.vn (Báo Lai Châu điện tử).

    - Category dạng /{slug}.
    - Bài viết có dạng /{category}/{slug}-{id}.
    - Link bài viết thường dùng class "blc-post__link".
    """

    return SiteConfig(
        key="baolaichau",
        base_url="https://baolaichau.vn",
        home_path="/",
        category_path_pattern="/{slug}",
        article_name="baolaichau",
        max_categories=30,
        max_articles_per_category=80,
        deny_category_prefixes=(
            "/video",
            "/multimedia",
            "/infographic",
            "/quang-cao",
            "/tags",
        ),
        deny_exact_paths=("/",),
        allowed_article_path_regexes=(r"-\d+/?$",),
        article_link_selector="a.blc-post__link[href]",
    )


def _huengaynay_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://huengaynay.vn.

    Chưa có rule đặc thù (selector/category prefix) do môi trường chạy không truy
    cập được mạng để kiểm tra cấu trúc HTML hiện tại; dùng heuristic chung và
    loại bỏ một số prefix không phải chuyên mục/bài viết.
    """

    return SiteConfig(
        key="huengaynay",
        base_url="https://huengaynay.vn",
        home_path="/",
        canonicalize_category_paths=False,
        article_name="huengaynay",
        max_categories=30,
        max_articles_per_category=80,
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".htm", ".html"),
        deny_category_prefixes=(
            "/rss",
            "/feed",
            "/video",
            "/podcast",
            "/multimedia",
            "/media",
            "/lien-he",
            "/gioi-thieu",
            "/dang-nhap",
            "/login",
            "/search",
            "/tim-kiem",
            "/tag",
            "/tags",
        ),
        deny_article_prefixes=(
            "/rss",
            "/feed",
            "/video",
            "/podcast",
            "/multimedia",
            "/media",
            "/lien-he",
            "/gioi-thieu",
            "/dang-nhap",
            "/login",
            "/search",
            "/tim-kiem",
            "/tag",
            "/tags",
        ),
    )


def _vietnamnet_config() -> SiteConfig:
    return _default_site_config("vietnamnet", "https://vietnamnet.vn")


def _vietnamplus_config() -> SiteConfig:
    return _default_site_config("vietnamplus", "https://www.vietnamplus.vn")


def _sggp_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://www.sggp.org.vn (Báo Sài Gòn Giải Phóng).

    - Category có dạng /{slug}/, chủ yếu lấy theo menu chính.
    - Bài viết chi tiết có URL đuôi "-post<id>.html".
    - Trang category hiển thị danh sách bài trong <article class="story">.
    """

    return SiteConfig(
        key="sggp",
        base_url="https://www.sggp.org.vn",
        home_path="/",
        category_path_pattern="/{slug}/",
        article_name="sggp",
        max_categories=40,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinhtri/",
            "/xaydungdang/",
            "/bvnentangtutuongdang/",
            "/caicachhanhchinh/",
            "/quoc-phong-an-ninh/",
            "/chinhtri-doingoai/",
            "/xahoi/",
            "/theodongthoisu/",
            "/sapxepcacdonvihanhchinh/",
            "/xahoi-giaothong/",
            "/xahoi-gt/",
            "/xahoi-tuoitrecuocsong/",
            "/xahoi-moitruong/",
            "/phapluat/",
            "/anninhtrattu/",
            "/tuvanphapluat/",
            "/kinhte/",
            "/thitruongkt/",
            "/xaydungdiaoc/",
            "/kinhte-taichinhchuungkhoan/",
            "/dulichkhampha/",
            "/dautukt/",
            "/kinhte-doanhnghiepdoanhnhan/",
            "/kinhtedoisong24h/",
            "/daphuongtien/",
            "/thegioi/",
            "/thegioi-tieudiem/",
            "/chinhtruongthegioi/",
            "/hosotulieu/",
            "/giaoduc/",
            "/ytesuckhoe/",
            "/ytesuckhoe-antoanthucpham/",
            "/ytesuckhoe-alobacsi/",
            "/vanhoavannghe/",
            "/nhip-song/",
            "/vanhoagiaitri-nhanvat/",
            "/dienanh/",
            "/vanhoagiaitri-sach/",
            "/nhipcaubandoc/",
            "/nhipcaubandoc-ykienbandoc/",
            "/nhipcaubandoc-diendan-thaoluan/",
            "/khoahoc-congnghe/",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-post\d+\.html$",),
        article_link_selector="article.story a[href]",
        description_selectors=("div.article__sapo",),
    )


def _baoxaydung_config() -> SiteConfig:
    return _default_site_config(
        "baoxaydung",
        "https://baoxaydung.vn",
        # Bài viết thường có đuôi "-<id>.htm"; dùng regex để bỏ qua link chuyên mục.
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(
            r"/.+-\d+\.htm$",
        ),
    )


def _hanoimoi_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://hanoimoi.vn.

    - Category có path dạng /chinh-tri, /kinh-te, /do-thi, ...
    - Bài viết chi tiết có URL dạng "slug-<id>.html".
    - Loại bỏ các trang event tổng hợp (đuôi -event<id>.html).
    """

    return SiteConfig(
        key="hanoimoi",
        base_url="https://hanoimoi.vn",
        home_path="/",
        article_name="hanoimoi",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/kinh-te",
            "/do-thi",
            "/van-hoa",
            "/xa-hoi",
            "/giao-duc",
            "/y-te",
            "/the-gioi",
            "/du-lich",
            "/nong-nghiep-nong-thon",
            "/khoa-hoc-cong-nghe",
            "/doi-song",
        ),
        deny_category_prefixes=(
            "/an-pham",
            "/tin-moi-nhat",
            "/ban-do-ha-noi",
            "/multimedia",
            "/video",
            "/emagazine",
            "/infographic",
            "/photo",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(
            r"/(?!.*-event\d+\.html$).+-\d+\.html$",
        ),
        article_link_selector="h3 a[href]",
        description_selectors=(
            "meta[name='description']",
            "meta[property='og:description']",
        ),
    )


def _baodautu_config() -> SiteConfig:
    return _default_site_config("baodautu", "https://baodautu.vn")


def _soha_config() -> SiteConfig:
    return _default_site_config("soha", "https://soha.vn")


def _vneconomy_config() -> SiteConfig:
    return SiteConfig(
        key="vneconomy",
        base_url="https://vneconomy.vn",
        home_path="/",
        article_name="vneconomy",
        deny_exact_paths=("/",),
        description_selectors=(
            "div.news-sapo",
            "[data-field='sapo']",
            "div.news-sapo[data-field='sapo'] p",
            "div.news-sapo p",
            "[data-field='sapo'] p",
            "div.news-sapo[data-field='sapo'] p b",
        ),
    )


def _baophapluat_config() -> SiteConfig:
    """
    Cấu hình cho https://baophapluat.vn (Báo Pháp luật Việt Nam).

    - Category nằm dưới /chuyen-muc/{slug}.html (một số link không có .html).
    - Bài viết chi tiết có URL dạng "/{slug}.html".
    - Link bài viết thường dùng <a class="loading-link" ...>.
    """

    return SiteConfig(
        key="baophapluat",
        base_url="https://baophapluat.vn",
        home_path="/",
        category_path_pattern="/chuyen-muc/{slug}.html",
        article_name="baophapluat",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chuyen-muc/",
        ),
        deny_category_prefixes=(
            "/chuyen-muc/media",
            "/chuyen-muc/thong-tin-quang-cao",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(
            r"^/[^/]+\.html$",
        ),
        deny_article_prefixes=(
            "/chuyen-muc/",
            "/media/",
            "/podcasts/",
            "/static/",
        ),
        article_link_selector="a.loading-link[href$='.html']",
        description_selectors=(
            "meta[name='description']",
            "meta[property='og:description']",
        ),
    )


def _vietnambiz_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://vietnambiz.vn (VietnamBiz).

    - Các chuyên mục chính có path dạng /thoi-su.htm, /tai-chinh.htm, ...
    - Bài viết chi tiết có URL đuôi ".htm" với phần cuối "-<id>.htm".
    - Trang category/home hiển thị danh sách bài trong các block với
      tiêu đề nằm trong h2.title, h3.title hoặc div.title > a[data-type='title'].
    - Nội dung sapo/tóm tắt bài chi tiết nằm trong div.vnbcbc-sapo[data-role='sapo'].
    """

    return SiteConfig(
        key="vietnambiz",
        base_url="https://vietnambiz.vn",
        home_path="/",
        category_path_pattern="/{slug}.htm",
        article_name="vietnambiz",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/du-bao",
            "/hang-hoa",
            "/quoc-te",
            "/tai-chinh",
            "/nha-dat",
            "/chung-khoan",
            "/doanh-nghiep",
            "/kinh-doanh",
        ),
        deny_category_prefixes=(
            "/emagazine",
            "/infographic",
            "/photostory",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_article_url_suffixes=(".htm",),
        description_selectors=(
            "div.vnbcbc-sapo[data-role='sapo']",
            "div.vnbcbc-sapo",
        ),
        article_link_selector=(
            "h2.title a[href], "
            "h3.title a[href], "
            "div.title > a[data-type='title']"
        ),
    )


def _baodongnai_config() -> SiteConfig:
    return SiteConfig(
        key="baodongnai",
        base_url="https://baodongnai.com.vn",
        home_path="/",
        article_name="baodongnai",
        max_categories=30,
        deny_exact_paths=("/",),
        deny_category_prefixes=(
            "/media",
            "/video-clip",
            "/podcast",
            "/anh-dep",
            "/tim-kiem",
            "/common",
            "/file",
        ),
        allowed_article_path_regexes=(
            r"/\d{6}/[a-z0-9-]+-[a-f0-9]{7}/?$",
        ),
        deny_article_prefixes=(
            "/video-clip",
            "/media/infographic",
            "/media/megastory",
            "/podcast",
            "/anh-dep",
            "/file",
            "/common",
        ),
        article_link_selector="a.title1[href], a.title3[href]",
        description_selectors=(
            "div#content.content-detail .td-post-content > p",
            "div#content.content-detail p",
        ),
    )


def _baodongthap_config() -> SiteConfig:
    """
    Cấu hình cho https://baodongthap.vn (Báo Đồng Tháp Online).

    - Category dạng /{slug}/.
    - Bài viết có đuôi ".html" với slug kết thúc "-a<id>.html".
    """

    return SiteConfig(
        key="baodongthap",
        base_url="https://baodongthap.vn",
        home_path="/",
        article_name="baodongthap",
        category_path_pattern="/{slug}/",
        max_categories=20,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/van-hoa-nghe-thuat",
            "/the-thao",
            "/giao-duc",
            "/phap-luat",
            "/suc-khoe-y-te",
            "/quoc-te",
            "/khoa-hoc",
        ),
        deny_category_prefixes=(
            "/video",
            "/podcast",
            "/longform",
            "/infographic",
            "/xem-bao",
            "/xem-albumphoto",
            "/tim-kiem",
            "/en",
            "/files",
        ),
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-a\d+\.html$",),
        deny_article_prefixes=(
            "/en/",
            "/video",
            "/podcast",
            "/longform",
            "/infographic",
            "/xem-albumphoto",
        ),
        article_link_selector="a.news-title[href], a.title[href]",
    )


def _bnews_config() -> SiteConfig:
    return _default_site_config("bnews", "https://bnews.vn")


def _dantri_config() -> SiteConfig:
    return SiteConfig(
        key="dantri",
        base_url="https://dantri.com.vn",
        home_path="/",
        article_name="dantri",
        deny_exact_paths=("/",),
        description_selectors=(
            ".singular-sapo",
            ".singular-sapo h2",
            "meta[name='description']",
        ),
    )


def _baocantho_config() -> SiteConfig:
    """
    Cấu hình cho https://baocantho.com.vn.

    - Category dạng /{slug}/, có thể có subcategory.
    - Bài viết dùng đuôi .html với slug "-a<id>.html".
    """

    return SiteConfig(
        key="baocantho",
        base_url="https://baocantho.com.vn",
        home_path="/",
        article_name="baocantho",
        category_path_pattern="/{slug}/",
        max_categories=20,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi-phap-luat",
            "/quoc-phong-an-ninh",
            "/the-gioi",
            "/giao-duc",
            "/y-te",
            "/cong-nghe",
            "/chuyen-doi-so",
            "/van-hoa-giai-tri",
            "/the-thao",
            "/du-lich",
        ),
        deny_category_prefixes=(
            "/video",
            "/xem-bao",
            "/news",
            "/khmer",
            "/bang-gia-quang-cao-bao-in",
            "/tim-kiem",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-a\d+\.html$",),
    )


def _baogialai_config() -> SiteConfig:
    """
    Cấu hình cho https://baogialai.com.vn.

    - Category dạng /{slug}/.
    - Bài viết chi tiết có URL dạng "-post<id>.html".
    """

    return SiteConfig(
        key="baogialai",
        base_url="https://baogialai.com.vn",
        home_path="/",
        article_name="baogialai",
        category_path_pattern="/{slug}/",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su-su-kien",
            "/thoi-su-quoc-te",
            "/thoi-su-binh-luan",
            "/chinh-tri",
            "/kinh-te",
            "/giao-duc",
            "/suc-khoe",
            "/van-hoa",
            "/giai-tri",
            "/doi-song",
            "/the-thao",
            "/song-tre-song-dep",
            "/khoa-hoc-cong-nghe",
            "/do-thi",
            "/du-lich",
            "/phap-luat",
            "/tu-thien",
            "/ban-doc",
            "/chuyen-nguoi-gia-lai",
            "/phong-su-ky-su",
            "/xe-may-xe-o-to",
            "/thi-truong-vang",
            "/ma-ra-thon",
            "/tennis-pickleball",
            "/xoa-nha-tam-nha-dot-nat",
            "/ban-tin-the-gioi",
            "/gia-lai-hom-nay",
            "/gia-lai-moi-tuan-mot-diem-den",
            "/diem-den-gia-lai-2022",
            "/net-zero",
            "/rung-bien-ket-noi",
            "/chuyen-dong-tre",
            "/thoi-tiet",
        ),
        deny_category_prefixes=(
            "/bao-anh",
            "/bao-in",
            "/media",
            "/multimedia",
            "/podcast",
            "/thong-tin-quang-cao",
            "/chu-de",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-post\d+\.html$",),
        article_link_selector="article a[href]",
    )


def _baothanhhoa_config() -> SiteConfig:
    """
    Cấu hình cho https://baothanhhoa.vn (Báo Thanh Hóa điện tử).

    - Category chính có path dạng /{slug}.
    - Bài viết chi tiết có URL đuôi ".htm" với slug kết thúc bằng "-<id>.htm".
    - Sapo/description thường nằm trong div.article__sapo.
    """

    return SiteConfig(
        key="baothanhhoa",
        base_url="https://baothanhhoa.vn",
        home_path="/",
        article_name="baothanhhoa",
        max_categories=40,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/tin24h",
            "/xa-phuong",
            "/thoi-su",
            "/kiem-chung-thong-tin",
            "/dai-bieu-voi-cu-tri",
            "/noi-chinh",
            "/xay-dung-dang",
            "/theo-guong-bac",
            "/nghi-quyet-cua-dang",
            "/tu-tuong-dang",
            "/du-thao",
            "/ve-voi-xu-thanh",
            "/dat-va-nguoi",
            "/khat-vong-thanh-hoa",
            "/diem-den",
            "/mien-tay-thanh-hoa",
            "/kinh-te",
            "/doanh-nghiep",
            "/co-hoi-dau-tu",
            "/kinh-te-thi-truong",
            "/hoi-nhap-quoc-te",
            "/kkt-nghi-son",
            "/sao-mai-group",
            "/xuc-tien-dau-tu",
            "/doi-song-xa-hoi",
            "/giao-duc",
            "/nguoi-tot",
            "/review-ocop",
            "/nong-thon-moi",
            "/an-toan-thuc-pham",
            "/phap-luat",
            "/anttocs",
            "/an-ninh-trat-tu",
            "/van-ban-phap-luat",
            "/the-gioi",
            "/kieu-bao",
            "/ho-so-tu-lieu",
            "/phan-tich-binh-luan",
            "/van-hoa-giai-tri",
            "/dien-anh",
            "/du-lich",
            "/nhip-song-tre",
            "/the-thao",
            "/the-thao-trong-tinh",
            "/the-thao-trong-nuoc",
            "/the-thao-quoc-te",
            "/quoc-phong-an-ninh",
            "/khoa-hoc-cong-nghe",
            "/cong-nghe-moi",
            "/moi-truong",
            "/chuyen-doi-so",
            "/y-te-suc-khoe",
            "/tu-van-suc-khoe",
            "/thuoc-dinh-duong",
            "/khoe-dep",
            "/nhung-dia-chi-tam-long",
            "/xe",
            "/thi-truong-xe",
            "/tu-van-xe",
            "/bat-dong-san-kien-truc",
            "/thi-truong",
            "/tin-tuc-dai-hoi",
            "/ddci-thanh-hoa",
        ),
        deny_category_prefixes=(
            "/short-video",
            "/truyen-hinh",
            "/bao-in",
            "/multimedia",
            "/emagazine",
            "/infographic",
            "/image",
            "/story",
            "/video",
            "/podcast",
            "/phat-thanh",
            "/doc-gia",
            "/docbao",
            "/bao-hang-thang",
        ),
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(r"-\d+\.htm$",),
        deny_article_prefixes=(
            "/video/",
            "/podcast/",
            "/short-video/",
            "/truyen-hinh/",
            "/phat-thanh/",
            "/multimedia/",
            "/emagazine/",
            "/infographic/",
            "/image/",
            "/story/",
            "/docbao/",
            "/bao-in/",
        ),
        description_selectors=(
            "div.article__sapo",
            "meta[name='description']",
            "meta[property='og:description']",
        ),
    )


def _baohatinh_config() -> SiteConfig:
    """
    Cấu hình cho https://baohatinh.vn (Báo Hà Tĩnh).

    - Category dạng /{slug}/ (có subcategory).
    - Bài viết có URL dạng "...-post<id>.html".
    - Link bài viết dùng class "cms-link".
    """

    return SiteConfig(
        key="baohatinh",
        base_url="https://baohatinh.vn",
        home_path="/",
        category_path_pattern="/{slug}/",
        article_name="baohatinh",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri/",
            "/kinh-te/",
            "/xa-hoi/",
            "/van-hoa-giai-tri/",
            "/phap-luat/",
            "/the-thao/",
            "/the-gioi/",
            "/ve-ha-tinh/",
            "/doi-song/",
            "/cong-nghe/",
            "/cong-dong/",
            "/xe/",
        ),
        deny_category_prefixes=(
            "/epaper/",
            "/multimedia/",
            "/short-video/",
            "/podcast/",
            "/video/",
            "/emagazine/",
        ),
        deny_exact_paths=(
            "/",
            "/tin-moi.html",
        ),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-post\d+\.html$",),
        article_link_selector="a.cms-link[href]",
        allowed_locales=("vi", "vi-vn"),
    )


def _baohaugiang_config() -> SiteConfig:
    """
    Cấu hình cho https://baohaugiang.com.vn (Báo Hậu Giang Online).

    - Category dạng /{slug}.html với slug có hậu tố id (ví dụ: /thoi-su-215.html).
    - Bài viết có URL dạng /{category}/{slug}-<id>.html.
    """

    return SiteConfig(
        key="baohaugiang",
        base_url="https://baohaugiang.com.vn",
        home_path="/",
        category_path_pattern="/{slug}.html",
        article_name="baohaugiang",
        max_categories=40,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/an-toan-giao-thong-",
            "/ban-doc-",
            "/bao-hiem-xa-hoi-",
            "/bien-dao-viet-nam-",
            "/chinh-tri-",
            "/chuyen-thoi-su-",
            "/cong-thuong-",
            "/cung-phong-chong-toi-pham-",
            "/doan-dai-bieu-quoc-hoi-tinh-hau-giang-",
            "/doanh-nghiep-tu-gioi-thieu-",
            "/doi-song-",
            "/du-lich-",
            "/dua-nghi-quyet-cua-dang-vao-cuoc-song-",
            "/giao-duc-",
            "/goc-suc-khoe-",
            "/hoat-dong-doan-the-",
            "/hoc-tap-va-lam-theo-tam-guong-dao-duc-ho-chi-minh-",
            "/hoi-dong-nhan-dan-tinh-hau-giang-",
            "/khoa-giao-",
            "/khoa-hoc-cong-nghe-",
            "/kinh-te-",
            "/lao-dong-viec-lam-",
            "/mat-tran-to-quoc-viet-nam-tinh-hau-giang-",
            "/moi-truong-",
            "/nong-nghiep-nong-thon-",
            "/phap-luat-",
            "/quoc-phong-an-ninh-",
            "/quoc-te-",
            "/tai-chinh-",
            "/tam-long-vang-",
            "/the-gioi-do-day-",
            "/the-thao-",
            "/the-thao-nuoc-ngoai-",
            "/the-thao-trong-nuoc-",
            "/thoi-su-",
            "/thoi-su-trong-nuoc-",
            "/thoi-su-trong-tinh-",
            "/tim-hieu-phap-luat-",
            "/tin-tuc-",
            "/van-hoa-",
            "/xa-hoi-",
            "/xay-dung-dang-chinh-quyen-",
            "/xay-dung-do-thi-",
            "/y-te-",
        ),
        deny_exact_paths=("/",),
        deny_article_prefixes=(
            "/bang-gia-quang-cao/",
            "/lien-he/",
            "/tim-kiem/",
            "/video/",
            "/multimedia/",
            "/megastory/",
            "/infographics/",
            "/anh/",
            "/podcast/",
            "/foreign-languages/",
        ),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"/[^/]+/[^/]+-\d+\.html$",),
    )


def _baohungyen_config() -> SiteConfig:
    """
    Cấu hình cho https://baohungyen.vn (Báo Hưng Yên điện tử).

    - Category dạng /{slug} (menu chính có cả dạng chữ hoa và thường).
    - Bài viết có URL dạng "...-<id>.html".
    """

    return SiteConfig(
        key="baohungyen",
        base_url="https://baohungyen.vn",
        home_path="/",
        category_path_pattern="/{slug}",
        article_name="baohungyen",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/Chinh-tri",
            "/kinh-te",
            "/Kinh-te",
            "/xa-hoi",
            "/Xa-hoi",
            "/van-hoa",
            "/Van-hoa",
            "/the-thao",
            "/The-thao",
            "/an-ninh-quoc-phong",
            "/quoc-te",
            "/giao-duc",
            "/Giao-duc",
            "/dat-va-nguoi-hung-yen",
            "/ban-doc",
            "/Ban-doc",
            "/doi-song",
            "/phap-luat-doi-song",
            "/bien-dao-Viet-Nam",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-\d+\.html$",),
    )


def _baonghean_config() -> SiteConfig:
    """
    Cấu hình cho https://baonghean.vn (Báo Nghệ An điện tử).

    - Category dạng /{slug} và có subcategory.
    - Bài viết thường có URL kết thúc bằng -<id>.html hoặc -event<id>.html.
    - Link bài viết trong trang category thường nằm trong .b-grid__title/.b-grid__img.
    """

    return SiteConfig(
        key="baonghean",
        base_url="https://baonghean.vn",
        home_path="/",
        article_name="baonghean",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/kinh-te",
            "/xa-hoi",
            "/the-thao",
            "/suc-khoe",
            "/phap-luat",
            "/quoc-te",
            "/xay-dung-dang",
            "/giao-duc",
            "/giai-tri",
            "/ket-noi-doanh-nghiep",
            "/lao-dong",
        ),
        deny_category_prefixes=(
            "/video",
            "/short-video",
            "/photo",
            "/podcast",
            "/emagazine",
            "/an-pham",
            "/tin-moi-nhat",
            "/thoi-tiet",
            "/lich-am-duong-hom-nay",
            "/cdn-cgi",
            "/assets",
            "/en",
            "/fr",
            "/ru",
            "/cn",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(
            r"-\d+\.html$",
            r"-event\d+\.html$",
        ),
        deny_article_prefixes=(
            "/video",
            "/short-video",
            "/photo",
            "/podcast",
            "/emagazine",
            "/an-pham",
        ),
        article_link_selector=".b-grid__title a[href], .b-grid__img a[href]",
        description_selectors=(
            ".sc-longform-header-sapo",
            "meta[name='description']",
        ),
        allowed_locales=("vi", "vi-vn"),
    )


def _baothainguyen_config() -> SiteConfig:
    """
    Cấu hình cho https://baothainguyen.vn (Báo Thái Nguyên điện tử).

    - Category dạng /{slug}/ trên menu chính.
    - Bài viết có URL dạng /{category}/{YYYYMM}/{slug}-{id}/.
    - Link bài viết trong trang category dùng class "title2".
    """

    return SiteConfig(
        key="baothainguyen",
        base_url="https://baothainguyen.vn",
        home_path="/",
        article_name="baothainguyen",
        category_path_pattern="/{slug}/",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su-thai-nguyen",
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/phap-luat",
            "/giao-duc",
            "/y-te",
            "/van-hoa",
            "/van-nghe-thai-nguyen",
            "/the-thao",
            "/giao-thong",
            "/o-to-xe-may",
            "/tai-nguyen-moi-truong",
            "/quoc-phong-an-ninh",
            "/quoc-te",
            "/que-huong-dat-nuoc",
            "/ban-doc",
            "/tieu-diem",
            "/tin-moi",
            "/thong-tin-can-biet",
        ),
        deny_category_prefixes=(
            "/audio",
            "/audio-bao-thai-nguyen",
            "/audio-thai-nguyen",
            "/multimedia",
            "/podcast",
            "/video",
            "/doc-bao-in",
            "/tim-kiem",
            "/thong-tin-quang-cao",
        ),
        deny_exact_paths=("/",),
        allowed_article_path_regexes=(
            r"/\d{6}/[^/]+/?$",
        ),
        deny_article_prefixes=(
            "/audio",
            "/audio-bao-thai-nguyen",
            "/audio-thai-nguyen",
            "/multimedia",
            "/podcast",
            "/video",
            "/doc-bao-in",
        ),
        article_link_selector="a.title2[href]",
        description_selectors=("div.desc",),
    )


def _baodaklak_config() -> SiteConfig:
    """
    Cấu hình cho https://baodaklak.vn (Báo Đắk Lắk điện tử).

    - Category dạng /{slug}/, có thể có subcategory.
    - Bài viết thường có URL dạng /{category}/{YYYYMM}/{slug}/.
    """

    return SiteConfig(
        key="baodaklak",
        base_url="https://baodaklak.vn",
        home_path="/",
        article_name="baodaklak",
        category_path_pattern="/{slug}/",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/giao-duc",
            "/y-te-suc-khoe",
            "/chinh-sach-xa-hoi",
            "/phap-luat",
            "/an-ninh-quoc-phong",
            "/quoc-te",
            "/the-thao",
            "/van-hoa-du-lich-van-hoc-nghe-thuat",
            "/du-lich",
            "/khoa-hoc-cong-nghe",
            "/moi-truong",
            "/trang-tin-dia-phuong",
            "/thong-tin-doanh-nghiep-tu-gioi-thieu",
            "/phong-su-ky-su",
            "/van-de-ban-doc-quan-tam",
        ),
        deny_category_prefixes=(
            "/multimedia",
            "/video",
            "/doc-bao-in",
            "/tim-kiem",
        ),
        deny_exact_paths=("/",),
        allowed_article_path_regexes=(
            r"/\d{6}/[^/]+/?$",
        ),
        deny_article_prefixes=(
            "/multimedia",
            "/video",
            "/doc-bao-in",
            "/tim-kiem",
        ),
        article_link_selector="a.title5[href]",
    )


def _baosonla_config() -> SiteConfig:
    """
    Cấu hình cho https://baosonla.vn (Báo Sơn La điện tử).

    - Category chủ yếu có dạng /{slug}.html theo menu chính.
    - Bài viết có dạng /{category}/{slug}-{id}.html.
    - Sapo/description ưu tiên lấy từ meta description.
    - Link bài viết thường dùng class "cms-link".
    """

    return SiteConfig(
        key="baosonla",
        base_url="https://baosonla.vn",
        home_path="/",
        category_path_pattern="/{slug}.html",
        article_name="baosonla",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su-chinh-tri",
            "/xay-dung-dang",
            "/bao-ve-nen-tang-tu-tuong-cua-dang",
            "/phong-chong-tham-nhung",
            "/kinh-te",
            "/nong-nghiep",
            "/cong-nghiep-ttcn",
            "/thuong-mai-dich-vu",
            "/van-hoa-xa-hoi",
            "/xa-hoi",
            "/khoa-giao",
            "/suc-khoe",
            "/an-toan-giao-thong",
            "/the-thao",
            "/ban-can-biet",
            "/quoc-phong-an-ninh",
            "/quoc-phong",
            "/an-ninh-trat-tu",
            "/doi-ngoai",
            "/quoc-te",
            "/du-lich",
            "/nong-thon-moi",
            "/dien-dan-cu-tri",
            "/phong-su",
            "/phap-luat",
            "/cai-cach-hanh-chinh",
        ),
        deny_category_prefixes=(
            "/emagazine",
            "/thong-tin-quang-cao",
            "/bao-in",
            "/trang-dia-phuong",
            "/lien-he",
            "/video",
        ),
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"^/[^/]+/.+\.html$",),
        deny_article_prefixes=(
            "/emagazine",
            "/thong-tin-quang-cao",
            "/video",
        ),
        article_link_selector="a.cms-link[href$='.html']",
        description_selectors=(
            "meta[name='description']",
            "meta[property='og:description']",
        ),
    )


def _baodienbienphu_config() -> SiteConfig:
    """
    Cấu hình cho https://baodienbienphu.vn.

    - Bài viết có path dạng /tin-bai/{category}/{slug}.
    - Trang chủ có link bài viết, nhưng trang chuyên mục render client-side,
      nên dùng trang chủ làm nguồn thu thập bài.
    """

    return SiteConfig(
        key="baodienbienphu",
        base_url="https://baodienbienphu.vn",
        home_path="/",
        article_name="baodienbienphu",
        category_path_pattern="/tin-tuc/{slug}",
        max_categories=20,
        max_articles_per_category=12,
        article_link_selector="a[href*='/tin-bai/']",
        allowed_article_path_regexes=(
            r"^/tin-bai/[^/]+/[^/]+/?$",
        ),
    )


def _baocaobang_config() -> SiteConfig:
    """
    Cấu hình cho https://baocaobang.vn (Báo Cao Bằng điện tử).

    - Category chính trên menu có dạng /Thoi-su, /chinh-tri, ...
    - Bài viết chi tiết có URL đuôi ".html" với slug kết thúc bằng "-<id>.html".
    """

    return SiteConfig(
        key="baocaobang",
        base_url="https://baocaobang.vn",
        home_path="/",
        article_name="baocaobang",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/Thoi-su",
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/van-hoa",
            "/the-thao",
            "/Khoa-hoc-Cong-nghe",
            "/Quoc-phong-An-ninh",
            "/Suc-khoe-Doi-song",
            "/The-gioi",
            "/Giao-duc",
            "/Ky-Phong-su",
        ),
        deny_category_prefixes=(
            "/Truyenhinh-Internet",
            "/Thong-tin-Toa-soan",
            "/Phongsuanh",
            "/Du-bao-thoi-tiet-Cao-Bang",
            "/tin-noi-bat",
            "/tin-tieu-diem",
            "/multimedia",
            "/search",
            "/tags",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-\d+\.html$",),
        article_link_selector="article a[href], h3 a[href], h2 a[href], .card-title a[href]",
    )


def _baobinhduong_config() -> SiteConfig:
    """
    Cấu hình cho https://baobinhduong.vn.

    - Category chính có path dạng /chinh-tri, /kinh-te, ...
    - Bài viết có URL đuôi .html với slug "-a<id>.html".
    - Danh sách bài trong category dùng block .article-item và tiêu đề h3 > a.
    """

    return SiteConfig(
        key="baobinhduong",
        base_url="https://baobinhduong.vn",
        home_path="/",
        article_name="baobinhduong",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/the-thao",
            "/giao-duc",
            "/phap-luat",
            "/y-te",
            "/nhip-song-so",
            "/phan-tich",
            "/ban-doc",
            "/du-lich",
            "/quoc-te",
            "/toi-yeu-binh-duong",
        ),
        deny_category_prefixes=(
            "/video",
            "/podcast",
            "/infographic",
            "/longform",
            "/xem-albumphoto",
            "/xem-bao",
            "/en",
            "/cn",
            "/tim-kiem",
            "/su-kien",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-a\d+\.html$",),
        article_link_selector=".article-item a[href], h3 a[href], h2 a[href]",
    )


def _baotayninh_config() -> SiteConfig:
    """
    Cấu hình cho https://www.baotayninh.vn (Báo Tây Ninh Online).

    - Category dạng /{slug}/, có thể có subcategory.
    - Bài viết có URL đuôi ".html" với slug "-a<id>.html".
    - Sapo thường nằm trong h4.sapo.
    - Link bài trong trang category dùng thẻ a.title.
    """

    return SiteConfig(
        key="baotayninh",
        base_url="https://www.baotayninh.vn",
        home_path="/",
        category_path_pattern="/{slug}/",
        article_name="baotayninh",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su-chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/phap-luat",
            "/quoc-te",
            "/van-hoa-giai-tri",
            "/the-thao",
            "/cong-nghe",
            "/y-te-suc-khoe",
            "/dia-phuong",
            "/trong-tinh",
            "/su-kien",
        ),
        deny_category_prefixes=(
            "/video",
            "/audio",
            "/longform",
            "/image",
            "/xem-bao",
        ),
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-a\d+\.html$",),
        deny_article_prefixes=(
            "/longform",
            "/video",
            "/audio",
            "/image",
            "/xem-bao",
            "/albumphoto",
        ),
        article_link_selector="a.title[href]",
        description_selectors=(
            "h4.sapo",
            "p.sapo",
        ),
    )


def _baobacninhtv_config() -> SiteConfig:
    """
    Cấu hình cho https://baobacninhtv.vn (Báo Bắc Ninh).

    - Category dạng /{slug}.
    - Bài viết có URL đuôi .bbg với pattern "-postid<id>.bbg".
    - Sapo trong div.news_detail_sapo.
    """

    return SiteConfig(
        key="baobacninhtv",
        base_url="https://baobacninhtv.vn",
        home_path="/",
        article_name="baobacninhtv",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/xay-dung-dang",
            "/chinh-tri-bao-ve-nen-tang-tu-tuong-cua-dang",
            "/chinh-tri-nhan-su-moi",
            "/kinh-te",
            "/xa-hoi",
            "/doi-song",
            "/phap-luat",
            "/an-toan-giao-thong",
            "/suc-khoe",
            "/giao-duc",
            "/quoc-phong",
            "/the-gioi",
            "/the-thao",
            "/the-thao-nhat-ky-sea-games-33",
            "/nhip-song-tre",
            "/nhip-song-tre-guong-mat",
            "/nhip-song-tre-thanh-nien-cong-nhan",
            "/dat-va-nguoi-bac-ninh",
            "/van-hoa-goc-cho-nguoi-yeu-tho",
            "/van-hoa-tac-gia-tac-pham",
            "/phong-tuc-tap-quan",
            "/sukien",
            "/mon-ngon",
            "/bacgiang-van-hoa",
            "/moi-nhat",
        ),
        deny_category_prefixes=(
            "/multimedia",
            "/podcast",
            "/photo",
            "/videos",
            "/infographics",
            "/thong-tin-quang-cao",
            "/bacgiang-emagazine",
            "/bg2",
            "/bando",
        ),
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".bbg",),
        allowed_article_path_regexes=(r"-postid\d+\.bbg$",),
        deny_article_prefixes=(
            "/bg/infographics",
            "/photo",
            "/videos",
            "/podcast",
        ),
        article_link_selector="a.font-tin-doc[href]",
        description_selectors=(
            "div.news_detail_sapo p",
            "div.news_detail_sapo",
        ),
    )


def _baoquangninh_config() -> SiteConfig:
    """
    Cấu hình cho https://baoquangninh.vn (Báo Quảng Ninh điện tử).

    - Category dạng /{slug} và có các chuyên mục chính trên menu.
    - Bài viết có URL kết thúc bằng "-<id>.html".
    """

    return SiteConfig(
        key="baoquangninh",
        base_url="https://baoquangninh.vn",
        home_path="/",
        article_name="baoquangninh",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/phap-luat",
            "/the-thao",
            "/du-lich",
            "/van-hoa",
            "/quoc-te",
            "/doi-song",
            "/khoa-hoc-cong-nghe",
            "/ban-doc",
            "/multimedia",
            "/truyen-hinh",
            "/phat-thanh",
        ),
        deny_category_prefixes=(
            "/intro",
            "/users",
            "/thong-tin-quang-cao",
        ),
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-\d+\.html$",),
        article_link_selector="article.card a[href], .card-content a[href]",
    )


def _baoquangngai_config() -> SiteConfig:
    """
    Cấu hình cho https://baoquangngai.vn (Báo Quảng Ngãi điện tử).

    - Category chính có path dạng /chinh-tri, /thoi-su, /kinh-te, ...
    - Bài viết có URL đuôi ".htm" với slug kết thúc bằng "-<id>.htm".
    - Trang category liệt kê bài trong các thẻ article.
    """

    return SiteConfig(
        key="baoquangngai",
        base_url="https://baoquangngai.vn",
        home_path="/",
        article_name="baoquangngai",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/thoi-su",
            "/kinh-te",
            "/xa-hoi",
            "/du-lich",
            "/doi-song",
            "/van-hoa-nghe-thuat",
            "/the-thao",
            "/khoa-hoc-cong-nghe",
            "/phap-luat",
            "/quoc-te",
            "/phong-su",
            "/phong-van-doi-thoai",
            "/quang-ngai-que-minh",
            "/nhin-ra-tinh-ban",
            "/hoat-dong-cua-lanh-dao-tinh",
            "/chuyen-de-chuyen-sau",
            "/thong-tin-can-biet",
        ),
        deny_category_prefixes=(
            "/multimedia",
            "/bao-in",
            "/tin-moi-nhat",
            "/tet-online",
            "/o-to-xe-may",
            "/ban-do-quang-ngai",
            "/@baoquangngai.vn",
        ),
        deny_exact_paths=("/",),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(r"-\d+\.htm$",),
        deny_article_prefixes=(
            "/bao-in",
            "/event",
            "/expert",
            "/multimedia",
            "/tin-moi-nhat",
            "/tet-online",
            "/o-to-xe-may",
            "/ban-do-quang-ngai",
        ),
        article_link_selector="article a[href$='.htm']",
        description_selectors=(
            "p.sapo",
            "#body .sapo",
        ),
    )


def _baoquangtri_config() -> SiteConfig:
    """
    Cấu hình cho https://baoquangtri.vn (Báo và phát thanh, truyền hình Quảng Trị).

    - Category dạng /{slug}/, có thể có subcategory.
    - Bài viết thường có URL dạng /{category}/{YYYYMM}/{slug}-{id}/.
    """

    return SiteConfig(
        key="baoquangtri",
        base_url="https://baoquangtri.vn",
        home_path="/",
        article_name="baoquangtri",
        category_path_pattern="/{slug}/",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri/",
            "/dat-va-nguoi-quang-binh/",
            "/dat-va-nguoi-quang-tri/",
            "/du-lich/",
            "/giao-duc/",
            "/khoa-hoc-cong-nghe/",
            "/kinh-te/",
            "/multimedia/",
            "/phap-luat/",
            "/phong-su-ky-su/",
            "/quoc-phong-an-ninh/",
            "/quoc-te/",
            "/suc-khoe/",
            "/the-thao/",
            "/thoi-su/",
            "/toa-soan-ban-doc/",
            "/van-hoa/",
            "/xa-hoi/",
            "/moi-nong/",
        ),
        deny_category_prefixes=(
            "/doc-bao-in/",
            "/thong-tin-quang-cao-tuyen-dung/",
        ),
        deny_exact_paths=("/",),
        allowed_article_path_regexes=(
            r"^/[a-z0-9-]+(?:/[a-z0-9-]+)?/\d{6}/[a-z0-9-]+-[0-9a-f]+/?$",
        ),
        deny_article_prefixes=(
            "/doc-bao-in/",
            "/thong-tin-quang-cao-tuyen-dung/",
        ),
        article_link_selector="a.h2[href], a.h3[href], a.card-img[href]",
    )


def _baocamau_config() -> SiteConfig:
    return _default_site_config(
        "baocamau",
        "https://baocamau.vn",
        allowed_article_url_suffixes=(".html",),
    )


def _baodongkhoi_config() -> SiteConfig:
    """
    Cấu hình cho https://baodongkhoi.vn.

    Trang baodongkhoi.vn render nội dung với base href trỏ về
    dongkhoi.baovinhlong.vn, nên dùng host này để thu thập link bài viết.
    """

    return SiteConfig(
        key="baodongkhoi",
        base_url="https://dongkhoi.baovinhlong.vn",
        home_path="/",
        article_name="baodongkhoi",
        max_categories=20,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/chinh-tri",
            "/kinh-te",
            "/phap-luat",
            "/xa-hoi",
            "/van-hoa",
            "/khoa-giao",
            "/the-thao",
            "/quoc-phong",
            "/an-ninh",
            "/ban-doc",
            "/quoc-te",
        ),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-a\d+\.html$",),
        deny_article_prefixes=(
            "/https/",
        ),
    )


def _dongkhoi_baovinhlong_config() -> SiteConfig:
    """
    Cấu hình cho https://dongkhoi.baovinhlong.vn.

    - Category dạng /{slug}/ (có trailing slash).
    - Bài viết có URL kết thúc bằng "-a<id>.html".
    """

    return SiteConfig(
        key="dongkhoi_baovinhlong",
        base_url="https://dongkhoi.baovinhlong.vn",
        home_path="/",
        article_name="dongkhoi_baovinhlong",
        category_path_pattern="/{slug}/",
        max_categories=20,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/thoi-su",
            "/chinh-tri",
            "/kinh-te",
            "/phap-luat",
            "/xa-hoi",
            "/van-hoa",
            "/khoa-giao",
            "/the-thao",
            "/quoc-phong",
            "/an-ninh",
            "/ban-doc",
            "/quoc-te",
        ),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"-a\d+\.html$",),
    )


def _znews_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://znews.vn (Zing News).

    - Các chuyên mục chính có path dạng /xuat-ban.html, /kinh-doanh-tai-chinh.html, ...
    - Bài viết chi tiết có URL đuôi ".html" với slug "-post<id>.html".
    - Trang category và trang chủ hiển thị danh sách bài trong
      <article class="article-item"> với tiêu đề trong h3.article-title > a.
    - Nội dung bài chi tiết dùng phần tóm tắt trong p.the-article-summary.
    """

    return SiteConfig(
        key="znews",
        base_url="https://znews.vn",
        home_path="/",
        article_name="znews",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/xuat-ban",
            "/kinh-doanh-tai-chinh",
            "/suc-khoe",
            "/the-thao",
            "/doi-song",
            "/cong-nghe",
            "/giai-tri",
            "/sach-hay",
            "/du-lich",
            "/oto-xe-may",
            "/cuon-sach-toi-doc",
            "/van-hoa-doc",
            "/xa-hoi",
            "/phap-luat",
            "/the-gioi",
            "/giao-duc",
        ),
        deny_category_prefixes=(
            "/video",
            "/series",
            "/tieu-diem",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_article_url_suffixes=(".html",),
        # Danh sách bài trên category/home: <article class="article-item"> với
        # tiêu đề trong h3.article-title > a.
        article_link_selector="article.article-item h3.article-title a[href]",
        # Tóm tắt bài chi tiết: <p class="the-article-summary">...</p>
        description_selectors=(
            "p.the-article-summary",
        ),
    )


def _vov_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://vov.vn (Báo điện tử VOV).

    Tạm thời sử dụng cấu hình mặc định, dựa vào heuristic chung để:
    - phát hiện category từ các link nội bộ trên trang chủ,
    - phát hiện link bài viết trong trang category.
    Nếu cần tối ưu thêm (selector description, danh sách category cụ thể, ...),
    có thể tinh chỉnh cấu hình này sau khi đã thu thập được dữ liệu mẫu.
    """

    return SiteConfig(
        key="vov",
        base_url="https://vov.vn",
        home_path="/",
        article_name="vov",
        deny_exact_paths=("/",),
    )


def _baohaiphong_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://baohaiphong.vn.

    - Category chính có path dạng /chinh-tri, /kinh-te, /xa-hoi, ...
    - Bài viết chi tiết có URL đuôi .html (slug-id.html).
    - Danh sách bài trong category thường dùng thẻ h3 > a.
    """

    return SiteConfig(
        key="baohaiphong",
        base_url="https://baohaiphong.vn",
        home_path="/",
        article_name="baohaiphong",
        max_categories=40,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/kinh-te",
            "/xa-hoi",
            "/goc-nhin",
            "/khoa-hoc-giao-duc",
            "/phap-luat",
            "/bat-dong-san",
            "/van-hoa-giai-tri",
            "/van-nghe",
            "/quoc-te",
            "/the-thao",
            "/doi-song",
            "/dat-va-nguoi-xu-dong",
            "/ban-doc",
            "/du-lich",
            "/su-kien-qua-anh",
            "/xe",
        ),
        deny_category_prefixes=(
            "/video",
            "/emagazine",
            "/podcast",
            "/infographic",
            "/thong-tin-quang-cao",
            "/an-pham",
            "/thoi-tiet-hai-phong",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        deny_article_prefixes=(
            "/an-pham",
            "/video",
            "/podcast",
            "/emagazine",
            "/infographic",
            "/thong-tin-quang-cao",
        ),
        article_link_selector="h3 a[href]",
        description_selectors=(
            "p.sc-longform-header-sapo",
            "p.block-sc-sapo",
            ".sc-longform-header-sapo",
        ),
    )


def _baodanang_config() -> SiteConfig:
    """
    Cấu hình cơ bản cho https://baodanang.vn.

    - Category chính có path dạng /chinh-tri, /xa-hoi, /kinh-te, ...
    - Bài viết thường có URL đuôi .html (không nằm trong thư mục category).
    - Danh sách bài trong category dùng thẻ h3.b-grid__title > a.
    """

    return SiteConfig(
        key="baodanang",
        base_url="https://baodanang.vn",
        home_path="/",
        article_name="baodanang",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/xa-hoi",
            "/kinh-te",
            "/nong-nghiep-nong-thon",
            "/quoc-phong-an-ninh",
            "/the-gioi",
            "/the-thao",
            "/van-hoa-van-nghe",
            "/doi-song",
            "/du-lich",
            "/khoa-hoc-cong-nghe",
            "/su-kien-binh-luan",
            "/co-hoi-dau-tu",
            "/theo-buoc-chan-nguoi-quang",
            "/toa-soan-ban-doc",
            "/tin-moi-nhat",
        ),
        deny_category_prefixes=(
            "/media",
            "/podcast",
            "/truyen-hinh",
            "/quang-cao-rao-vat",
            "/am-duong-lich-hom-nay",
        ),
        deny_exact_paths=("/",),
        allowed_article_url_suffixes=(".html",),
        article_link_selector="h3.b-grid__title a[href]",
    )


def _bocongan_config() -> SiteConfig:
    """
    Cấu hình cho https://bocongan.gov.vn (Cổng Thông tin điện tử Bộ Công an).

    - Category chính có path dạng /chuyen-muc/<slug>.
    - Bài viết chi tiết có URL dạng /bai-viet/<slug>-<id>.
    - Sapo/description nằm trong đoạn văn có class text-bca-gray-700.
    """

    return SiteConfig(
        key="bocongan",
        base_url="https://bocongan.gov.vn",
        home_path="/",
        category_path_pattern="/chuyen-muc/{slug}",
        article_name="bocongan",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chuyen-muc",
        ),
        deny_category_prefixes=(
            "/gioi-thieu",
            "/albums",
            "/videos",
            "/podcast",
            "/longform",
            "/e-magazine",
            "/infographic",
            "/hoi-dap",
            "/truyen-thong",
            "/chinh-sach-phap-luat",
            "/interpol",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_article_path_regexes=(
            r"^/bai-viet/.+-\d+/?$",
        ),
        article_link_selector="a[href^='/bai-viet/']",
        description_selectors=(
            "p.text-justify.mb-\\[22px\\].text-bca-gray-700.font-medium.lg\\:text-\\[20px\\]",
            "p.text-justify.text-bca-gray-700.font-medium",
            "p.text-bca-gray-700",
        ),
    )


def _cand_config() -> SiteConfig:
    """
    Cấu hình cho https://cand.com.vn (Báo Công an nhân dân).

    - Category dạng /{slug}/.
    - Bài viết có URL kết thúc bằng "-i<id>/".
    """

    return SiteConfig(
        key="cand",
        base_url="https://cand.com.vn",
        home_path="/",
        category_path_pattern="/{slug}/",
        article_name="cand",
        max_categories=40,
        max_articles_per_category=80,
        deny_category_prefixes=(
            "/topic",
            "/rssfeed",
            "/eMagazine",
            "/emagazine",
            "/video",
            "/Video",
            "/clip",
            "/Clip",
            "/search",
            "/tags",
            "/tag",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_path_regexes=(r"-i\d+/?$",),
        article_link_selector=".box-title a[href]",
        description_selectors=(
            "div.box-des-detail",
        ),
    )


def _modgov_config() -> SiteConfig:
    """
    Cấu hình cho https://mod.gov.vn (Cổng TTĐT Bộ Quốc phòng).

    - Category dùng dạng /home/news?... với query param urile=wcm:path:...
    - Bài viết chi tiết dùng /home/detail?... với query param urile=wcm:path:...
    """

    return SiteConfig(
        key="modgov",
        base_url="https://mod.gov.vn",
        home_path="/home",
        article_name="modgov",
        max_categories=20,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/home/news",
            "/home/news/td",
            "/home/news/event",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_article_path_regexes=(r"^/home/detail$",),
        keep_query_params=True,
    )


def _vpcp_config() -> SiteConfig:
    """
    Cấu hình cho https://vpcp.chinhphu.vn (Website Văn phòng Chính phủ).

    Ghi chú:
    - Category/listing thường là các trang *.htm (vd: /thong-tin-hoat-dong.htm).
    - Bài viết chi tiết thường có hậu tố dạng "-<digits>.htm" (vd: ...-115260....htm).
    - Trang có chuyên mục /video nên loại bỏ khỏi tập URL bài viết.
    """

    return SiteConfig(
        key="vpcp",
        base_url="https://vpcp.chinhphu.vn",
        home_path="/",
        canonicalize_category_paths=False,
        article_name="vpcp",
        max_categories=10,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/tin-noi-bat.htm",
            "/thong-tin-hoat-dong.htm",
            "/cong-tac-dang-doan-the.htm",
            "/cong-ttdt-chinh-phu/",
            "/cac-chuyen-muc-dac-biet/",
        ),
        deny_category_prefixes=(
            "/video",
            "/anh",
            "/owa",
        ),
        deny_exact_paths=(
            "/",
        ),
        deny_category_path_regexes=(
            r"^/.+-\d{8,}\.htm$",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(
            r"-\d{8,}\.htm$",
        ),
        deny_article_prefixes=(
            "/video",
            "/anh",
        ),
        article_link_selector="a.box-stream-link-title[href], a.box-focus-link-title[href]",
        delay_seconds=0.8,
    )


def _mofa_config() -> SiteConfig:
    """
    Cấu hình cho https://mofa.gov.vn (Cổng thông tin Bộ Ngoại Giao).

    - Category chủ yếu có path dạng /tin-..., /hoat-dong-...
    - Bài viết chi tiết dùng path /tin-chi-tiet/chi-tiet/<slug>-<id>-<cat>.html.
    """

    return SiteConfig(
        key="mofa",
        base_url="https://mofa.gov.vn",
        home_path="/",
        article_name="mofa",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/tin-",
            "/hoat-dong-",
        ),
        deny_category_prefixes=(
            "/tin-chi-tiet",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_path_regexes=(
            r"^/tin-chi-tiet/chi-tiet/.+-\d+(?:-\d+)?\.html$",
        ),
        article_link_selector="a[href*='/tin-chi-tiet/chi-tiet/']",
        description_selectors=(
            "div.article-summary",
        ),
    )


def _mof_config() -> SiteConfig:
    """
    Cấu hình cho https://www.mof.gov.vn (Cổng thông tin Bộ Tài chính).

    - Trang sử dụng SPA, danh sách bài lấy qua API nội bộ.
    - URL bài viết dùng pattern /{rootSlug}/{categorySlug}/{articleSlug}.
    """

    return SiteConfig(
        key="mof",
        base_url="https://www.mof.gov.vn",
        home_path="/",
        article_name="mof",
        max_categories=1,
        max_articles_per_category=80,
        allowed_locales=("vi", "vi-vn"),
    )


def _moh_config() -> SiteConfig:
    """
    Cấu hình cho https://moh.gov.vn (Cổng thông tin điện tử Bộ Y tế).

    Ghi chú:
    - Trang (thường) dùng Liferay, category nằm dưới prefix /web/guest/<slug>.
    - Bài viết chi tiết thường có path chứa "/-/" hoặc đuôi .html/.htm/.aspx.
    - Category mặc định được ép về "yte" theo yêu cầu phân loại downstream.
    """

    return SiteConfig(
        key="moh",
        base_url="https://moh.gov.vn",
        home_path="/",
        category_path_pattern="/web/guest/{slug}",
        canonicalize_category_paths=False,
        article_name="moh",
        forced_category_id="yte",
        forced_category_name="yte",
        max_categories=30,
        max_articles_per_category=80,
        max_retries=5,
        retry_backoff=1.5,
        allow_category_prefixes=(),
        deny_exact_paths=(
            "/",
        ),
        # Tránh lấy nhầm link bài viết (có đuôi .html/.htm/.aspx) làm category.
        deny_category_path_regexes=(
            r"^/.+\\.(?:html|htm|aspx)$",
            r"/-/",
        ),
        deny_category_prefixes=(
            "/sitemap",
            "/rss",
            "/search",
            "/tim-kiem",
            "/web/guest/-",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_path_regexes=(
            r"^/web/guest/-/",
            r"\\.html$",
            r"\\.htm$",
            r"\\.aspx$",
            r"/-/",
        ),
        article_link_selector="a[href*='/web/guest/-/'], a[href*='/-/'], a[href$='.html'], a[href$='.htm'], a[href$='.aspx']",
        delay_seconds=1.0,
        request_headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        # moh.gov.vn hiện trả về handshake với DH key nhỏ, OpenSSL 3 mặc định từ chối.
        allow_weak_dh_ssl=True,
    )


def _thanhtra_config() -> SiteConfig:
    """
    Cấu hình cho https://thanhtra.gov.vn (Cổng TTĐT Thanh tra Chính phủ).

    Ghi chú:
    - Site dùng Liferay, category nằm dưới prefix /web/guest/<slug>.
    - Link bài viết chi tiết có dạng:
      /web/guest/xem-chi-tiet-tin-tuc/-/asset_publisher//Content/<slug>?<id>
      (query dạng "?<id>" là bắt buộc để server render đúng nội dung).
    """

    return SiteConfig(
        key="thanhtra",
        base_url="https://thanhtra.gov.vn",
        home_path="/",
        category_path_pattern="/web/guest/{slug}",
        article_name="thanhtra",
        max_categories=20,
        max_articles_per_category=80,
        keep_query_params=True,
        allow_category_prefixes=(
            "/web/guest/thanh-tra",
            "/web/guest/khieu-nai-to-cao",
            "/web/guest/phong-chong-tham-nhung",
            "/web/guest/tin-tong-hop",
            "/web/guest/thong-bao",
            "/web/guest/tin-hinh-anh",
        ),
        deny_category_prefixes=(
            "/web/guest/xem-chi-tiet-tin-tuc",
            "/web/guest/trang-chu",
            "/web/guest/tim-kiem",
        ),
        deny_exact_paths=(
            "/",
            "/web/guest",
            "/web/guest/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_path_regexes=(
            r"^/web/guest/xem-chi-tiet-tin-tuc/-/asset_publisher/+[Cc]ontent/.+",
        ),
        # Tránh lấy nhầm trang giới thiệu lẫn trong menu.
        deny_article_prefixes=(
            "/web/guest/xem-chi-tiet-tin-tuc/-/asset_publisher/Content/chuc-nang-nhiem",
            "/web/guest/xem-chi-tiet-tin-tuc/-/asset_publisher//Content/chuc-nang-nhiem",
        ),
        article_link_selector=(
            "a[href*='/xem-chi-tiet-tin-tuc/-/asset_publisher']"
            "[href*='Content'][href*='?']"
        ),
    )


def _moit_config() -> SiteConfig:
    """
    Cấu hình cho https://moit.gov.vn (Cổng thông tin điện tử Bộ Công Thương).

    - Category chính nằm dưới /tin-tuc/<slug>.
    - Bài viết chi tiết có URL đuôi ".html" dưới /tin-tuc/.
    """

    return SiteConfig(
        key="moit",
        base_url="https://moit.gov.vn",
        home_path="/",
        category_path_pattern="/tin-tuc/{slug}",
        article_name="moit",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/tin-tuc",
        ),
        deny_exact_paths=(
            "/",
            "/tin-tuc",
            "/tin-tuc/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"^/tin-tuc/.+\.html$",),
        article_link_selector="a[href*='/tin-tuc/'][href$='.html']",
        description_selectors=(
            "div.article-brief",
            "meta[name='description']",
            "meta[property='og:description']",
        ),
    )


def _moet_config() -> SiteConfig:
    """
    Cấu hình cho https://moet.gov.vn (Cổng thông tin Bộ Giáo dục và Đào tạo).

    - Category chính nằm dưới /tin-tuc/<slug>.
    - Bài viết chi tiết có URL đuôi ".html" dưới /tin-tuc/.
    """

    return SiteConfig(
        key="moet",
        base_url="https://moet.gov.vn",
        home_path="/",
        category_path_pattern="/tin-tuc/{slug}",
        article_name="moet",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/tin-tuc",
        ),
        deny_category_prefixes=(
            "/tin-tuc/tin-video",
        ),
        deny_exact_paths=(
            "/",
            "/tin-tuc",
            "/tin-tuc/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".html",),
        allowed_article_path_regexes=(r"^/tin-tuc/.+\.html$",),
        article_link_selector="a[href*='/tin-tuc/'][href*='.html']",
        description_selectors=(
            "meta[name='description']",
            "meta[property='og:description']",
        ),
    )


def _mst_config() -> SiteConfig:
    """
    Cấu hình cho https://mst.gov.vn (Cổng thông tin điện tử Bộ Khoa học và Công nghệ).

    - Category dạng /tin-tuc-su-kien[/<slug>].htm.
    - Bài viết chi tiết thường kết thúc bằng "-<digits>.htm".
    """

    return SiteConfig(
        key="mst",
        base_url="https://mst.gov.vn",
        home_path="/",
        category_path_pattern="/{slug}.htm",
        article_name="mst",
        max_categories=30,
        max_articles_per_category=80,
        deny_exact_paths=(
            "/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(
            r"^/.+-\d{8,}\.htm$",
        ),
        article_link_selector="div.box-category-item a[href]",
        description_selectors=(
            "div.detail-sapo",
            "meta[name='description']",
            "meta[property='og:description']",
        ),
    )


def _cema_config() -> SiteConfig:
    """
    Cấu hình cho http://cema.gov.vn (Cổng thông tin điện tử Bộ Dân tộc và Tôn giáo).

    Ghi chú:
    - Site phục vụ qua HTTP; HTTPS hiện lỗi chứng chỉ (hostname mismatch).
    - Trang chuyên mục thường là các URL kết thúc bằng ".htm" (ví dụ: /tin-tuc.htm,
      /tin-tuc/tin-tuc-su-kien/thoi-su-chinh-tri.htm).
    - Bài viết chi tiết thường nằm dưới các prefix như:
      /tin-tuc/<group>/<category>/<article>.htm, /thong-bao/<article>.htm, ...
    """

    return SiteConfig(
        key="cema",
        base_url="http://cema.gov.vn",
        home_path="/home.htm",
        canonicalize_category_paths=False,
        article_name="cema",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/tin-tuc",
            "/tin-tuc-hoat-dong",
            "/thong-bao",
            "/chuyen-doi-so",
        ),
        deny_exact_paths=(
            "/",
        ),
        # Tránh lấy nhầm link bài viết làm category.
        deny_category_path_regexes=(
            r"^/tin-tuc/[^/]+/[^/]+/.+\.htm$",
            r"^/tin-tuc-hoat-dong/.+\.htm$",
            r"^/thong-bao/.+\.htm$",
            r"^/chuyen-doi-so/.+\.htm$",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(
            r"^/tin-tuc/[^/]+/[^/]+/[^/]+\.htm$",
            r"^/tin-tuc-hoat-dong/[^/]+\.htm$",
            r"^/thong-bao/[^/]+\.htm$",
            r"^/chuyen-doi-so/[^/]+\.htm$",
        ),
        article_link_selector=(
            ".news-block a[href], .news-block-body a[href], .news-block-other a[href]"
        ),
        delay_seconds=1.0,
        max_retries=5,
        retry_backoff=1.5,
        request_headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )


def _moha_config() -> SiteConfig:
    """
    Cấu hình cho https://moha.gov.vn (Bộ Nội vụ).

    - Category có path dạng /chuyen-muc/<slug>---id<id>.
    - Bài viết có path dạng /tin-tuc/<slug>---id<id>.
    """

    return SiteConfig(
        key="moha",
        base_url="https://moha.gov.vn",
        home_path="/",
        category_path_pattern="/chuyen-muc/{slug}",
        article_name="moha",
        max_categories=20,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chuyen-muc",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_article_path_regexes=(
            r"^/tin-tuc/.+---id\d+/?$",
        ),
        article_link_selector="a[href*='/tin-tuc/']",
    )


def _moj_config() -> SiteConfig:
    """
    Cấu hình cho https://www.moj.gov.vn (Bộ Tư pháp).

    - Category dạng /qt/tintuc/Pages/<slug>.aspx.
    - Bài viết chi tiết dùng query param ItemID.
    """

    return SiteConfig(
        key="moj",
        base_url="https://www.moj.gov.vn",
        home_path="/Pages/home.aspx",
        category_path_pattern="/qt/tintuc/Pages/{slug}.aspx",
        article_name="moj",
        max_categories=200,
        max_articles_per_category=80,
        deny_category_prefixes=(
            "/UserControls",
        ),
        deny_exact_paths=(
            "/",
            "/Pages/home.aspx",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".aspx",),
        allowed_article_path_regexes=(
            r"^/qt/tintuc/Pages/.+\\.aspx$",
        ),
        article_link_selector="a[href*='ItemID=']",
        keep_query_params=True,
    )


def _mard_config() -> SiteConfig:
    """
    Cấu hình cho https://www.mard.gov.vn (Cổng thông tin điện tử Bộ NN&PTNT).

    - Trang chủ dùng /Pages/default.aspx.
    - Category list page dạng /Pages/tin-*.aspx và /Pages/danh-sach-tin-*.aspx.
    - Bài viết chi tiết dạng /Pages/<slug>.aspx (loại trừ các list page).
    """

    return SiteConfig(
        key="mard",
        base_url="https://mard.gov.vn",
        home_path="/Pages/default.aspx",
        category_path_pattern="/Pages/{slug}.aspx",
        article_name="mard",
        max_categories=20,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/Pages/tin-",
            "/Pages/danh-sach-tin-",
        ),
        deny_category_prefixes=(
            "/Pages/danh-sach-tin-video.aspx",
        ),
        deny_exact_paths=(
            "/",
            "/Pages/default.aspx",
        ),
        allowed_article_url_suffixes=(".aspx",),
        allowed_article_path_regexes=(
            r"^/Pages/.+\\.aspx$",
        ),
        deny_article_prefixes=(
            "/Pages/tin-",
            "/Pages/danh-sach-tin-",
            "/Pages/default.aspx",
        ),
        article_link_selector="a[href^='/Pages/'][href*='.aspx']",
        timeout_seconds=40,
        request_headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        },
    )


def _mae_config() -> SiteConfig:
    """
    Cấu hình cho https://mae.gov.vn (Bộ Nông nghiệp và Môi trường).

    - Category list page dạng /chuyen-muc/<slug>.htm.
    - Bài viết dạng /<slug>-<id>.htm hoặc /tin-*/<slug>-<id>.htm.
    """

    return SiteConfig(
        key="mae",
        base_url="https://mae.gov.vn",
        home_path="/",
        category_path_pattern="/chuyen-muc/{slug}.htm",
        article_name="mae",
        max_categories=30,
        max_articles_per_category=80,
        delay_seconds=1.5,
        allow_category_prefixes=(
            "/chuyen-muc/",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(
            r"^/[^/]+-\\d+\\.htm$",
            r"^/(?:tin-[^/]+|tin-tuc--su-kien)/[^/]+-\\d+\\.htm$",
        ),
        deny_article_prefixes=(
            "/chuyen-muc",
            "/gioi-thieu",
            "/Pages",
            "/lien-ket",
            "/van-ban",
        ),
        article_link_selector="a.item-tintuc[href]",
        blocked_content_markers=(
            "Thông báo từ chối truy cập",
            "Hệ thống đang gặp vấn đề khi xử lý yêu cầu của bạn",
        ),
        timeout_seconds=30,
        request_headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        },
    )


def _bvhttdl_config() -> SiteConfig:
    """
    Cấu hình cho https://bvhttdl.gov.vn (Cổng thông tin Bộ VHTT&DL).

    - Category chủ yếu dạng /<slug>.htm (vd: /tin-tuc-va-su-kien.htm).
    - Bài viết chi tiết thường là URL root-level kết thúc bằng số dạng timestamp:
      /<slug>-<16-17digits>.htm
    - Một số trang dạng "-t<id>.htm" là trang tổng hợp/chuyên đề, không phải bài viết.
    """

    return SiteConfig(
        key="bvhttdl",
        base_url="https://bvhttdl.gov.vn",
        home_path="/",
        category_path_pattern="/{slug}.htm",
        article_name="bvhttdl",
        max_categories=30,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/tin-tuc-va-su-kien",
            "/su-kien-trang-chu",
            "/van-hoa",
            "/the-ducthe-thao",
            "/du-lich",
            "/gia-dinh",
            "/bao-chi-xuat-ban",
        ),
        deny_exact_paths=(
            "/",
        ),
        deny_category_path_regexes=(
            r"^/.+-\d{14,17}\.htm$",
            r"^/.+-t\d+\.htm$",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_url_suffixes=(".htm",),
        allowed_article_path_regexes=(
            r"^/[^/]+-\d{14,17}\.htm$",
        ),
        article_link_selector="a[href$='.htm']",
        description_selectors=(
            "p.sapo",
        ),
    )


def _qdnd_config() -> SiteConfig:
    """
    Cấu hình cho https://www.qdnd.vn (Báo Quân đội nhân dân).

    - Category chính thường có path dạng /chinh-tri, /quoc-phong-an-ninh, ...
    - Bài viết có slug kết thúc bằng ID số, ví dụ "...-1020977".
    - Sapo nằm trong div.post-summary.
    """

    return SiteConfig(
        key="qdnd",
        base_url="https://www.qdnd.vn",
        home_path="/",
        article_name="qdnd",
        max_categories=40,
        max_articles_per_category=80,
        allow_category_prefixes=(
            "/chinh-tri",
            "/quoc-phong-an-ninh",
            "/da-phuong-tien",
            "/bao-ve-nen-tang-tu-tuong-cua-dang",
            "/phong-chong-dien-bien-hoa-binh",
            "/phong-chong-tu-dien-bien-tu-chuyen-hoa",
            "/kinh-te",
            "/xa-hoi",
            "/van-hoa",
            "/phong-su-dieu-tra",
            "/giao-duc-khoa-hoc",
            "/phap-luat",
            "/ban-doc",
            "/y-te",
            "/the-thao",
            "/quoc-te",
            "/du-lich",
            "/cung-ban-luan",
            "/tien-toi-dai-hoi-xiv-cua-dang",
        ),
        deny_category_prefixes=(
            "/audio",
            "/video",
            "/Lf",
        ),
        deny_exact_paths=(
            "/",
        ),
        allowed_locales=("vi", "vi-vn"),
        allowed_article_path_regexes=(r"-\d+/?$",),
        article_link_selector=".list-news a[href]",
        description_selectors=("div.post-summary",),
    )


def get_supported_sites() -> Dict[str, SiteConfig]:
    """Trả về dict {site_key: SiteConfig} cho tất cả các trang được hỗ trợ."""
    sites: Dict[str, SiteConfig] = {}
    for cfg in (
        _vnexpress_config(),
        _tuoitre_config(),
        _nguoilaodong_config(),
        _laodong_config(),
        _thanhnien_config(),
        _twentyfourh_config(),
        _tienphong_config(),
        _genk_config(),
        _kenh14_config(),
        _mattran_config(),
        _nguoiquansat_config(),
        _tinnhanhchungkhoan_config(),
        _giadinh_suckhoedoisong_config(),
        _nhandan_config(),
        _vietbao_config(),
        _anninhthudo_config(),
        _cafebiz_config(),
        _daibieunhandan_config(),
        _congly_config(),
        _nongnghiepmoitruong_config(),
        _cafef_config(),
        _vtv_config(),
        _vtvgov_config(),
        _vtcnews_config(),
        _baolaocai_config(),
        _baolaichau_config(),
        _huengaynay_config(),
        _vietnamnet_config(),
        _vietnamplus_config(),
        _sggp_config(),
        _baoxaydung_config(),
        _hanoimoi_config(),
        _baodautu_config(),
        _soha_config(),
        _vneconomy_config(),
        _vietnambiz_config(),
        _baophapluat_config(),
        _baodongnai_config(),
        _baodongthap_config(),
        _bnews_config(),
        _dantri_config(),
        _baocantho_config(),
        _baogialai_config(),
        _baothanhhoa_config(),
        _baohatinh_config(),
        _baohaugiang_config(),
        _baohungyen_config(),
        _baonghean_config(),
        _baothainguyen_config(),
        _baodaklak_config(),
        _baosonla_config(),
        _baodienbienphu_config(),
        _baocaobang_config(),
        _baobinhduong_config(),
        _baotayninh_config(),
        _baobacninhtv_config(),
        _baoquangninh_config(),
        _baoquangngai_config(),
        _baoquangtri_config(),
        _baocamau_config(),
        _baodongkhoi_config(),
        _dongkhoi_baovinhlong_config(),
        _znews_config(),
        _vov_config(),
        _baohaiphong_config(),
        _baodanang_config(),
        _bocongan_config(),
        _cand_config(),
        _modgov_config(),
        _vpcp_config(),
        _mofa_config(),
        _mof_config(),
        _moh_config(),
        _thanhtra_config(),
        _moit_config(),
        _moet_config(),
        _mst_config(),
        _cema_config(),
        _moha_config(),
        _moj_config(),
        _mard_config(),
        _mae_config(),
        _bvhttdl_config(),
        _qdnd_config(),
    ):
        sites[cfg.key] = cfg
    return sites


def list_site_keys() -> List[str]:
    """Danh sách key của các site, dùng cho CLI help."""
    return sorted(get_supported_sites().keys())


def get_site_config(site_key: str) -> SiteConfig:
    """Lấy cấu hình cho 1 site, raise KeyError nếu không tồn tại."""
    sites = get_supported_sites()
    try:
        return sites[site_key]
    except KeyError as exc:
        raise KeyError(
            f"Unknown site '{site_key}'. Supported sites: {', '.join(sorted(sites))}"
        ) from exc


def iter_site_configs(keys: Iterable[str] | None = None) -> Iterable[SiteConfig]:
    """Iterator trả về các cấu hình theo danh sách key (hoặc tất cả nếu None)."""
    sites = get_supported_sites()
    if keys is None:
        yield from sites.values()
        return
    for key in keys:
        if key not in sites:
            raise KeyError(
                f"Unknown site '{key}'. Supported sites: {', '.join(sorted(sites))}"
            )
        yield sites[key]
