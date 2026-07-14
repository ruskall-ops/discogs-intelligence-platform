from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


from database import Database
from services import HistoricalIntelligenceService


class HistoricalIntelligenceTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database = Database(
            Path(self.temp_directory.name) / "test.db"
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def test_compare_latest_runs_handles_missing_history(self) -> None:
        service = HistoricalIntelligenceService(self.database)

        result = service.compare_latest_runs()

        self.assertIsNone(result)

    def test_compare_runs_calculates_market_changes(self) -> None:
        self.database.import_releases(
            rows=[
                {
                    "release_id": "1001",
                    "Artist": "Test Artist",
                    "Title": "Test Release",
                    "Label": "Test Label",
                    "Catalog#": "TEST-001",
                    "Format": "12\"",
                    "Released": "2026",
                    "CollectionFolder": "Test",
                    "Date Added": "2026-01-01",
                    "Rating": "0",
                }
            ],
            release_col="release_id",
        )
        first_run_id = self.database.start_analysis_run(
            run_type="market_refresh",
            source="test",
            application_version="test",
        )

        self.database.add_snapshot(
            first_run_id,
            1001,
            "2026-01-01T10:00:00",
            {
                "wants": 10,
                "haves": 20,
                "copies_for_sale": 5,
                "lowest_price": 10.00,
            },
        )

        self.database.complete_analysis_run(
            run_id=first_run_id,
            releases_attempted=1,
            releases_succeeded=1,
            releases_failed=0,
        )

        second_run_id = self.database.start_analysis_run(
            run_type="market_refresh",
            source="test",
            application_version="test",
        )

        self.database.add_snapshot(
            second_run_id,
            1001,
            "2026-01-02T10:00:00",
            {
                "wants": 14,
                "haves": 22,
                "copies_for_sale": 3,
                "lowest_price": 12.50,
            },
        )

        self.database.complete_analysis_run(
            run_id=second_run_id,
            releases_attempted=1,
            releases_succeeded=1,
            releases_failed=0,
        )

        service = HistoricalIntelligenceService(self.database)
        result = service.compare_latest_runs()

        self.assertIsNotNone(result)

        comparison = result.comparisons[0]

        self.assertEqual(comparison.status, "changed")
        self.assertEqual(comparison.wants_change, 4)
        self.assertEqual(comparison.haves_change, 2)
        self.assertEqual(comparison.copies_for_sale_change, -2)
        self.assertEqual(str(comparison.lowest_price_change), "2.5")
        self.assertEqual(result.total_changed, 1)    

if __name__ == "__main__":
    unittest.main()