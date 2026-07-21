from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest

from dip.app.intelligence_context import IntelligenceContextFactory
from dip.experience.dashboard import (
    DashboardCardState,
    HiddenGemsCardPresenter,
    HiddenGemsCardViewModel,
    HistoricalIntelligenceCardPresenter,
    HistoricalIntelligenceCardViewModel,
    IntelligenceDashboardPresenter,
)
from dip.experience.desktop.dashboard_renderer import DesktopDashboardRenderer
from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus
from dip.intelligence.modules import HiddenGemsModule, HistoricalIntelligenceModule


def release(release_id: int, artist: str = "Artist", title: str = "Title"):
    return {
        "release_id": release_id,
        "artist": artist,
        "title": title,
        "label": "Label",
        "quantity": 1,
    }


def market(wants=200, supply=2, rating=4.5, price=10):
    return {
        "wants": wants,
        "copies_for_sale": supply,
        "community_rating": rating,
        "lowest_price": price,
    }


def snapshot(release_id: int, value: int, timestamp: str, artist="Artist", title="Title"):
    return {
        "release_id": release_id,
        "lowest_price": value,
        "captured_at": timestamp,
        "artist": artist,
        "title": title,
    }


class HiddenGemsDashboardTests(unittest.TestCase):
    def test_completed_result_maps_top_five_without_raw_scores(self) -> None:
        collection = tuple(
            release(index, f"Artist {index}", f"Title {index}")
            for index in range(1, 7)
        )
        result = HiddenGemsModule().analyse(
            IntelligenceContext(
                collection=collection,
                marketplace={index: market() for index in range(1, 7)},
            )
        )

        card = HiddenGemsCardPresenter().present(result)

        self.assertIsInstance(card, HiddenGemsCardViewModel)
        self.assertEqual(card.state, DashboardCardState.READY)
        self.assertEqual(card.total_hidden_gems, 6)
        self.assertEqual(len(card.top_gems), 5)
        self.assertEqual(card.top_gems[0].release_id, 1)
        self.assertFalse(hasattr(card.top_gems[0], "hidden_gem_score"))
        self.assertIn("Demand is", card.top_gems[0].explanation)
        with self.assertRaises(FrozenInstanceError):
            card.total_hidden_gems = 99  # type: ignore[misc]

    def test_failed_hidden_gems_result_is_safe(self) -> None:
        result = IntelligenceResult(
            module_id="hidden_gems",
            status=IntelligenceStatus.FAILED,
            summary="Hidden Gems failed.",
            diagnostics=("controlled",),
        )
        card = HiddenGemsCardPresenter().present(result)
        self.assertEqual(card.state, DashboardCardState.FAILED)
        self.assertEqual(card.top_gems, ())


class HistoricalDashboardTests(unittest.TestCase):
    def test_completed_result_maps_dates_changes_rankings_and_coverage(self) -> None:
        result = HistoricalIntelligenceModule().analyse(
            IntelligenceContext(
                history={
                    1: (
                        snapshot(1, 10, "2026-07-01T10:00:00Z", "A", "One"),
                        snapshot(2, 20, "2026-07-01T10:00:00Z", "B", "Two"),
                    ),
                    2: (
                        snapshot(1, 15, "2026-07-08T10:00:00Z", "A", "One"),
                        snapshot(3, 30, "2026-07-08T10:00:00Z", "C", "Three"),
                    ),
                }
            )
        )

        card = HistoricalIntelligenceCardPresenter().present(result)

        self.assertIsInstance(card, HistoricalIntelligenceCardViewModel)
        self.assertEqual(card.state, DashboardCardState.READY)
        self.assertEqual(card.latest_snapshot_date, "08 Jul 2026 10:00")
        self.assertEqual(card.previous_snapshot_date, "01 Jul 2026 10:00")
        self.assertEqual(card.releases_added, 1)
        self.assertEqual(card.releases_removed, 1)
        self.assertEqual(card.collection_size_change, 0)
        self.assertEqual(card.collection_value_change, "+£15.00")
        self.assertEqual(card.average_value_change, "+£7.50")
        self.assertEqual(card.median_value_change, "+£7.50")
        self.assertEqual(card.top_gainers[0].change, "+£5.00")
        self.assertEqual(card.top_decliners, ())
        self.assertIn("previous 2/2", card.evidence_coverage_summary)

    def test_insufficient_history_is_informational(self) -> None:
        result = HistoricalIntelligenceModule().analyse(
            IntelligenceContext(history={1: (snapshot(1, 10, "2026-07-01T10:00:00Z"),)})
        )
        card = HistoricalIntelligenceCardPresenter().present(result)
        self.assertEqual(card.state, DashboardCardState.INSUFFICIENT_HISTORY)
        self.assertIn("fewer than two", card.summary)

    def test_failed_historical_result_is_safe(self) -> None:
        card = HistoricalIntelligenceCardPresenter().present(
            IntelligenceResult(
                module_id="historical_intelligence",
                status=IntelligenceStatus.FAILED,
                summary="Historical Intelligence failed.",
            )
        )
        self.assertEqual(card.state, DashboardCardState.FAILED)


