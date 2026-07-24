from dataclasses import FrozenInstanceError
import unittest

from dip.app import MarketplaceWorkspacePresentationService
from dip.experience.desktop.marketplace_workspace_renderer import DesktopMarketplaceWorkspaceController
from dip.experience.history_explorer import HistoryExplorerStateBuilder
from dip.experience.intelligence_insights import SnapshotInsightGenerator
from dip.experience.marketplace_opportunity import MarketplaceOpportunityDetailViewModel
from dip.experience.marketplace_workspace import (
    MarketplaceAttentionItemViewModel,
    MarketplaceEvidenceSectionViewModel,
    MarketplacePortfolioContextViewModel,
    MarketplaceResearchStatus,
    MarketplaceWorkspaceAvailability,
    MarketplaceWorkspaceFilters,
    MarketplaceWorkspacePane,
    MarketplaceWorkspaceStateBuilder,
)
from tests.test_history_explorer import supplied_view_models


def queue():
    snapshots, changes, trends = supplied_view_models()
    history = HistoryExplorerStateBuilder().build(snapshots, changes, trends)
    insights = (SnapshotInsightGenerator().generate(snapshots[0]),)
    evidence = (
        MarketplaceEvidenceSectionViewModel("marketplace", "Marketplace", ("assessment supplied",)),
        MarketplaceEvidenceSectionViewModel("supply", "Supply", ("supply evidence",)),
        MarketplaceEvidenceSectionViewModel("portfolio", "Portfolio", ("ownership evidence",)),
    )
    portfolio = MarketplacePortfolioContextViewModel(
        True, 2, "selectively aligned", "not supplied", "duplicate copies",
        "intermediate", "complete", "portfolio provenance",
    )
    first = MarketplaceAttentionItemViewModel(
        20, "Beta", "Second", "Label B", "balanced", "complete", "balanced",
        "Observed evidence is available.", ("reason-b",), (), True, True,
        MarketplaceResearchStatus.UNREVIEWED,
        MarketplaceOpportunityDetailViewModel.unavailable(), evidence, history,
        insights, portfolio, "marketplace provenance", "rules 1.0",
    )
    second = MarketplaceAttentionItemViewModel(
        10, "Alpha", "First", "Label A", "developing", "partial", "developing",
        "Observed evidence is partial.", ("reason-a",), ("diagnostic-a",), False, False,
        MarketplaceResearchStatus.REVIEWING,
        MarketplaceOpportunityDetailViewModel.unavailable(), evidence, None,
        (), MarketplacePortfolioContextViewModel(False, 0), "other provenance", "rules 1.0",
    )
    return first, second


class MarketplaceWorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        self.builder = MarketplaceWorkspaceStateBuilder()
        self.presentation = MarketplaceWorkspacePresentationService(self.builder)

    def test_construction_selection_and_queue_order_are_caller_owned(self):
        supplied = queue()
        state = self.presentation.workspace(supplied)
        self.assertEqual(tuple(value.release_id for value in state.queue), (20, 10))
        self.assertEqual(tuple(value.release_id for value in state.filtered_queue), (20, 10))
        self.assertEqual(state.selected_release_id, 20)
        selected = self.presentation.select(state, 10, pane=MarketplaceWorkspacePane.EVIDENCE)
        self.assertEqual(selected.selected_release_id, 10)
        self.assertIs(selected.current_pane, MarketplaceWorkspacePane.EVIDENCE)
        self.assertEqual(state.selected_release_id, 20)

    def test_identity_and_workflow_filters_preserve_relative_order(self):
        supplied = queue()
        filters = (
            MarketplaceWorkspaceFilters(research_status=MarketplaceResearchStatus.REVIEWING),
            MarketplaceWorkspaceFilters(marketplace_assessment="developing"),
            MarketplaceWorkspaceFilters(evidence_state="partial"),
            MarketplaceWorkspaceFilters(artist="Alpha"),
            MarketplaceWorkspaceFilters(label="Label A"),
            MarketplaceWorkspaceFilters(owned=False),
            MarketplaceWorkspaceFilters(release_id=10),
            MarketplaceWorkspaceFilters(history_available=False),
            MarketplaceWorkspaceFilters(trend_available=False),
        )
        for value in filters:
            with self.subTest(filters=value):
                state = self.presentation.workspace(supplied, filters=value)
                self.assertEqual(tuple(item.release_id for item in state.filtered_queue), (10,))

    def test_research_status_is_user_owned_immutable_state(self):
        state = self.presentation.workspace(queue())
        updated = self.presentation.set_research_status(
            state, 20, MarketplaceResearchStatus.RESEARCHED
        )
        self.assertIs(updated.current_pane, MarketplaceWorkspacePane.RESEARCH_STATUS)
        self.assertIs(updated.filtered_queue[0].research_status, MarketplaceResearchStatus.RESEARCHED)
        self.assertIs(state.filtered_queue[0].research_status, MarketplaceResearchStatus.UNREVIEWED)
        with self.assertRaises(FrozenInstanceError):
            updated.selected_release_id = 10

    def test_renderer_integrates_detail_evidence_history_insights_and_portfolio(self):
        rendered = DesktopMarketplaceWorkspaceController(self.presentation).open(queue())
        self.assertEqual(
            tuple(value.title for value in rendered.sections),
            (
                "Attention Queue", "Opportunity Detail", "Evidence",
                "Marketplace History", "Portfolio Context", "Research Status",
            ),
        )
        body = "\n".join(value.body for value in rendered.sections)
        self.assertLess(body.index("Release 20"), body.index("Release 10"))
        for expected in (
            "Marketplace\nassessment supplied", "Timeline", "Insights:\nSnapshot",
            "Owned copies: 2", "Research status: Unreviewed",
            "Reasons:", "Diagnostics:", "Provenance:",
        ):
            self.assertIn(expected, body)
        for forbidden in ("should buy", "recommendation", "predicted"):
            self.assertNotIn(forbidden, body.lower())

    def test_empty_unavailable_and_missing_context_states(self):
        controller = DesktopMarketplaceWorkspaceController(self.presentation)
        empty = controller.open()
        self.assertIs(empty.availability, MarketplaceWorkspaceAvailability.EMPTY)
        self.assertEqual(empty.sections[0].body, "No opportunities supplied.")
        self.assertEqual(empty.sections[2].body, "No evidence.")
        self.assertEqual(empty.sections[3].body, "No history.")
        self.assertEqual(empty.sections[4].body, "No portfolio context.")
        unavailable = controller.open(available=False)
        self.assertIs(unavailable.availability, MarketplaceWorkspaceAvailability.UNAVAILABLE)
        self.assertEqual(unavailable.sections[0].body, "Workspace unavailable.")


if __name__ == "__main__":
    unittest.main()
