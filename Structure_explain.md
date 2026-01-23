# Project structure overview

This repo is a news crawler for Vietnamese sites. The core flow is:
`main.py` -> `site_crawler.py` -> `crawler/article.py` + database models in `db/`.

## Top-level entrypoints
- `main.py`
  - CLI entrypoint. Parses arguments (sites, DB URL, worker count, logging).
  - Creates per-site threads and runs `NewsSiteCrawler` for each site.
  - Uses `db/session.py` for SQLAlchemy sessions.
- `__init__.py`
  - Package description and module-level docstring.
- `crawler.py`
  - Compatibility shim that re-exports classes from `site_crawler.py`.

## Configuration
- `config.py`
  - Defines `SiteConfig` dataclass (base URL, category rules, URL filters, selectors).
  - Contains a config factory per site (e.g., `_vnexpress_config`, `_znews_config`).
  - Exposes helpers: `get_supported_sites`, `get_site_config`, `iter_site_configs`.

## Crawling and parsing
- `site_crawler.py`
  - `RateLimitedHttpClient`: requests wrapper with delay.
  - `NewsSiteCrawler`: orchestrates category discovery, article discovery, parsing, and DB save.
  - `ParsedArticle`/`CategoryInfo` data containers.
  - URL normalization and filtering (host, suffix, deny prefixes), skip rules, tag/media extraction.
- `crawler/article.py`
  - `ArticleExtractor`: HTML parser for title/description/content/tags/media.
  - Site-specific extraction rules are loaded via `crawler/site_config.py`.
  - Includes helpers for content pruning, meta parsing, and data normalization.
- `crawler/site_config.py`
  - `ArticleSiteConfig`: per-domain extraction overrides (selectors, keywords, exclusions).
  - Loads per-domain overrides from `crawler/site_config.yml`.
- `crawler/sitemap.py`
  - `SitemapCrawler`: fetches and parses sitemap or sitemap index URLs.
  - Supports gzip, legacy TLS, throttling, filtering.
- `crawler/throttle.py`
  - `RequestThrottler`: shared delay between outbound requests.
- `crawler/utils.py`
  - Small helpers (slugify, parse ISO/W3C datetime, etc.).

## Database
- `db/models.py`
  - SQLAlchemy models: `Article`, `ArticleImage`, `ArticleVideo`.
  - UUIDv7 IDs, relationships, and indexes.
  - Also includes example usage in a `__main__` block.
- `db/session.py`
  - Loads `.env`, builds engine, creates tables, provides `session_scope`.

## Tests
- `tests/test_site_crawler.py`
  - Unit tests for URL filtering and article parsing behavior.

## Docs and misc
- `README.md`
  - Usage, configuration, and run instructions.
- `grant_privileges.md`
  - SQL commands for database privileges.
- `requirements.txt`
  - Python dependencies.
- HTML fixtures (e.g., `znews_sample_article.html`, `vtcnews_home.html`)
  - Saved pages for debugging and local parsing tests.

## Data and runtime
- `logs/`
  - Per-site crawl logs.
- `pgdata/`
  - Local PostgreSQL data directory (Docker).
- `.env`
  - Database URL or other local environment settings.
