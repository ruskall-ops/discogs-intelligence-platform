import unittest

from dip.app import ListingLifecyclePresentationService
from dip.experience.desktop.listing_lifecycle_renderer import DesktopListingLifecycleRenderer
from dip.experience.listing_lifecycle import ListingLifecycleDetailState, ListingLifecycleDetailViewModelBuilder
from tests.test_listing_lifecycle import history, output


class ListingLifecycleExperienceTestCase(unittest.TestCase):
    def test_presentation_preserves_typed_order_and_renderer_is_factual(self):
        result, _ = output(history())
        detail = ListingLifecyclePresentationService(ListingLifecycleDetailViewModelBuilder()).detail_for_result(result)
        self.assertIs(detail.state, ListingLifecycleDetailState.AVAILABLE)
        rendered = DesktopListingLifecycleRenderer().render(detail)
        active = next(value for value in rendered.lifecycles if value.listing_id == "active")
        self.assertIn("Lifecycle state: Active", active.body)
        self.assertIn("Observed snapshots: 6 of 6", active.body)
        self.assertIn("Observation ratio: 1", active.body)

    def test_missing_result_is_unavailable(self):
        self.assertIs(ListingLifecycleDetailViewModelBuilder().build(None).state, ListingLifecycleDetailState.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
