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
from typing import Dict, Iterable, List, Tuple


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


def _default_site_config(
    key: str,
    base_url: str,
    *,
    article_name: str | None = None,
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
    )


def _genk_config() -> SiteConfig:
    return _default_site_config("genk", "https://genk.vn")


def _kenh14_config() -> SiteConfig:
    return _default_site_config("kenh14", "https://kenh14.vn")


def _mattran_config() -> SiteConfig:
    return _default_site_config("mattran", "https://mattran.org.vn")


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
    return _default_site_config("nhandan", "https://nhandan.vn")


def _vietbao_config() -> SiteConfig:
    return _default_site_config("vietbao", "https://vietbao.vn")


def _anninhthudo_config() -> SiteConfig:
    return _default_site_config("anninhthudo", "https://www.anninhthudo.vn")


def _cafebiz_config() -> SiteConfig:
    return _default_site_config("cafebiz", "https://cafebiz.vn")


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


def get_supported_sites() -> Dict[str, SiteConfig]:
    """Trả về dict {site_key: SiteConfig} cho tất cả các trang được hỗ trợ."""
    sites: Dict[str, SiteConfig] = {}
    for cfg in (
        _vnexpress_config(),
        _tuoitre_config(),
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
        _baolaocai_config(),
        _vietnamnet_config(),
        _vietnamplus_config(),
        _baoxaydung_config(),
        _baodautu_config(),
        _soha_config(),
        _vneconomy_config(),
        _baophapluat_config(),
        _baodongnai_config(),
        _bnews_config(),
        _dantri_config(),
        _baocamau_config(),
        _baodongkhoi_config(),
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
