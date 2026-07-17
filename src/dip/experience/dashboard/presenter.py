"""Map intelligence results into presentation-neutral dashboard cards."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import math
from typing import Any

from dip.intelligence.models import (
    IntelligenceExecution,
    IntelligenceResult,
    IntelligenceStatus,
)

from .models import (
    DashboardCardState,
    DashboardCardViewModel,
    DashboardComponentScore,
    IntelligenceDashboardViewModel,
)


class CollectionHealthCardPresenter:
    """Create a dashboard card without calculating Collection Health."""

    module_id = "collection_health"
    title = "Collection Health"

    _COMPONENTS = (
        ("metadata_completeness", "Metadata completeness"),
        ("marketplace_coverage", "Marketplace coverage"),
        ("demand_strength", "Demand strength"),
        ("valuation_coverage", "Valuation coverage"),
    )

    def present(self, result: IntelligenceResult) -> DashboardCardViewModel:
        if result.module_id != self.module_id:
            raise ValueError(
                "CollectionHealthCardPresenter requires a collection_health result."
            )

        if result.status == IntelligenceStatus.FAILED:
            return self._failed_card(result)

        score = self._score(result.metrics.get("overall_health_score"))
        components, missing_components = self._components(
            result.metrics.get("component_scores")
        )
        strengths = self._text_items(result.metrics.get("strengths"))
        opportunities = self._text_items(
            result.metrics.get("improvement_opportunities")
        )
        diagnostics = tuple(result.diagnostics)

        if result.status == IntelligenceStatus.SKIPPED:
            state = DashboardCardState.SKIPPED
        elif score is None or missing_components:
            state = DashboardCardState.INCOMPLETE
            diagnostics += (
                "Collection Health result is incomplete; one or more required "
                "dashboard metrics are unavailable or invalid.",
            )
        else:
            state = DashboardCardState.READY

        return DashboardCardViewModel(
            module_id=result.module_id,
            title=self.title,
            state=state,
            headline_label="Overall health score",
            headline_score=score,
            summary=result.summary,
            components=components,
            strengths=strengths,
            improvement_opportunities=opportunities,
            evidence=tuple(result.evidence),
            diagnostics=diagnostics,
        )

    def _failed_card(
        self,
        result: IntelligenceResult,
    ) -> DashboardCardViewModel:
        return DashboardCardViewModel(
            module_id=result.module_id,
            title=self.title,
            state=DashboardCardState.FAILED,
            headline_label="Overall health score",
            headline_score=None,
            summary=result.summary,
            evidence=tuple(result.evidence),
            diagnostics=tuple(result.diagnostics),
        )

    def _components(
        self,
        raw_components: Any,
    ) -> tuple[tuple[DashboardComponentScore, ...], bool]:
        if not isinstance(raw_components, Mapping):
            return (), True

        components: list[DashboardComponentScore] = []
        missing = False

        for key, label in self._COMPONENTS:
            score = self._score(raw_components.get(key))

            if score is None:
                missing = True
                continue

            components.append(
                DashboardComponentScore(
                    key=key,
                    label=label,
                    score=score,
                )
            )

        return tuple(components), missing

    @staticmethod
    def _score(value: Any) -> float | None:
        if isinstance(value, bool):
            return None

        try:
            score = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(score) or not 0 <= score <= 100:
            return None

        return score

    @staticmethod
    def _text_items(value: Any) -> tuple[str, ...]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return ()

        return tuple(
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        )


class IntelligenceDashboardPresenter:
    """Build the current dashboard slice from engine results."""

    def __init__(
        self,
        collection_health: CollectionHealthCardPresenter | None = None,
    ) -> None:
        self.collection_health = (
            collection_health or CollectionHealthCardPresenter()
        )

    def present(
        self,
        intelligence: IntelligenceExecution | Iterable[IntelligenceResult],
    ) -> IntelligenceDashboardViewModel:
        results = (
            intelligence.results
            if isinstance(intelligence, IntelligenceExecution)
            else tuple(intelligence)
        )
        cards = tuple(
            self.collection_health.present(result)
            for result in results
            if result.module_id == self.collection_health.module_id
        )

        return IntelligenceDashboardViewModel(cards=cards)
