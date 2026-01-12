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

    # Chỉ lấy link bài viết có path khớp regex (nếu rỗng sẽ bỏ qua lọc theo path).
    allowed_article_path_regexes: Tuple[str, ...] = field(default_factory=tuple)

    # Loại bỏ các bài viết có path bắt đầu bằng những prefix này.
    deny_article_prefixes: Tuple[str, ...] = field(default_factory=tuple)

    # Giữ lại query string khi chuẩn hóa URL (mặc định loại bỏ).
    keep_query_params: bool = False

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
        deny_exact_paths=("/",),
        allowed_article_path_regexes=(
            r"/\d{6}/[^/]+/?$",
        ),
        deny_article_prefixes=(
            "/video-clip",
            "/media/infographic",
            "/media/megastory",
            "/chinh-tri",
            "/kinh-te",
            "/van-hoc",
            "/van-hoa",
            "/xa-hoi",
            "/phap-luat",
            "/ban-doc",
            "/doanh-nhan-doanh-nghiep",
            "/kham-pha-dong-nai",
            "/dong-nai-cuoi-tuan",
            "/giai-tri",
        ),
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
        _vtcnews_config(),
        _baolaocai_config(),
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
        _bnews_config(),
        _dantri_config(),
        _baocantho_config(),
        _baodaklak_config(),
        _baodienbienphu_config(),
        _baocaobang_config(),
        _baobinhduong_config(),
        _baobacninhtv_config(),
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
