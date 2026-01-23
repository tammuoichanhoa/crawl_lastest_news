from __future__ import annotations

from ..base import SiteConfig, _default_site_config
from ..registry import register_site

@register_site("nguoiquansat")
def build_config() -> SiteConfig:
    return _default_site_config("nguoiquansat", "https://nguoiquansat.vn")

