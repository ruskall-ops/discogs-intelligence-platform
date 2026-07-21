from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    CollectionHealthPresentationService,
    HiddenGemsPresentationService,
    WeekendListingsPresentationService,
)
from dip.experience.collection_health import CollectionHealthDetailViewModelBuilder
from dip.experience.desktop import (
    DesktopCollectionExplorerController,
    DesktopCollectionExplorerRenderer,
    DesktopWeekendListingsRenderer,
)
from dip.experience.explorer import (
    CollectionExplorerDestination,
    CollectionExplorerState,
    CollectionExplorerViewModelBuilder,
)
from dip.experience.hidden_gems import HiddenGemsDetailViewModelBuilder
from dip.experience.weekend_listings import (
    WeekendListingsDetailConsistencyError,
    WeekendListingsDetailState,
    WeekendListingsDetailViewModel,
    WeekendListingsDetailViewModelBuilder,
)
from dip.intelligence import IntelligenceContext
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    WeekendListingsModule,
    WeekendWindow,
)
from tests.test_collection_explorer import available_homepage
from tests.test_weekend_listings import (
    MONDAY,
    SATURDAY,
    listing,
    snapshot,
)


class WeekendListingsPresentationModelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = WeekendListingsDetailViewModelBuilder()

    def test_available_model_is_frozen_and_preserves_exact_values_and_order(self) -> None:
        result = weekend_result(
            listing("later", 1, SATURDAY.replace(hour=10)),
            listing("earlier", 2, SATURDAY.replace(hour=9)),
        )

        detail = self.builder.build(result)
        copied = replace(detail, candidates=list(detail.candidates))

        self.assertIs(detail.state, WeekendListingsDetailState.AVAILABLE)
        self.assertEqual(detail.candidate_count, 2)
        self.assertEqual(
            tuple(value.listing_id for value in detail.candidates),
            ("later", "earlier"),
        )
        self.assertEqual(detail.candidates[0].price.amount.as_tuple().exponent, -2)
        self.assertIsInstance(copied.candidates, tuple)
        with self.assertRaises(FrozenInstanceError):
            detail.summary = "Changed"  # type: ignore[misc]

    def test_partial_empty_unavailable_insufficient_and_error_are_distinct(self) -> None:
        partial = self.builder.build(
            weekend_result(
                listing("listing-1", 1, SATURDAY, optional=False)
            )
        )
        empty = self.builder.build(weekend_result())
        unavailable = self.builder.build(None)
        insufficient = self.builder.build(
            WeekendListingsModule(WeekendWindow(SATURDAY, MONDAY)).analyse(
                IntelligenceContext()
            )
        )
        failed_source = replace(
            snapshot(),
            status=MarketplaceDataStatus.FAILED,
            release_observations=(),
            listing_observations=(),
            diagnostics=(
                MarketplaceDiagnostic("capture_failed", "Capture failed."),
            ),
        )
        error = self.builder.build(
            WeekendListingsModule(WeekendWindow(SATURDAY, MONDAY)).analyse(
                IntelligenceContext(
                    collection=({"release_id": 1},),
                    marketplace_snapshot=failed_source,
                )
            )
        )

        self.assertIs(partial.state, WeekendListingsDetailState.PARTIAL)
        self.assertIs(empty.state, WeekendListingsDetailState.EMPTY)
        self.assertIs(unavailable.state, WeekendListingsDetailState.UNAVAILABLE)
        self.assertIs(
            insufficient.state,
            WeekendListingsDetailState.UNAVAILABLE,
        )
        self.assertIs(error.state, WeekendListingsDetailState.ERROR)

    def test_builder_rejects_wrong_module_missing_output_and_does_not_reorder(self) -> None:
        result = weekend_result(listing("listing-1", 1, SATURDAY))
        with self.assertRaisesRegex(WeekendListingsDetailConsistencyError, "requires"):
            self.builder.build(replace(result, module_id="other_module"))
        with self.assertRaisesRegex(WeekendListingsDetailConsistencyError, "typed"):
            self.builder.build(replace(result, metrics={}))

        output = result.metrics["output"]
        with self.assertRaisesRegex(WeekendListingsDetailConsistencyError, "order"):
            replace(
                self.builder.build(
                    weekend_result(
                        listing("later", 1, SATURDAY.replace(hour=10)),
                        listing("earlier", 2, SATURDAY.replace(hour=9)),
                    )
                ),
                candidates=tuple(
                    reversed(
                        self.builder.build(
                            weekend_result(
                                listing("later", 1, SATURDAY.replace(hour=10)),
                                listing("earlier", 2, SATURDAY.replace(hour=9)),
                            )
                        ).candidates
                    )
                ),
            )
        self.assertEqual(output.candidates[0].listing_id, "listing-1")

    def test_contradictory_count_duplicates_and_state_are_rejected(self) -> None:
        detail = self.builder.build(
            weekend_result(listing("listing-1", 1, SATURDAY))
        )

        with self.assertRaisesRegex(WeekendListingsDetailConsistencyError, "complete"):
            replace(detail, candidate_count=2)
        with self.assertRaisesRegex(WeekendListingsDetailConsistencyError, "unique"):
            replace(detail, candidates=(detail.candidates[0], detail.candidates[0]))
        with self.assertRaisesRegex(WeekendListingsDetailConsistencyError, "zero"):
            replace(detail, state=WeekendListingsDetailState.EMPTY)


class WeekendListingsRendererTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = WeekendListingsDetailViewModelBuilder()
        self.renderer = DesktopWeekendListingsRenderer()

    def test_available_rendering_preserves_window_money_and_evidence(self) -> None:
        rendered = self.renderer.render(
            self.builder.build(
                weekend_result(listing("listing-1", 1, SATURDAY))
            )
        )

        self.assertIn("2026-07-18T00:00+00:00", rendered.context)
        self.assertIn("2026-07-20T00:00+00:00", rendered.context)
        self.assertEqual(rendered.candidates[0].heading, "Artist 1 — Title 1")
        self.assertIn("Price: GBP 20.00", rendered.candidates[0].body)
        self.assertIn("Shipping: GBP 3.00", rendered.candidates[0].body)
        self.assertIn("Release is present", rendered.candidates[0].body)

    def test_missing_optional_empty_unavailable_and_insufficient_render_clearly(self) -> None:
        partial = self.renderer.render(
            self.builder.build(
                weekend_result(
                    listing("listing-1", 1, SATURDAY, optional=False)
                )
            )
        )
        empty = self.renderer.render(self.builder.build(weekend_result()))
        unavailable = self.renderer.render(WeekendListingsDetailViewModel.unavailable())
        insufficient = self.renderer.render(
            self.builder.build(
                WeekendListingsModule(WeekendWindow(SATURDAY, MONDAY)).analyse(
                    IntelligenceContext()
                )
            )
        )

        self.assertIn("Shipping: Unavailable", partial.candidates[0].body)
        self.assertIn("Condition: Unavailable", partial.candidates[0].body)
        self.assertIn("Seller region: Unavailable", partial.candidates[0].body)
        self.assertIn("No qualifying", empty.headline)
        self.assertIn("unavailable", unavailable.headline.lower())
        self.assertIn("unavailable", insufficient.headline.lower())

    def test_partial_and_present_but_invalid_inputs_have_explicit_warnings(self) -> None:
        partial = self.renderer.render(
            self.builder.build(
                weekend_result(
                    listing("listing-1", 1, SATURDAY, optional=False)
                )
            )
        )
        insufficient = self.renderer.render(
            self.builder.build(
                WeekendListingsModule(WeekendWindow(SATURDAY, MONDAY)).analyse(
                    IntelligenceContext(
                        collection=({"release_id": "invalid"},),
                        marketplace_snapshot=snapshot(),
                    )
                )
            )
        )

        self.assertIn("partial evidence", partial.headline)
        self.assertIn("Insufficient data", insufficient.headline)

    def test_renderer_contains_no_desirability_wording_or_calculations(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src/dip/experience/desktop/weekend_listings_renderer.py"
        ).read_text(encoding="utf-8").lower()
        for forbidden in (
            "good deal",
            "bargain",
            "buy now",
            "underpriced",
            "recommended",
            "expected profit",
        ):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("candidate.price +", source)