class UnifiedDashboardTests(unittest.TestCase):
    def test_empty_intelligence_produces_three_unavailable_cards(self) -> None:
        dashboard = IntelligenceDashboardPresenter().present(())
        self.assertEqual(
            tuple(card.module_id for card in dashboard.cards),
            ("collection_health", "hidden_gems", "historical_intelligence"),
        )
        self.assertTrue(all(card.state == DashboardCardState.UNAVAILABLE for card in dashboard.cards))

    def test_one_presenter_failure_does_not_prevent_other_cards(self) -> None:
        class ExplodingHiddenGemsPresenter(HiddenGemsCardPresenter):
            def present(self, result):
                raise RuntimeError("controlled display failure")

        hidden_result = HiddenGemsModule().analyse(
            IntelligenceContext(collection=(release(1),), marketplace={1: market()})
        )
        historical_result = HistoricalIntelligenceModule().analyse(IntelligenceContext())
        dashboard = IntelligenceDashboardPresenter(
            hidden_gems=ExplodingHiddenGemsPresenter()
        ).present((hidden_result, historical_result))

        self.assertEqual(dashboard.card_for("hidden_gems").state, DashboardCardState.FAILED)
        self.assertEqual(
            dashboard.card_for("historical_intelligence").state,
            DashboardCardState.INSUFFICIENT_HISTORY,
        )
        self.assertEqual(
            dashboard.card_for("collection_health").state,
            DashboardCardState.UNAVAILABLE,
        )

    def test_desktop_renderer_renders_all_three_cards(self) -> None:
        hidden = HiddenGemsModule().analyse(
            IntelligenceContext(collection=(release(1),), marketplace={1: market()})
        )
        history = HistoricalIntelligenceModule().analyse(IntelligenceContext())
        dashboard = IntelligenceDashboardPresenter().present((hidden, history))
        rendered = DesktopDashboardRenderer().render(dashboard)

        self.assertEqual(len(rendered), 3)
        self.assertIn("Total hidden gems: 1", rendered[1].body)
        self.assertIn("Insufficient history", rendered[2].body)


class FakeRepository:
    def review_rows(self, *, limit):
        return [release(1, "Prepared Artist", "Prepared Title")]

    def latest_completed_analysis_run(self):
        return {"id": 2}

    def previous_completed_analysis_run(self, before_run_id):
        return {"id": 1}

    def snapshots_for_analysis_run(self, run_id):
        return [
            {
                "release_id": 1,
                "captured_at": f"2026-07-0{run_id}T10:00:00Z",
                "lowest_price": Decimal(str(run_id * 10)),
                "wants": 100,
                "copies_for_sale": 2,
            }
        ]


class IntelligenceContextFactoryTests(unittest.TestCase):
    def test_application_layer_prepares_current_and_historical_evidence(self) -> None:
        context = IntelligenceContextFactory(FakeRepository()).build()
        self.assertEqual(context.analysis_run_id, 2)
        self.assertEqual(tuple(context.history), (2, 1))
        self.assertEqual(context.marketplace[1]["lowest_price"], Decimal("20"))
        self.assertEqual(context.history[1][0]["artist"], "Prepared Artist")


if __name__ == "__main__":
    unittest.main()
