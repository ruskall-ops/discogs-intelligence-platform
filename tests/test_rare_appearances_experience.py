from datetime import datetime, timedelta, timezone
import unittest

from dip.app import RareAppearancesPresentationService
from dip.experience.desktop.rare_appearances_renderer import DesktopRareAppearancesRenderer
from dip.experience.rare_appearances import RareAppearancesDetailState, RareAppearancesDetailViewModelBuilder
from dip.intelligence import IntelligenceContext
from dip.marketplace_intelligence import MarketplaceDataStatus, MarketplaceReleaseObservation, MarketplaceSnapshot, RareAppearancesModule


class RareAppearancesExperienceTestCase(unittest.TestCase):
    def test_presentation_copies_output_and_renderer_displays_factual_values(self):
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        snapshots = tuple(MarketplaceSnapshot(f"snapshot-{index}", start + timedelta(days=index), "discogs", MarketplaceDataStatus.COMPLETE if index in (0, 2) else MarketplaceDataStatus.EMPTY, ((MarketplaceReleaseObservation(1, start + timedelta(days=index), MarketplaceDataStatus.COMPLETE, num_for_sale=1),) if index in (0, 2) else ())) for index in range(3))
        result = RareAppearancesModule().analyse(IntelligenceContext(marketplace_history=snapshots))
        detail = RareAppearancesPresentationService(RareAppearancesDetailViewModelBuilder()).detail_for_result(result)
        self.assertIs(detail.state, RareAppearancesDetailState.AVAILABLE)
        rendered = DesktopRareAppearancesRenderer().render(detail)
        self.assertIn("Appearances: 2 of 3", rendered.appearances[0].body)
        self.assertIn("Longest absence: 1 snapshots", rendered.appearances[0].body)

    def test_missing_result_is_unavailable(self):
        self.assertIs(RareAppearancesDetailViewModelBuilder().build(None).state, RareAppearancesDetailState.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