class WeekendListingsExplorerIntegrationTestCase(unittest.TestCase):
    def test_weekend_listings_is_fifth_and_overview_remains_selected(self) -> None:
        result = weekend_result(listing("listing-1", 1, SATURDAY))
        rendered = controller().open(
            available_homepage(),
            weekend_listings_result=result,
        )

        self.assertEqual(
            tuple(section.destination for section in rendered.sections),
            tuple(CollectionExplorerDestination),
        )
        self.assertIs(
            rendered.sections[4].destination,
            CollectionExplorerDestination.WEEKEND_LISTINGS,
        )
        self.assertIs(rendered.selected_destination, CollectionExplorerDestination.OVERVIEW)
        self.assertIn("Listing ID: listing-1", rendered.sections[4].body)

    def test_result_is_consumed_once_and_repeated_destination_access_does_no_work(self) -> None:
        result = weekend_result(listing("listing-1", 1, SATURDAY))
        real = explorer_service()

        class RecordingPresentation:
            def __init__(self) -> None:
                self.calls = []

            def explorer_for_homepage(
                self,
                homepage,
                *,
                selected_destination,
                weekend_listings_result=None,
            ):
                self.calls.append(weekend_listings_result)
                return real.explorer_for_homepage(
                    homepage,
                    selected_destination=selected_destination,
                    weekend_listings_result=weekend_listings_result,
                )

        presentation = RecordingPresentation()
        rendered = DesktopCollectionExplorerController(presentation).open(
            available_homepage(),
            weekend_listings_result=result,
        )
        for _ in range(3):
            for destination in CollectionExplorerDestination:
                next(
                    section
                    for section in rendered.sections
                    if section.destination is destination
                )

        self.assertEqual(presentation.calls, [result])

    def test_unavailable_is_usable_and_partial_result_makes_explorer_partial(self) -> None:
        unavailable = controller().open(available_homepage())
        partial = controller().open(
            available_homepage(),
            weekend_listings_result=weekend_result(
                listing("listing-1", 1, SATURDAY, optional=False)
            ),
        )

        self.assertIs(unavailable.state, CollectionExplorerState.AVAILABLE)
        self.assertIs(
            unavailable.navigation[4].state,
            CollectionExplorerState.UNAVAILABLE,
        )
        self.assertIs(partial.state, CollectionExplorerState.PARTIAL)
        self.assertIs(partial.navigation[4].state, CollectionExplorerState.PARTIAL)

    def test_presentation_and_renderer_have_no_module_persistence_or_network_imports(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = (
            root / "src/dip/app/weekend_listings_presentation.py",
            root / "src/dip/experience/weekend_listings/models.py",
            root / "src/dip/experience/weekend_listings/builder.py",
            root / "src/dip/experience/desktop/weekend_listings_renderer.py",
        )
        for path in files:
            source = path.read_text(encoding="utf-8")
            for forbidden in (
                "WeekendListingsModule",
                "dip.persistence",
                "sqlite3",
                "requests",
                "urllib",
            ):
                self.assertNotIn(forbidden, source)


def weekend_result(*listings):
    source = snapshot(*listings)
    collection = tuple(
        {
            "release_id": release_id,
            "artist": f"Artist {release_id}",
            "title": f"Title {release_id}",
        }
        for release_id in sorted({value.release_id for value in listings} or {1})
    )
    return WeekendListingsModule(WeekendWindow(SATURDAY, MONDAY)).analyse(
        IntelligenceContext(
            collection=collection,
            marketplace_snapshot=source,
        )
    )


def explorer_service() -> CollectionExplorerPresentationService:
    return CollectionExplorerPresentationService(
        CollectionHealthPresentationService(CollectionHealthDetailViewModelBuilder()),
        HiddenGemsPresentationService(HiddenGemsDetailViewModelBuilder()),
        CollectionExplorerViewModelBuilder(),
        weekend_listings=WeekendListingsPresentationService(
            WeekendListingsDetailViewModelBuilder()
        ),
    )


def controller() -> DesktopCollectionExplorerController:
    return DesktopCollectionExplorerController(
        explorer_service(),
        DesktopCollectionExplorerRenderer(),
    )


if __name__ == "__main__":
    unittest.main()
