from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from dateutil import parser as date_parser
from sqlalchemy import select

# Allow running directly (like main.py) while keeping relative imports working.
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if package_parent not in sys.path:
        sys.path.insert(0, package_parent)
    __package__ = "crawl_lastest_news"

from .db.models import Article, ArticleImage  # noqa: E402
from .db.session import session_scope  # noqa: E402


_DEFAULT_IMAGES_BASE_DIR = "/data/lastest_news_images"
_FILENAME_RE = re.compile(r"^[0-9a-fA-F-]{36}_img_[0-9]+\.[A-Za-z0-9]+$")


@dataclass(frozen=True, slots=True)
class AuditResult:
    images_folder: str
    disk_files_total: int
    disk_files_nonmatching_name: int
    db_rows_total: int
    missing_total: int
    extra_total: int
    missing_sample: list[str]
    extra_sample: list[str]


def _build_images_folder_for_date(target_date: date, *, base_dir: str) -> str:
    folder_name = f"{target_date.day}_{target_date.month}_{target_date.year}"
    return str(Path(base_dir) / folder_name)


def _build_recent_days(last_n_days: int, *, today: date | None = None) -> list[date]:
    if last_n_days < 1:
        raise ValueError("last_n_days must be >= 1")
    base = today or date.today()
    return [base - timedelta(days=offset) for offset in range(last_n_days)]


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be an integer >= 1") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return number


def _parse_date(value: str) -> date:
    value = (value or "").strip()
    if not value:
        raise ValueError("Empty date value.")
    # Support both ISO (YYYY-MM-DD) and day/month/year-ish inputs.
    dt = date_parser.parse(value, dayfirst=True, yearfirst=False)
    return dt.date()


def _iter_disk_files(folder: Path, *, recursive: bool) -> Iterable[Path]:
    if recursive:
        yield from (p for p in folder.rglob("*") if p.is_file())
    else:
        yield from (p for p in folder.iterdir() if p.is_file())


