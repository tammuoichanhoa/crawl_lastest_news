from __future__ import annotations

import argparse
import logging
import os
import sys
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
from .crawler import NewsSiteCrawler
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
    return parser.parse_args(argv)


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

    logging.info(
        "Selected sites: %s",
        ", ".join(cfg.key for cfg in site_configs),
    )

    with session_scope(database_url=args.database_url, echo=args.echo_sql) as session:
        for cfg in site_configs:
            crawler = NewsSiteCrawler(cfg, session=session)
            crawler.crawl(max_articles=args.max_articles_per_site)
            logging.info(
                "Site %s done. Stats: %s",
                cfg.key,
                crawler.stats,
            )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
