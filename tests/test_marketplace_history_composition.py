from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from dip.app import (
    MarketplaceHistoryCommandService,
    MarketplaceHistoryQueryService,
    MarketplaceMomentumExecutionService,
    MarketplaceStabilityExecutionService,
    MarketplaceScarcityExecutionService,
    ListingLifecycleExecutionService,
    PriceChangesExecutionService,
)
from dip.composition import (
    DesktopApplicationDependencies,
    build_desktop_application_dependencies,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)


class _CompositionMarketplaceHistoryRepository:
    def __init__(self, stored: MarketplaceSnapshot) -> None:
        self.stored = stored
        self.calls: list[tuple[str, object | None]] = []

    def save_snapshot(self, snapshot: MarketplaceSnapshot) -> None:
        self.calls.append(("save_snapshot", snapshot))

    def get_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None:
        self.calls.append(("get_snapshot", snapshot_id))
        return self.stored if snapshot_id == self.stored.snapshot_id else None

    def latest_snapshot(self) -> MarketplaceSnapshot | None:
        self.calls.append(("latest_snapshot", None))
        return self.stored

    def recent_snapshots(
        self,
        limit: int,
    ) -> tuple[MarketplaceSnapshot, ...]:
        self.calls.append(("recent_snapshots", limit))
        return (self.stored,)

    def previous_snapshot(
        self,
        snapshot_id: str,
    ) -> MarketplaceSnapshot | None:
        self.calls.append(("previous_snapshot", snapshot_id))
        return None

    def all_snapshots(self) -> tuple[MarketplaceSnapshot, ...]:
        self.calls.append(("all_snapshots", None))
        return (self.stored,)


class MarketplaceHistoryCompositionTestCase(unittest.TestCase):
    def test_existing_dependency_constructor_remains_compatible(self) -> None:
        existing = object()

        dependencies = DesktopApplicationDependencies(
            database=existing,  # type: ignore[arg-type]
            dashboard_homepage=existing,  # type: ignore[arg-type]
            collection_health_controller=existing,  # type: ignore[arg-type]
            collection_explorer_controller=existing,  # type: ignore[arg-type]
            hidden_gems_controller=existing,  # type: ignore[arg-type]
        )

        self.assertIs(dependencies.database, existing)
        self.assertIsNone(dependencies.marketplace_history_commands)
        self.assertIsNone(dependencies.marketplace_history_queries)
        self.assertIsNone(dependencies.price_changes_execution)
        self.assertIsNone(dependencies.listing_lifecycle_execution)
        self.assertIsNone(dependencies.marketplace_momentum_execution)
        self.assertIsNone(dependencies.marketplace_stability_execution)
        self.assertIsNone(dependencies.marketplace_scarcity_execution)

    def test_composition_exposes_services_without_accessing_history_on_startup(
        self,
    ) -> None:
        captured_at = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
        stored = MarketplaceSnapshot(
            "snapshot-1",
            captured_at,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (
                MarketplaceReleaseObservation(
                    1,
                    captured_at,
                    MarketplaceDataStatus.COMPLETE,
                    num_for_sale=0,
                ),
            ),
        )
        repository = _CompositionMarketplaceHistoryRepository(stored)
        database = object()

        with (
            patch("dip.composition.Database", return_value=database),
            patch(
                "dip.composition.SQLiteMarketplaceHistoryRepository",
                return_value=repository,
            ) as repository_type,
        ):
            dependencies = build_desktop_application_dependencies()

        repository_type.assert_called_once_with(database)
        self.assertIs(dependencies.database, database)
        self.assertIsInstance(
            dependencies.marketplace_history_queries,
            MarketplaceHistoryQueryService,
        )
        self.assertIsInstance(
            dependencies.marketplace_history_commands,
            MarketplaceHistoryCommandService,
        )
        self.assertIsInstance(
            dependencies.price_changes_execution,
            PriceChangesExecutionService,
        )
        self.assertIsInstance(
            dependencies.listing_lifecycle_execution,
            ListingLifecycleExecutionService,
        )
        self.assertIsInstance(
            dependencies.marketplace_momentum_execution,
            MarketplaceMomentumExecutionService,
        )
        self.assertIsInstance(
            dependencies.marketplace_stability_execution,
            MarketplaceStabilityExecutionService,
        )
        self.assertIsInstance(
            dependencies.marketplace_scarcity_execution,
            MarketplaceScarcityExecutionService,
        )
        self.assertEqual(repository.calls, [])

        self.assertIs(
            dependencies.marketplace_history_queries.latest_snapshot(),
            stored,
        )
        self.assertIs(
            dependencies.marketplace_history_commands.record_snapshot(stored),
            stored,
        )
        self.assertEqual(
            repository.calls,
            [
                ("latest_snapshot", None),
                ("save_snapshot", stored),
            ],
        )

        self.assertIsNotNone(dependencies.dashboard_homepage)
        self.assertIsNotNone(dependencies.collection_health_controller)
        self.assertIsNotNone(dependencies.collection_explorer_controller)
        self.assertIsNotNone(dependencies.hidden_gems_controller)


if __name__ == "__main__":
    unittest.main()
