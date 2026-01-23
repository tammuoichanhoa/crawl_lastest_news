from __future__ import annotations

from ..base import SiteConfig, _default_site_config
from ..registry import register_site

@register_site("laodong")
def build_config() -> SiteConfig:
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

