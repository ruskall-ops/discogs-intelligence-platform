import unittest

from dip.app import MarketplaceActivityPresentationService
from dip.experience.desktop.marketplace_activity_renderer import DesktopMarketplaceActivityRenderer
from dip.experience.marketplace_activity import MarketplaceActivityDetailState, MarketplaceActivityDetailViewModelBuilder
from tests.test_marketplace_activity import activity, source_results


class MarketplaceActivityExperienceTestCase(unittest.TestCase):
    def test_presentation_preserves_aggregation_and_renderer_is_factual(self):
        _, price, supply, rare = source_results()
        result, _ = activity(price, supply, rare)
        detail = MarketplaceActivityPresentationService(MarketplaceActivityDetailViewModelBuilder()).detail_for_result(result)
        self.assertIs(detail.state, MarketplaceActivityDetailState.AVAILABLE)
        self.assertEqual(tuple(value.release_id for value in detail.activities), (1, 2))
        rendered = DesktopMarketplaceActivityRenderer().render(detail)
        self.assertIn("Historical activity count: 4", rendered.activities[0].body)
        self.assertIn("Appearance ratio: 0.666", rendered.activities[0].body)

    def test_missing_result_is_unavailable(self):
        self.assertIs(MarketplaceActivityDetailViewModelBuilder().build(None).state, MarketplaceActivityDetailState.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