def _audit_day(
    *,
    database_url: str | None,
    images_folder: str,
    limit: int,
    recursive: bool,
    include_statuses: Optional[set[str]],
    verbose_missing: bool,
) -> AuditResult:
    folder_path = Path(images_folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Images folder not found: {images_folder}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Images folder is not a directory: {images_folder}")

    disk_files: set[str] = set()
    nonmatching = 0
    for path in _iter_disk_files(folder_path, recursive=recursive):
        full = str(path)
        disk_files.add(full)
        if not _FILENAME_RE.match(path.name):
            nonmatching += 1

    folder_prefix = str(folder_path)
    if not folder_prefix.endswith(os.sep):
        folder_prefix += os.sep

    db_paths: set[str] = set()
    with session_scope(database_url=database_url) as session:
        stmt = select(ArticleImage.image_path).where(ArticleImage.image_path.like(folder_prefix + "%"))
        if include_statuses:
            stmt = stmt.where(ArticleImage.status.in_(sorted(include_statuses)))
        for (image_path,) in session.execute(stmt):
            if image_path:
                db_paths.add(str(image_path))

    missing = sorted(db_paths - disk_files)
    extra = sorted(disk_files - db_paths)

    missing_out = missing[:limit] if limit >= 0 else missing
    extra_out = extra[:limit] if limit >= 0 else extra

    # If requested, enrich missing list with article URL hints (without bloating output).
    if verbose_missing and missing_out:
        enriched: list[str] = []
        with session_scope(database_url=database_url) as session:
            for image_path in missing_out:
                row = (
                    session.execute(
                        select(Article.url, ArticleImage.sequence_number)
                        .join(Article, Article.id == ArticleImage.article_id)
                        .where(ArticleImage.image_path == image_path)
                        .limit(1)
                    )
                    .first()
                )
                if row:
                    url, seq = row
                    enriched.append(f"{image_path} | seq={seq} | {url}")
                else:
                    enriched.append(image_path)
        missing_out = enriched

    return AuditResult(
        images_folder=str(folder_path),
        disk_files_total=len(disk_files),
        disk_files_nonmatching_name=nonmatching,
        db_rows_total=len(db_paths),
        missing_total=len(missing),
        extra_total=len(extra),
        missing_sample=missing_out,
        extra_sample=extra_out,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Audit downloaded images in /data/lastest_news_images/<d_m_y>/ against DB rows "
            "(article_images.image_path)."
        )
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--date", help="Target day, e.g. 2026-03-20 or 20/3/2026.")
    g.add_argument("--images-folder", help="Explicit images folder path to audit.")
    g.add_argument(
        "--last-n-days",
        type=_positive_int,
        help="Audit today and previous N-1 days (e.g. --last-n-days 3).",
    )
    p.add_argument(
        "--images-base-dir",
        default=_DEFAULT_IMAGES_BASE_DIR,
        help=f"Base dir for --date (default: {_DEFAULT_IMAGES_BASE_DIR}).",
    )
    p.add_argument(
        "--database-url",
        dest="database_url",
        default=None,
        help="DB URL (default: DATABASE_URL from .env/env).",
    )
    p.add_argument(
        "--status",
        action="append",
        default=None,
        help="Filter DB rows by status; can be repeated, e.g. --status downloaded (default: all).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max items to print for missing/extra (default: 50). Use -1 for all.",
    )
    p.add_argument(
        "--recursive",
        action="store_true",
        help="Scan subfolders too (default: only top-level files).",
    )
    p.add_argument(
        "--verbose-missing",
        action="store_true",
        help="For missing paths, also print article URL hints (slower).",
    )
    p.add_argument(
        "--report-json",
        default=None,
        help="Write full summary JSON to this path.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    statuses = set(args.status) if args.status else None

    if args.last_n_days:
        days = _build_recent_days(args.last_n_days)
        day_reports: list[dict[str, object]] = []
        days_failed = 0
        total_missing = 0
        total_extra = 0
        total_disk_files = 0
        total_db_rows = 0

        for day in days:
            images_folder = _build_images_folder_for_date(day, base_dir=args.images_base_dir)
            day_payload: dict[str, object] = {
                "date": day.isoformat(),
                "images_folder": images_folder,
            }
            try:
                result = _audit_day(
                    database_url=args.database_url,
                    images_folder=images_folder,
                    limit=args.limit,
                    recursive=bool(args.recursive),
                    include_statuses=statuses,
                    verbose_missing=bool(args.verbose_missing),
                )
            except (FileNotFoundError, NotADirectoryError) as exc:
                days_failed += 1
                day_payload["ok"] = False
                day_payload["error"] = str(exc)
            else:
                day_ok = result.missing_total == 0 and result.extra_total == 0
                if not day_ok:
                    days_failed += 1

                total_missing += result.missing_total
                total_extra += result.extra_total
                total_disk_files += result.disk_files_total
                total_db_rows += result.db_rows_total

                day_payload.update(
                    {
                        "ok": day_ok,
                        "disk_files_total": result.disk_files_total,
                        "disk_files_nonmatching_name": result.disk_files_nonmatching_name,
                        "db_rows_total": result.db_rows_total,
                        "missing_on_disk_total": result.missing_total,
                        "extra_on_disk_total": result.extra_total,
                        "missing_on_disk_sample": result.missing_sample,
                        "extra_on_disk_sample": result.extra_sample,
                    }
                )
            day_reports.append(day_payload)

        ok = days_failed == 0
        for day_payload in day_reports:
            print(f"date={day_payload['date']}")
            print(f"images_folder={day_payload['images_folder']}")
            if "error" in day_payload:
                print(f"error={day_payload['error']}")
                continue
            print(f"disk_files_total={day_payload['disk_files_total']}")
            print(f"disk_files_nonmatching_name={day_payload['disk_files_nonmatching_name']}")
            print(f"db_rows_total={day_payload['db_rows_total']}")
            print(f"missing_on_disk={day_payload['missing_on_disk_total']}")
            for item in day_payload["missing_on_disk_sample"]:
                print(f"  MISSING {item}")
            print(f"extra_on_disk={day_payload['extra_on_disk_total']}")
            for item in day_payload["extra_on_disk_sample"]:
                print(f"  EXTRA   {item}")

        print(f"days_requested={len(days)}")
        print(f"days_failed={days_failed}")
        print(f"missing_on_disk_total={total_missing}")
        print(f"extra_on_disk_total={total_extra}")

        if args.report_json:
            payload = {
                "days_requested": len(days),
                "days_failed": days_failed,
                "disk_files_total": total_disk_files,
                "db_rows_total": total_db_rows,
                "missing_on_disk_total": total_missing,
                "extra_on_disk_total": total_extra,
                "days": day_reports,
                "ok": ok,
                "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            Path(args.report_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return 0 if ok else 2

    if args.date:
        day = _parse_date(args.date)
        images_folder = _build_images_folder_for_date(day, base_dir=args.images_base_dir)
    else:
        images_folder = args.images_folder

    result = _audit_day(
        database_url=args.database_url,
        images_folder=images_folder,
        limit=args.limit,
        recursive=bool(args.recursive),
        include_statuses=statuses,
        verbose_missing=bool(args.verbose_missing),
    )

    ok = result.missing_total == 0 and result.extra_total == 0
    print(f"images_folder={result.images_folder}")
    print(f"disk_files_total={result.disk_files_total}")
    print(f"disk_files_nonmatching_name={result.disk_files_nonmatching_name}")
    print(f"db_rows_total={result.db_rows_total}")
    print(f"missing_on_disk={result.missing_total}")
    if result.missing_sample:
        for item in result.missing_sample:
            print(f"  MISSING {item}")
    print(f"extra_on_disk={result.extra_total}")
    if result.extra_sample:
        for item in result.extra_sample:
            print(f"  EXTRA   {item}")

    if args.report_json:
        payload = {
            "images_folder": result.images_folder,
            "disk_files_total": result.disk_files_total,
            "disk_files_nonmatching_name": result.disk_files_nonmatching_name,
            "db_rows_total": result.db_rows_total,
            "missing_on_disk_total": result.missing_total,
            "extra_on_disk_total": result.extra_total,
            "missing_on_disk_sample": result.missing_sample,
            "extra_on_disk_sample": result.extra_sample,
            "ok": ok,
            "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        Path(args.report_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if ok else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
