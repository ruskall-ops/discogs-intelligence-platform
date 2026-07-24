"""Dedicated rendering of already-produced immutable Insight collections."""

from dataclasses import dataclass

from dip.experience.intelligence_insights import IntelligenceInsightCollection


@dataclass(frozen=True)
class DesktopIntelligenceInsightsSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopIntelligenceInsightsView:
    title: str
    sections: tuple[DesktopIntelligenceInsightsSection, ...]


class DesktopIntelligenceInsightsRenderer:
    def render(self, collections):
        collections = tuple(collections)
        if any(type(value) is not IntelligenceInsightCollection for value in collections):
            raise TypeError("collections must contain IntelligenceInsightCollection values.")
        if not collections:
            return DesktopIntelligenceInsightsView(
                "Intelligence Insights",
                (DesktopIntelligenceInsightsSection("Insights", "No insights."),),
            )
        sections = tuple(
            DesktopIntelligenceInsightsSection(
                _label(collection.category.value) if collection.category else "Insights",
                "\n\n".join(_insight(value) for value in collection.insights)
                if collection.insights else collection.message,
            )
            for collection in collections
        )
        return DesktopIntelligenceInsightsView("Intelligence Insights", sections)


class DesktopIntelligenceInsightsController:
    def __init__(self, renderer=None):
        self._renderer = renderer or DesktopIntelligenceInsightsRenderer()

    def open(self, collections=()):
        return self._renderer.render(collections)


def _insight(value):
    return "\n".join((
        value.title,
        value.summary,
        f"Priority: {_label(value.priority.value)}",
        f"Category: {_label(value.category.value)}",
        f"Type: {_label(value.insight_type.value)}",
        f"Evidence: {'; '.join(f'{item.label}: {_values(item.values)}' for item in value.evidence)}",
        f"Reasons: {_values(value.reason_codes)}",
        f"Diagnostics: {_values(value.diagnostics)}",
        f"Source: {value.source}",
        f"Provenance: {value.provenance}",
    ))


def _values(values):
    return ", ".join(str(value.value) if hasattr(value, "value") else str(value) for value in values) or "none"


def _label(value):
    return value.replace("_", " ").title()


__all__ = [
    "DesktopIntelligenceInsightsController", "DesktopIntelligenceInsightsRenderer",
    "DesktopIntelligenceInsightsSection", "DesktopIntelligenceInsightsView",
]
