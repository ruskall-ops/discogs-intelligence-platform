from __future__ import annotations

from pathlib import Path

from database import Database
from reports import render_markdown
from services import ReportingService


def test_reporting_engine() -> None:
    """Verify that a report can be generated and rendered."""

    db = Database(Path("discogs_intelligence.db"))

    try:
        service = ReportingService(db)

        report = service.build_latest_report()
        markdown = render_markdown(report)

        assert report.title
        assert report.generated_at is not None
        assert markdown.startswith("# ")

    finally:
        db.close()