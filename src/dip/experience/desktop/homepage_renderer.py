"""Tkinter-neutral text rendering for Dashboard homepage sections."""

from __future__ import annotations

from dataclasses import dataclass

from dip.experience.dashboard import (
    DashboardChangeSummaryViewModel,
    DashboardCollectionHealthViewModel,
    DashboardCollectionOverviewViewModel,
    DashboardExecutionViewModel,
    DashboardHiddenGemsViewModel,
    DashboardHomepageSection,
    DashboardHomepageViewModel,
    DashboardSectionId,
    DashboardSectionState,
    IntelligenceDashboardViewModel,
)

from .dashboard_renderer import DesktopDashboardRenderer


@dataclass(frozen=True)
class DesktopDashboardHomepageSection:
    """One rendered section ready for the existing Tkinter labels."""

    section_id: DashboardSectionId
    title: str
    body: str


class DesktopDashboardHomepageRenderer:
    """Format homepage ViewModels without domain, repository, or SQLite access."""

    def __init__(
        self,
        intelligence_cards: DesktopDashboardRenderer | None = None,
    ) -> None:
        self._intelligence_cards = intelligence_cards or DesktopDashboardRenderer()

    def render(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> tuple[DesktopDashboardHomepageSection, ...]:
        """Render all sections in their validated homepage order."""

        if type(homepage) is not DashboardHomepageViewModel:
            raise TypeError("homepage must be a DashboardHomepageViewModel.")
        return tuple(self._render_section(section) for section in homepage.sections)

    def _render_section(
        self,
        section: DashboardHomepageSection,
    ) -> DesktopDashboardHomepageSection:
        if type(section) is DashboardCollectionOverviewViewModel:
            body = self._overview(section)
        elif type(section) is DashboardCollectionHealthViewModel:
            body = self._collection_health(section)
        elif type(section) is DashboardHiddenGemsViewModel:
            body = self._hidden_gems(section)
        elif type(section) is DashboardChangeSummaryViewModel:
            body = self._changes(section)
        elif type(section) is DashboardExecutionViewModel:
            body = self._execution(section)
        else:
            raise TypeError("Unsupported Dashboard homepage section.")
        return DesktopDashboardHomepageSection(
            section_id=section.section_id,
            title=section.title,
            body=body,
        )

    @staticmethod
    def _overview(section: DashboardCollectionOverviewViewModel) -> str:
        state_message = _state_message(section.state, section.summary)
        if state_message is not None:
            return state_message
        collection_size = (
            f"{section.collection_size:,}"
            if section.collection_size is not None
            else "Unavailable"
        )
        return "\n".join(
            (
                f"Collection size: {collection_size}",
                f"Current status: {section.current_status.value.title()}",
                (
                    "Completed modules: "
                    f"{section.completed_module_count}/{section.total_module_count}"
                ),
                f"Latest execution: {_date(section.latest_executed_at)}",
            )
        )

    def _collection_health(
        self,
        section: DashboardCollectionHealthViewModel,
    ) -> str:
        if section.state is DashboardSectionState.LOADING:
            return "Collection Health is loading."
        if section.card is None:
            return "Collection Health is unavailable."
        rendered = self._intelligence_cards.render(
            IntelligenceDashboardViewModel(cards=(section.card,))
        )
        return rendered[0].body

    @staticmethod
    def _hidden_gems(section: DashboardHiddenGemsViewModel) -> str:
        if section.state is DashboardSectionState.LOADING:
            return "Hidden Gems are loading."
        if section.card is None:
            return "Hidden Gems intelligence is unavailable."
        if section.state is DashboardSectionState.EMPTY:
            return "\n".join(("No Hidden Gems qualify.", section.card.summary))
        state_message = _state_message(section.state, section.card.summary)
        if state_message is not None:
            return state_message
        lines = [
            f"Qualifying Hidden Gems: {section.card.total_hidden_gems}",
            section.card.summary,
        ]
        if section.preview:
            lines.append("Highest-ranked candidates")
            lines.extend(
                f"• {release.artist} — {release.title}: {release.explanation}"
                for release in section.preview
            )
        return "\n".join(lines)

    @staticmethod
    def _changes(section: DashboardChangeSummaryViewModel) -> str:
        state_message = _state_message(section.state, section.summary)
        if state_message is not None:
            return state_message
        lines = [
            section.summary,
            (
                f"Changed {section.changed_module_count} • "
                f"Unchanged {section.unchanged_module_count} • "
                f"Added {section.added_module_count} • "
                f"Removed {section.removed_module_count}"
            ),
        ]
        if section.changed_modules:
            lines.append("Changed modules")
            lines.extend(
                f"• {module.label} — {module.state.value.title()}"
                for module in section.changed_modules
            )
        return "\n".join(lines)

    @staticmethod
    def _execution(section: DashboardExecutionViewModel) -> str:
        state_message = _state_message(section.state, section.summary)
        if state_message is not None:
            return state_message
        status = "Successful" if section.successful else "Unavailable"
        return "\n".join(
            (
                f"Executed: {_date(section.executed_at)}",
                f"Modules: {section.module_count}",
                f"Engine version: {section.engine_version or 'Unavailable'}",
                f"Status: {status}",
            )
        )


def _state_message(state: DashboardSectionState, summary: str) -> str | None:
    labels = {
        DashboardSectionState.LOADING: "Loading",
        DashboardSectionState.EMPTY: "No intelligence history",
        DashboardSectionState.UNAVAILABLE: "Unavailable",
        DashboardSectionState.ERROR: "Unable to display",
        DashboardSectionState.INSUFFICIENT_HISTORY: "Insufficient history",
    }
    label = labels.get(state)
    return None if label is None else f"{label}\n{summary}"


def _date(value) -> str:
    return value.strftime("%d %b %Y %H:%M") if value is not None else "Unavailable"


__all__ = [
    "DesktopDashboardHomepageRenderer",
    "DesktopDashboardHomepageSection",
]
