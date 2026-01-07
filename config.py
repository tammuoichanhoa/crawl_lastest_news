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

    # Selector ưu tiên để tìm link bài viết trong trang category (nếu rỗng sẽ dùng heuristic chung).
    article_link_selector: str | None = None

    # Các selector ưu tiên để lấy description/sapo của bài viết (nếu rỗng sẽ dùng heuristic chung).
    description_selectors: Tuple[str, ...] = field(default_factory=tuple)

    # Chỉ chấp nhận các locale/language cụ thể (ví dụ: ("vi", "vi-vn")).
    allowed_locales: Tuple[str, ...] = field(default_factory=tuple)

    # Chỉ chấp nhận các host bài viết có hậu tố (suffix) nhất định, ví dụ: (".vn",)
    allowed_article_host_suffixes: Tuple[str, ...] = field(default_factory=tuple)

    # Chỉ lấy link bài viết có đuôi (suffix) cụ thể, ví dụ: (".html",)
    allowed_article_url_suffixes: Tuple[str, ...] = field(default_factory=tuple)

    # Loại bỏ các bài viết có path bắt đầu bằng những prefix này.
    deny_article_prefixes: Tuple[str, ...] = field(default_factory=tuple)

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
        allowed_article_url_suffixes=(".html",),
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
    return _default_site_config("vtv", "https://vtv.vn")


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


def _vietnamnet_config() -> SiteConfig:
    return _default_site_config("vietnamnet", "https://vietnamnet.vn")


def _vietnamplus_config() -> SiteConfig:
    return _default_site_config("vietnamplus", "https://www.vietnamplus.vn")


def _baoxaydung_config() -> SiteConfig:
    return _default_site_config("baoxaydung", "https://baoxaydung.vn")


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
    return _default_site_config("baophapluat", "https://baophapluat.vn")


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
        deny_exact_paths=("/",),
        description_selectors=(
            "div#content.content-detail .td-post-content > p",
            "div#content.content-detail p",
        ),
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


def _baocamau_config() -> SiteConfig:
    return _default_site_config("baocamau", "https://baocamau.vn")


def _baodongkhoi_config() -> SiteConfig:
    return _default_site_config("baodongkhoi", "https://baodongkhoi.vn")


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
        _vtcnews_config(),
        _baolaocai_config(),
        _vietnamnet_config(),
        _vietnamplus_config(),
        _baoxaydung_config(),
        _baodautu_config(),
        _soha_config(),
        _vneconomy_config(),
        _vietnambiz_config(),
        _baophapluat_config(),
        _baodongnai_config(),
        _bnews_config(),
        _dantri_config(),
        _baocamau_config(),
        _baodongkhoi_config(),
        _znews_config(),
        _vov_config(),
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
