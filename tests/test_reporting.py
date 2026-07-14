from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import Database
from reports import render_markdown
from services import ReportingService


class ReportingTestCase(unittest.TestCase):
    def test_reporting_engine(self) -> None:
        """Verify that a report can be generated and rendered."""

        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "test.db"
            db = Database(database_path)

            try:
                service = ReportingService(db)
                report = service.build_latest_report()
                markdown = render_markdown(report)

                self.assertTrue(report.title)
                self.assertIsNotNone(report.generated_at)
                self.assertTrue(markdown.startswith("# "))

            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()