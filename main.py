from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Sequence

# Cho phép chạy trực tiếp file này:
#   python crawl_lastest_news/main.py --sites vnexpress tuoitre
# bằng cách thiết lập lại __package__ để relative import (.config, .crawler, ...)
# vẫn hoạt động như khi chạy dưới dạng module:
#   python -m crawl_lastest_news.main
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if package_parent not in sys.path:
        sys.path.insert(0, package_parent)
    __package__ = "crawl_lastest_news"

from .config import iter_site_configs, list_site_keys
from .site_crawler import NewsSiteCrawler
from .db.session import session_scope


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl các bài báo mới từ nhiều trang (vnexpress, tuoitre, ...)",
    )
    parser.add_argument(
        "--sites",
        nargs="*",
        metavar="SITE_KEY",
        help=(
            "Danh sách site muốn crawl, ví dụ: --sites vnexpress tuoitre "
            f"(mặc định: tất cả = {', '.join(list_site_keys())})"
        ),
    )
    # postgresql+psycopg2://crawl:crawl@localhost:15432/lastest_news
    parser.add_argument(
        "--database-url",
        dest="database_url",
        help=(
            "Chuỗi kết nối DB, ví dụ: postgresql+psycopg2://user:pass@host/dbname "
            "(mặc định: đọc từ biến môi trường DATABASE_URL hoặc file .env)."
        ),
    )
    parser.add_argument(
        "--max-articles-per-site",
        type=int,
        default=None,
        help="Giới hạn tổng số bài cho mỗi site (default: không giới hạn).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Mức log (default: INFO).",
    )
    parser.add_argument(
        "--echo-sql",
        action="store_true",
        help="Bật echo SQLAlchemy (debug).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Số luồng crawl song song (default: số site được chọn). "
            "Mỗi site sẽ chạy trong 1 thread và 1 DB session riêng."
        ),
    )
    parser.add_argument(
        "--list-article-links",
        action="store_true",
        help=(
            "Chỉ thu thập link bài viết từ trang category đầu tiên, "
            "không lưu DB."
        ),
    )
    parser.add_argument(
        "--output",
        help="Ghi kết quả JSON ra file (mặc định: in ra stdout).",
    )
    return parser.parse_args(argv)


def _crawl_single_site(
    cfg,
    *,
    database_url: str | None,
    echo_sql: bool,
    max_articles_per_site: int | None,
):
    with session_scope(database_url=database_url, echo=echo_sql) as session:
        crawler = NewsSiteCrawler(cfg, session=session)
        crawler.crawl(max_articles=max_articles_per_site)
        logging.info(
            "Site %s done. Stats: %s",
            cfg.key,
            crawler.stats,
        )


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        site_configs = list(iter_site_configs(args.sites))
    except KeyError as exc:
        logging.error("%s", exc)
        return 1

    if not site_configs:
        logging.warning("Không có site nào được chọn để crawl.")
        return 0

    if args.list_article_links:
        results = {}
        for cfg in site_configs:
            crawler = NewsSiteCrawler(cfg, session=None)
            results[cfg.key] = crawler.collect_category_article_links()
        payload = json.dumps(results, ensure_ascii=True, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(payload)
        else:
            print(payload)
        return 0

    logging.info(
        "Selected sites: %s",
        ", ".join(cfg.key for cfg in site_configs),
    )

    workers = args.workers or len(site_configs)
    if workers < 1:
        workers = 1

    logging.info("Starting crawl with %s worker(s)", workers)

    # Mỗi site chạy trong 1 thread riêng với 1 DB session riêng.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_cfg = {
            executor.submit(
                _crawl_single_site,
                cfg,
                database_url=args.database_url,
                echo_sql=args.echo_sql,
                max_articles_per_site=args.max_articles_per_site,
            ): cfg
            for cfg in site_configs
        }

        for future in as_completed(future_to_cfg):
            cfg = future_to_cfg[future]
            try:
                future.result()
            except Exception as exc:  # pragma: no cover - logging only
                logging.exception("Site %s failed: %s", cfg.key, exc)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
