from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from database import Database


ComparisonStatus = Literal[
    "changed",
    "unchanged",
    "new",
    "missing",
]


@dataclass(frozen=True)
class HistoricalComparison:
    """Objective change for one release between two analysis runs."""

    release_id: int
    status: ComparisonStatus

    previous_wants: int | None
    latest_wants: int | None
    wants_change: int | None

    previous_haves: int | None
    latest_haves: int | None
    haves_change: int | None

    previous_copies_for_sale: int | None
    latest_copies_for_sale: int | None
    copies_for_sale_change: int | None

    previous_lowest_price: Decimal | None
    latest_lowest_price: Decimal | None
    lowest_price_change: Decimal | None
    lowest_price_percent_change: Decimal | None


@dataclass(frozen=True)
class HistoricalComparisonResult:
    """Comparison of two completed marketplace analysis runs."""

    latest_run_id: int
    previous_run_id: int
    comparisons: list[HistoricalComparison]


class HistoricalIntelligenceService:
    """Compare marketplace snapshots between completed analysis runs."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def compare_latest_runs(self) -> HistoricalComparisonResult | None:
        """
        Compare the latest completed marketplace run with the previous one.

        Returns None when fewer than two completed marketplace runs exist.
        """

        latest_run = self.database.latest_completed_analysis_run()

        if latest_run is None:
            return None

        previous_run = self.database.previous_completed_analysis_run(
            latest_run["id"],
        )

        if previous_run is None:
            return None

        return self.compare_runs(
            latest_run_id=latest_run["id"],
            previous_run_id=previous_run["id"],
        )

    def compare_runs(
        self,
        latest_run_id: int,
        previous_run_id: int,
    ) -> HistoricalComparisonResult:
        latest_rows = self.database.snapshots_for_analysis_run(
            latest_run_id,
        )
        previous_rows = self.database.snapshots_for_analysis_run(
            previous_run_id,
        )

        latest_by_release = {
            int(row["release_id"]): row
            for row in latest_rows
        }

        previous_by_release = {
            int(row["release_id"]): row
            for row in previous_rows
        }

        release_ids = sorted(
            set(latest_by_release) | set(previous_by_release)
        )

        comparisons = [
            self._compare_release(
                release_id=release_id,
                latest=latest_by_release.get(release_id),
                previous=previous_by_release.get(release_id),
            )
            for release_id in release_ids
        ]

        return HistoricalComparisonResult(
            latest_run_id=latest_run_id,
            previous_run_id=previous_run_id,
            comparisons=comparisons,
        )

    def _compare_release(
        self,
        release_id: int,
        latest,
        previous,
    ) -> HistoricalComparison:
        if previous is None:
            return HistoricalComparison(
                release_id=release_id,
                status="new",
                previous_wants=None,
                latest_wants=int(latest["wants"]),
                wants_change=None,
                previous_haves=None,
                latest_haves=int(latest["haves"]),
                haves_change=None,
                previous_copies_for_sale=None,
                latest_copies_for_sale=int(latest["copies_for_sale"]),
                copies_for_sale_change=None,
                previous_lowest_price=None,
                latest_lowest_price=self._price(latest["lowest_price"]),
                lowest_price_change=None,
                lowest_price_percent_change=None,
            )

        if latest is None:
            return HistoricalComparison(
                release_id=release_id,
                status="missing",
                previous_wants=int(previous["wants"]),
                latest_wants=None,
                wants_change=None,
                previous_haves=int(previous["haves"]),
                latest_haves=None,
                haves_change=None,
                previous_copies_for_sale=int(
                    previous["copies_for_sale"]
                ),
                latest_copies_for_sale=None,
                copies_for_sale_change=None,
                previous_lowest_price=self._price(
                    previous["lowest_price"]
                ),
                latest_lowest_price=None,
                lowest_price_change=None,
                lowest_price_percent_change=None,
            )

        previous_price = self._price(previous["lowest_price"])
        latest_price = self._price(latest["lowest_price"])

        wants_change = int(latest["wants"]) - int(previous["wants"])
        haves_change = int(latest["haves"]) - int(previous["haves"])
        copies_change = (
            int(latest["copies_for_sale"])
            - int(previous["copies_for_sale"])
        )
        price_change = latest_price - previous_price

        price_percent_change = None

        if previous_price > 0:
            price_percent_change = (
                price_change / previous_price
            ) * Decimal("100")

        status: ComparisonStatus = (
            "unchanged"
            if (
                wants_change == 0
                and haves_change == 0
                and copies_change == 0
                and price_change == 0
            )
            else "changed"
        )

        return HistoricalComparison(
            release_id=release_id,
            status=status,
            previous_wants=int(previous["wants"]),
            latest_wants=int(latest["wants"]),
            wants_change=wants_change,
            previous_haves=int(previous["haves"]),
            latest_haves=int(latest["haves"]),
            haves_change=haves_change,
            previous_copies_for_sale=int(
                previous["copies_for_sale"]
            ),
            latest_copies_for_sale=int(
                latest["copies_for_sale"]
            ),
            copies_for_sale_change=copies_change,
            previous_lowest_price=previous_price,
            latest_lowest_price=latest_price,
            lowest_price_change=price_change,
            lowest_price_percent_change=price_percent_change,
        )

    @staticmethod
    def _price(value) -> Decimal:
        return Decimal(str(value or 0))