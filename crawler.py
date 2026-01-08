"""Compatibility shim for legacy imports.

This module used to host the crawler implementation. The logic now lives in
`site_crawler.py` to avoid duplication and keep a single source of truth.
"""

from __future__ import annotations

from .site_crawler import (
    CategoryInfo,
    NewsSiteCrawler,
    ParsedArticle,
    RateLimitedHttpClient,
    SkipArticle,
)

__all__ = [
    "CategoryInfo",
    "NewsSiteCrawler",
    "ParsedArticle",
    "RateLimitedHttpClient",
    "SkipArticle",
]
