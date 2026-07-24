from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dip.intelligence import IntelligenceContext, IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    dumps_intelligence_value,
    loads_intelligence_value,
)
from dip.marketplace_intelligence import (
    ListingPriceChange,
    MarketplaceDataStatus,
    MarketplaceListingObservation,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    PriceChangeDelta,
    PriceChangesModule,
    PriceChangesOutput,
    PriceChangesSnapshotReference,
    PriceChangesSummary,
    ReleasePriceChange,
)


class PriceChangesHistorySerializationTestCase(unittest.TestCase):
    def test_typed_price_changes_result_round_trips_without_type_or_scale_loss(
        self,
    ) -> None:
        result = PriceChangesModule().analyse(
            IntelligenceContext(
                marketplace_comparison=MarketplaceSnapshotComparisonInput(
                    previous_snapshot=snapshot(
                        "previous",
                        datetime(2026, 7, 21, 9, tzinfo=timezone.utc),
                        lowest="10.00",
                        highest="20.000",
                        listing="12.50",
                    ),
                    latest_snapshot=snapshot(
                        "latest",
                        datetime(
                            2026,
                            7,
                            22,
                            10,
                            tzinfo=timezone(timedelta(hours=1)),
                        ),
                        lowest="11.000",
                        highest="18.00",
                        listing="13.000",
                    ),
                )
            )
        )
        record = IntelligenceHistoryRecord(
            record_id=None,
            run_id=1,
            module_id=result.module_id,
            module_version=result.module_version,
            status=result.status,
            summary=result.summary,
            metrics=result.metrics,
            evidence=result.evidence,
            diagnostics=result.diagnostics,
        )

        restored = loads_intelligence_value(dumps_intelligence_value(record))

        self.assertEqual(restored, record)
        self.assertIs(restored.status, IntelligenceStatus.COMPLETED)
        output = restored.metrics["output"]
        self.assertIs(type(output), PriceChangesOutput)
        self.assertIs(type(output.previous_snapshot), PriceChangesSnapshotReference)
        self.assertIs(type(output.summary), PriceChangesSummary)
        self.assertTrue(
            all(type(value) is ListingPriceChange for value in output.listing_changes)
        )
        self.assertTrue(
            all(type(value) is ReleasePriceChange for value in output.release_changes)
        )
        self.assertTrue(
            all(
                type(value.delta) is PriceChangeDelta
                for value in (*output.listing_changes, *output.release_changes)
            )
        )
        self.assertEqual(output.listing_changes[0].delta.amount, Decimal("0.500"))
        self.assertEqual(output.listing_changes[0].delta.amount.as_tuple().exponent, -3)
        self.assertEqual(
            output.release_changes[0].delta.amount,
            Decimal("1.000"),
        )
        self.assertEqual(
            output.release_changes[1].delta.amount,
            Decimal("-2.000"),
        )
        self.assertEqual(
            output.release_changes[1].delta.amount.as_tuple().exponent,
            -3,
        )


def snapshot(
    snapshot_id: str,
    captured_at: datetime,
    *,
    lowest: str,
    highest: str,
    listing: str,
) -> MarketplaceSnapshot:
    observed_at = captured_at - timedelta(minutes=5)
    return MarketplaceSnapshot(
        snapshot_id=snapshot_id,
        captured_at=captured_at,
        source="discogs",
        status=MarketplaceDataStatus.COMPLETE,
        release_observations=(
            MarketplaceReleaseObservation(
                release_id=1,
                observed_at=observed_at,
                status=MarketplaceDataStatus.COMPLETE,
                lowest_price=MarketplaceMoney(Decimal(lowest), "GBP"),
                highest_price=MarketplaceMoney(Decimal(highest), "GBP"),
            ),
        ),
        listing_observations=(
            MarketplaceListingObservation(
                listing_id="listing-1",
                release_id=1,
                observed_at=observed_at,
                price=MarketplaceMoney(Decimal(listing), "GBP"),
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
