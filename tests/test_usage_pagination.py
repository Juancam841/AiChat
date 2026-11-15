import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from usage_manager import get_usage_summary, get_usage_summary_page


class UsagePaginationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "usage.db"
        connection = sqlite3.connect(self.database_path)
        connection.execute("""
            CREATE TABLE usage_records (
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                web_search_requests INTEGER NOT NULL DEFAULT 0,
                browser_open_requests INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.executemany("""
            INSERT INTO usage_records (
                provider, model, prompt_tokens, completion_tokens,
                total_tokens, success, created_at,
                web_search_requests, browser_open_requests
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("zeta", "model-b", 7, 3, 10, 1, "2026-11-03T00:00:00+00:00", 1, 0),
            ("alpha", "model-c", 5, 2, 7, 0, "2026-11-02T00:00:00+00:00", 0, 1),
            ("alpha", "model-a", 4, 6, 10, 1, "2026-11-01T00:00:00+00:00", 0, 0),
            ("alpha", "model-a", 1, 2, 3, 0, "2026-11-04T00:00:00+00:00", 1, 0),
        ])
        connection.commit()
        connection.close()

        def connect_to_test_database():
            test_connection = sqlite3.connect(self.database_path)
            test_connection.row_factory = sqlite3.Row
            return test_connection

        self.connection_patch = patch(
            "usage_manager.get_connection",
            side_effect=connect_to_test_database,
        )
        self.connection_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.temp_dir.cleanup()

    def test_page_is_stably_ordered_and_reports_total_and_has_more(self):
        page = get_usage_summary_page(limit=2, offset=0)

        self.assertEqual(page["total"], 3)
        self.assertEqual(page["limit"], 2)
        self.assertEqual(page["offset"], 0)
        self.assertTrue(page["has_more"])
        self.assertEqual(
            list(page["usage"]),
            ["alpha/model-a", "alpha/model-c"],
        )
        self.assertEqual(page["usage"]["alpha/model-a"]["requests"], 2)

    def test_last_page_and_empty_page_have_correct_has_more(self):
        last_page = get_usage_summary_page(limit=2, offset=2)
        empty_page = get_usage_summary_page(limit=2, offset=3)

        self.assertEqual(last_page["total"], 3)
        self.assertFalse(last_page["has_more"])
        self.assertEqual(list(last_page["usage"]), ["zeta/model-b"])
        self.assertEqual(empty_page["usage"], {})
        self.assertFalse(empty_page["has_more"])

    def test_empty_table_returns_empty_legacy_and_paged_summaries(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM usage_records")
        connection.commit()
        connection.close()

        self.assertEqual(get_usage_summary(), {})
        self.assertEqual(get_usage_summary_page(limit=25, offset=0), {
            "usage": {},
            "total": 0,
            "limit": 25,
            "offset": 0,
            "has_more": False,
        })

    def test_legacy_summary_contract_is_unchanged(self):
        summary = get_usage_summary()

        self.assertEqual(set(summary), {
            "alpha/model-a",
            "alpha/model-c",
            "zeta/model-b",
        })
        self.assertEqual(summary["alpha/model-a"]["requests"], 2)
        self.assertNotIn("total", summary)
        self.assertNotIn("has_more", summary)

    def test_minimum_and_maximum_limits_and_zero_offset(self):
        minimum_page = get_usage_summary_page(limit=1, offset=0)
        maximum_page = get_usage_summary_page(limit=100, offset=0)

        self.assertEqual(minimum_page["limit"], 1)
        self.assertEqual(minimum_page["offset"], 0)
        self.assertEqual(len(minimum_page["usage"]), 1)
        self.assertEqual(maximum_page["limit"], 100)
        self.assertEqual(maximum_page["offset"], 0)
        self.assertEqual(len(maximum_page["usage"]), 3)

    def test_out_of_range_pagination_values_are_rejected(self):
        for invalid_limit in (0, 101, -1, 1.5, True, "10"):
            with self.subTest(limit=invalid_limit):
                with self.assertRaises(ValueError):
                    get_usage_summary_page(limit=invalid_limit, offset=0)

        for invalid_offset in (-1, 1.5, True, "0"):
            with self.subTest(offset=invalid_offset):
                with self.assertRaises(ValueError):
                    get_usage_summary_page(limit=25, offset=invalid_offset)


if __name__ == "__main__":
    unittest.main()
