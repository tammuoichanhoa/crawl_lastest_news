import json
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from crawl_lastest_news import audit_images  # noqa: E402


class AuditImagesArgsTests(unittest.TestCase):
    def test_parse_args_accepts_last_n_days(self) -> None:
        args = audit_images._parse_args(["--last-n-days", "3"])
        self.assertEqual(args.last_n_days, 3)

    def test_parse_args_rejects_non_positive_last_n_days(self) -> None:
        with self.assertRaises(SystemExit):
            audit_images._parse_args(["--last-n-days", "0"])


class AuditImagesWindowTests(unittest.TestCase):
    def test_build_recent_days_includes_today(self) -> None:
        days = audit_images._build_recent_days(3, today=date(2026, 3, 31))
        self.assertEqual(days, [date(2026, 3, 31), date(2026, 3, 30), date(2026, 3, 29)])


class AuditImagesMultiDayMainTests(unittest.TestCase):
    def test_main_continues_when_one_day_folder_missing(self) -> None:
        args = Namespace(
            date=None,
            images_folder=None,
            last_n_days=3,
            images_base_dir="/base",
            database_url=None,
            status=None,
            limit=50,
            recursive=False,
            verbose_missing=False,
            report_json=None,
        )
        ok_result = audit_images.AuditResult(
            images_folder="/base/30_3_2026",
            disk_files_total=2,
            disk_files_nonmatching_name=0,
            db_rows_total=2,
            missing_total=0,
            extra_total=0,
            missing_sample=[],
            extra_sample=[],
        )

        with (
            mock.patch("crawl_lastest_news.audit_images._parse_args", return_value=args),
            mock.patch(
                "crawl_lastest_news.audit_images._build_recent_days",
                return_value=[date(2026, 3, 31), date(2026, 3, 30), date(2026, 3, 29)],
            ),
            mock.patch(
                "crawl_lastest_news.audit_images._build_images_folder_for_date",
                side_effect=["/base/31_3_2026", "/base/30_3_2026", "/base/29_3_2026"],
            ),
            mock.patch(
                "crawl_lastest_news.audit_images._audit_day",
                side_effect=[FileNotFoundError("missing day"), ok_result, ok_result],
            ) as audit_day,
        ):
            exit_code = audit_images.main(["--last-n-days", "3"])

        self.assertEqual(audit_day.call_count, 3)
        self.assertEqual(exit_code, 2)

    def test_main_writes_aggregate_and_per_day_json_for_last_n_days(self) -> None:
        args = Namespace(
            date=None,
            images_folder=None,
            last_n_days=2,
            images_base_dir="/base",
            database_url=None,
            status=None,
            limit=50,
            recursive=False,
            verbose_missing=False,
            report_json=None,
        )
        result_1 = audit_images.AuditResult(
            images_folder="/base/31_3_2026",
            disk_files_total=2,
            disk_files_nonmatching_name=0,
            db_rows_total=2,
            missing_total=0,
            extra_total=0,
            missing_sample=[],
            extra_sample=[],
        )
        result_2 = audit_images.AuditResult(
            images_folder="/base/30_3_2026",
            disk_files_total=3,
            disk_files_nonmatching_name=0,
            db_rows_total=3,
            missing_total=0,
            extra_total=0,
            missing_sample=[],
            extra_sample=[],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "report.json"
            args.report_json = str(report_path)
            with (
                mock.patch("crawl_lastest_news.audit_images._parse_args", return_value=args),
                mock.patch(
                    "crawl_lastest_news.audit_images._build_recent_days",
                    return_value=[date(2026, 3, 31), date(2026, 3, 30)],
                ),
                mock.patch(
                    "crawl_lastest_news.audit_images._build_images_folder_for_date",
                    side_effect=["/base/31_3_2026", "/base/30_3_2026"],
                ),
                mock.patch(
                    "crawl_lastest_news.audit_images._audit_day",
                    side_effect=[result_1, result_2],
                ),
            ):
                exit_code = audit_images.main(["--last-n-days", "2", "--report-json", str(report_path)])

            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertIn("days", payload)
        self.assertEqual(len(payload["days"]), 2)
        self.assertEqual(payload["days_requested"], 2)


if __name__ == "__main__":
    unittest.main()
