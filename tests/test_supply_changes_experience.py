from datetime import datetime, timezone
import unittest

from dip.app import SupplyChangesPresentationService
from dip.experience.desktop.supply_changes_renderer import DesktopSupplyChangesRenderer
from dip.experience.supply_changes import SupplyChangesDetailState, SupplyChangesDetailViewModelBuilder
from dip.intelligence import IntelligenceContext
from dataclasses import replace
from dip.marketplace_intelligence import MarketplaceDataStatus, MarketplaceReleaseObservation, MarketplaceSnapshot, MarketplaceSnapshotComparisonInput, SupplyChangesModule


class SupplyChangesExperienceTestCase(unittest.TestCase):
    def test_presentation_copies_typed_result_and_renderer_formats_signed_delta(self):
        old_time = datetime(2026, 7, 21, tzinfo=timezone.utc)
        new_time = datetime(2026, 7, 22, tzinfo=timezone.utc)
        old = MarketplaceSnapshot("old", old_time, "discogs", MarketplaceDataStatus.COMPLETE, (MarketplaceReleaseObservation(1, old_time, MarketplaceDataStatus.COMPLETE, num_for_sale=2),))
        new = MarketplaceSnapshot("new", new_time, "discogs", MarketplaceDataStatus.COMPLETE, (MarketplaceReleaseObservation(1, new_time, MarketplaceDataStatus.COMPLETE, num_for_sale=5),))
        result = SupplyChangesModule().analyse(IntelligenceContext(marketplace_comparison=MarketplaceSnapshotComparisonInput(old, new)))
        detail = SupplyChangesPresentationService(SupplyChangesDetailViewModelBuilder()).detail_for_result(result)
        self.assertIs(detail.state, SupplyChangesDetailState.AVAILABLE)
        self.assertEqual(detail.changes[0].delta, 3)
        rendered = DesktopSupplyChangesRenderer().render(detail)
        self.assertIn("Delta: +3", rendered.changes[0].body)
        self.assertIn("Comparison source: discogs", rendered.context)

    def test_missing_result_is_unavailable(self):
        detail = SupplyChangesDetailViewModelBuilder().build(None)
        self.assertIs(detail.state, SupplyChangesDetailState.UNAVAILABLE)

    def test_current_builder_rejects_historical_version(self):
        result = SupplyChangesModule().analyse(IntelligenceContext())
        with self.assertRaises(ValueError):
            SupplyChangesDetailViewModelBuilder().build(
                replace(result, module_version="1.0")
            )

    def test_current_builder_accepts_only_exact_identity_and_version(self):
        builder = SupplyChangesDetailViewModelBuilder()
        current = SupplyChangesModule().analyse(IntelligenceContext())
        self.assertIs(builder.build(current).state, SupplyChangesDetailState.INSUFFICIENT_HISTORY)
        for module_id, module_version in (
            ("supply_changes", "1.0"),
            ("supply_changes", "99.0"),
            ("listing_price_changes", "1.0"),
            ("TOKEN-SQL-/private/live.sqlite", "2.0"),
        ):
            with self.subTest(module_id=module_id, module_version=module_version):
                with self.assertRaisesRegex(ValueError, "supported Supply Changes contract") as raised:
                    builder.build(replace(current, module_id=module_id, module_version=module_version))
                self.assertNotIn(module_id, str(raised.exception))
                self.assertNotIn(module_version, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
