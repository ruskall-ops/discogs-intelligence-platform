"""Compatibility renderer for the original current-engine Explorer."""

from __future__ import annotations

from dataclasses import dataclass

from dip.experience.explorer import (
    CollectionHealthExplorerViewModel,
    CollectionIntelligenceExplorerViewModel,
    HiddenGemsExplorerViewModel,
    HistoricalIntelligenceExplorerViewModel,
    CollectionIntelligenceExplorerPresenter,
)
from dip.experience.dashboard import IntelligenceDashboardViewModel


@dataclass(frozen=True)
class DesktopExplorerSection:
    module_id: str
    title: str
    state: str
    body: str


@dataclass(frozen=True)
class DesktopExplorerView:
    title: str
    sections: tuple[DesktopExplorerSection, ...]


class DesktopExplorerRenderer:
    """Render presentation-ready Explorer sections as desktop text."""

    def render(
        self,
        explorer: CollectionIntelligenceExplorerViewModel,
    ) -> DesktopExplorerView:
        return DesktopExplorerView(
            title="Collection Intelligence Explorer",
            sections=tuple(
                self._render_section(section)
                for section in explorer.sections
            ),
        )

    def _render_section(self, section) -> DesktopExplorerSection:
        if isinstance(section, CollectionHealthExplorerViewModel):
            body = self._health(section)
        elif isinstance(section, HiddenGemsExplorerViewModel):
            body = self._hidden_gems(section)
        elif isinstance(section, HistoricalIntelligenceExplorerViewModel):
            body = self._historical(section)
        else:
            body = "Intelligence is unavailable."
        return DesktopExplorerSection(
            module_id=section.module_id,
            title=section.title,
            state=section.state.value,
            body=body,
        )

    def _health(self, section: CollectionHealthExplorerViewModel) -> str:
        score = (
            f"{section.overall_health:.1f}/100"
            if section.overall_health is not None
            else "Unavailable"
        )
        lines = [self._state(section.state.value), f"Overall health: {score}", section.summary]
        if section.component_scores:
            lines.append("Component scores")
            lines.extend(
                f"• {component.label}: {component.score:.1f}/100"
                for component in section.component_scores
            )
        lines.extend(self._items("Evidence", section.evidence))
        lines.extend(self._items("Diagnostics", section.diagnostics))
        return "\n".join(lines)

    def _hidden_gems(self, section: HiddenGemsExplorerViewModel) -> str:
        count = (
            str(section.total_hidden_gems)
            if section.total_hidden_gems is not None
            else "Unavailable"
        )
        lines = [self._state(section.state.value), f"Total hidden gems: {count}", section.summary]
        if section.ranked_releases:
            lines.append("Ranked releases")
            for index, release in enumerate(section.ranked_releases, start=1):
                lines.append(f"{index}. {release.artist} — {release.title}")
                if release.explanation:
                    lines.append(f"   {release.explanation}")
                lines.extend(f"   • {item}" for item in release.evidence)
        lines.extend(self._items("Diagnostics", section.diagnostics))
        return "\n".join(lines)

    def _historical(
        self,
        section: HistoricalIntelligenceExplorerViewModel,
    ) -> str:
        lines = [
            self._state(section.state.value),
            section.summary,
            f"Latest snapshot: {section.latest_snapshot or 'Unavailable'}",
            f"Previous snapshot: {section.previous_snapshot or 'Unavailable'}",
            f"Collection size change: {self._signed(section.collection_size_change)}",
            f"Collection value change: {section.collection_value_change or 'Unavailable'}",
            f"Average value change: {section.average_value_change or 'Unavailable'}",
            f"Median value change: {section.median_value_change or 'Unavailable'}",
            f"Releases added: {self._count(section.releases_added)}",
            f"Releases removed: {self._count(section.releases_removed)}",
        ]
        lines.extend(self._releases("Added releases", section.added_releases))
        lines.extend(self._releases("Removed releases", section.removed_releases))
        lines.extend(self._changes("Top gainers", section.top_gainers))
        lines.extend(self._changes("Top decliners", section.top_decliners))
        if section.evidence_coverage:
            lines.extend(("Evidence coverage", section.evidence_coverage))
        lines.extend(self._items("Diagnostics", section.diagnostics))
        return "\n".join(lines)

    @staticmethod
    def _state(value: str) -> str:
        return f"Status: {value.replace('_', ' ').title()}"

    @staticmethod
    def _items(title: str, items: tuple[str, ...]) -> list[str]:
        return [title, *(f"• {item}" for item in items)] if items else []

    @staticmethod
    def _releases(title: str, releases) -> list[str]:
        return (
            [title, *(f"• {item.artist} — {item.title}" for item in releases)]
            if releases
            else []
        )

    @staticmethod
    def _changes(title: str, releases) -> list[str]:
        return (
            [
                title,
                *(
                    f"• {item.artist} — {item.title}: {item.change}"
                    for item in releases
                ),
            ]
            if releases
            else []
        )

    @staticmethod
    def _signed(value: int | None) -> str:
        return "Unavailable" if value is None else f"{value:+d}"

    @staticmethod
    def _count(value: int | None) -> str:
        return "Unavailable" if value is None else str(value)


class DesktopExplorerController:
    """Preserve the prior controller API for compatibility clients."""

    def __init__(
        self,
        presenter: CollectionIntelligenceExplorerPresenter | None = None,
        renderer: DesktopExplorerRenderer | None = None,
    ) -> None:
        self.presenter = presenter or CollectionIntelligenceExplorerPresenter()
        self.renderer = renderer or DesktopExplorerRenderer()

    def open(
        self,
        dashboard: IntelligenceDashboardViewModel,
    ) -> DesktopExplorerView:
        return self.renderer.render(self.presenter.present(dashboard))
