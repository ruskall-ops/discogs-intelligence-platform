from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from dip.experience.reporting.models import (
    AnalysisRunSummary,
    CollectionSummary,
    HistoricalSummary,
    IntelligenceReport,
    ReportMover,
)
from dip.persistence.sqlite import Database
from dip.snapshots.services.historical_intelligence import (
    HistoricalComparison,
    HistoricalIntelligenceService,
)


class ReportingService:
    """Assemble structured intelligence reports from DIP data."""

    def __init__(
        self,
        database: Database,
        historical_service: HistoricalIntelligenceService | None = None,
    ) -> None:
        self.database = database
        self.historical_service = (
            historical_service
            or HistoricalIntelligenceService(database)
        )

    def build_latest_report(
        self,
        mover_limit: int = 10,
    ) -> IntelligenceReport:
        """Build a report from the latest available platform data."""

        dashboard = self.database.dashboard()
        latest_run = self.database.latest_completed_analysis_run()
        comparison_result = self.historical_service.compare_latest_runs()

        collection_summary = CollectionSummary(
            unique_releases=int(dashboard["unique_releases"] or 0),
            owned_copies=int(dashboard["owned_copies"] or 0),
            high_priority=int(dashboard["high_priority"] or 0),
            worth_reviewing=int(dashboard["worth_reviewing"] or 0),
            hot_now=int(dashboard["hot_now"] or 0),
            protected=int(dashboard["protected"] or 0),
        )

        analysis_run_summary = None

        if latest_run is not None:
            analysis_run_summary = AnalysisRunSummary(
                run_id=int(latest_run["id"]),
                status=str(latest_run["status"]),
                started_at=str(latest_run["started_at"]),
                completed_at=(
                    str(latest_run["completed_at"])
                    if latest_run["completed_at"] is not None
                    else None
                ),
                releases_attempted=int(
                    latest_run["releases_attempted"] or 0
                ),
                releases_succeeded=int(
                    latest_run["releases_succeeded"] or 0
                ),
                releases_failed=int(
                    latest_run["releases_failed"] or 0
                ),
            )

        historical_summary = None
        top_price_movers: list[ReportMover] = []
        top_demand_movers: list[ReportMover] = []
        top_scarcity_movers: list[ReportMover] = []

        if comparison_result is not None:
            historical_summary = HistoricalSummary(
                latest_run_id=comparison_result.latest_run_id,
                previous_run_id=comparison_result.previous_run_id,
                total_comparisons=comparison_result.total,
                changed=comparison_result.total_changed,
                unchanged=comparison_result.total_unchanged,
                new=comparison_result.total_new,
                missing=comparison_result.total_missing,
                percent_changed=comparison_result.percent_changed,
            )

            changed = comparison_result.changed

            top_price_movers = self._build_movers(
                sorted(
                    changed,
                    key=lambda item: self._absolute_decimal(
                        item.lowest_price_percent_change
                    ),
                    reverse=True,
                )[:mover_limit]
            )

            top_demand_movers = self._build_movers(
                sorted(
                    changed,
                    key=lambda item: abs(item.wants_change or 0),
                    reverse=True,
                )[:mover_limit]
            )

            top_scarcity_movers = self._build_movers(
                sorted(
                    changed,
                    key=lambda item: abs(
                        item.copies_for_sale_change or 0
                    ),
                    reverse=True,
                )[:mover_limit]
            )

        return IntelligenceReport(
            title="Discogs Intelligence Report",
            generated_at=datetime.now(),
            collection=collection_summary,
            latest_run=analysis_run_summary,
            historical=historical_summary,
            top_price_movers=top_price_movers,
            top_demand_movers=top_demand_movers,
            top_scarcity_movers=top_scarcity_movers,
        )

    def _build_movers(
        self,
        comparisons: list[HistoricalComparison],
    ) -> list[ReportMover]:
        release_details = {
            int(row["release_id"]): row
            for row in self.database.review_rows(limit=100000)
        }

        movers: list[ReportMover] = []

        for comparison in comparisons:
            release = release_details.get(comparison.release_id)

            movers.append(
                ReportMover(
                    release_id=comparison.release_id,
                    artist=(
                        str(release["artist"])
                        if release is not None
                        else ""
                    ),
                    title=(
                        str(release["title"])
                        if release is not None
                        else ""
                    ),
                    wants_change=comparison.wants_change,
                    copies_for_sale_change=(
                        comparison.copies_for_sale_change
                    ),
                    lowest_price_change=(
                        comparison.lowest_price_change
                    ),
                    lowest_price_percent_change=(
                        comparison.lowest_price_percent_change
                    ),
                )
            )

        return movers

    @staticmethod
    def _absolute_decimal(
        value: Decimal | None,
    ) -> Decimal:
        if value is None:
            return Decimal("0")

        return abs(value)
