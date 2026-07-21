"""Map intelligence results into presentation-neutral dashboard cards."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
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
    DashboardReleaseViewModel,
    HiddenGemsCardViewModel,
    HistoricalIntelligenceCardViewModel,
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

    def unavailable(self) -> DashboardCardViewModel:
        return DashboardCardViewModel(
            module_id=self.module_id,
            title=self.title,
            state=DashboardCardState.UNAVAILABLE,
            headline_label="Overall health score",
            headline_score=None,
            summary="Collection Health intelligence is unavailable.",
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


class HiddenGemsCardPresenter:
    """Map Hidden Gems results without exposing scoring internals."""

    module_id = "hidden_gems"
    title = "Hidden Gems"
    maximum_releases = 5

    def present(self, result: IntelligenceResult) -> HiddenGemsCardViewModel:
        if result.module_id != self.module_id:
            raise ValueError("HiddenGemsCardPresenter requires a hidden_gems result.")

        if result.status == IntelligenceStatus.FAILED:
            return self._card(
                DashboardCardState.FAILED,
                result.summary,
                diagnostics=tuple(result.diagnostics),
            )

        count = self._count(result.metrics.get("candidate_count"))
        releases, malformed = self._releases(
            result.metrics.get("ranked_candidates")
        )
        diagnostics = tuple(result.diagnostics)

        if result.status == IntelligenceStatus.SKIPPED:
            state = DashboardCardState.SKIPPED
        elif count is None or malformed:
            state = DashboardCardState.INCOMPLETE
            diagnostics += (
                "Hidden Gems result is incomplete; candidate presentation data "
                "is unavailable or invalid.",
            )
        else:
            state = DashboardCardState.READY

        return HiddenGemsCardViewModel(
            module_id=self.module_id,
            title=self.title,
            state=state,
            total_hidden_gems=count,
            summary=result.summary,
            top_gems=releases,
            explainability_summary=(
                "Each displayed release includes evidence supplied by the "
                "Hidden Gems intelligence result."
            ),
            diagnostics=diagnostics,
        )

    def unavailable(self) -> HiddenGemsCardViewModel:
        return self._card(
            DashboardCardState.UNAVAILABLE,
            "Hidden Gems intelligence is unavailable.",
        )

    def _card(
        self,
        state: DashboardCardState,
        summary: str,
        *,
        diagnostics: tuple[str, ...] = (),
    ) -> HiddenGemsCardViewModel:
        return HiddenGemsCardViewModel(
            module_id=self.module_id,
            title=self.title,
            state=state,
            total_hidden_gems=None,
            summary=summary,
            diagnostics=diagnostics,
        )

    def _releases(
        self,
        raw_candidates: Any,
    ) -> tuple[tuple[DashboardReleaseViewModel, ...], bool]:
        if not isinstance(raw_candidates, Sequence) or isinstance(
            raw_candidates, (str, bytes)
        ):
            return (), True

        releases: list[DashboardReleaseViewModel] = []
        malformed = False
        for candidate in raw_candidates[: self.maximum_releases]:
            release_id = self._release_id(getattr(candidate, "release_id", None))
            artist = self._text(getattr(candidate, "artist", None))
            title = self._text(getattr(candidate, "title", None))
            evidence = getattr(candidate, "evidence", ())
            if release_id is None or artist is None or title is None:
                malformed = True
                continue
            explanation = next(
                (
                    item.strip()
                    for item in evidence
                    if isinstance(item, str) and item.strip()
                ),
                "Module evidence is available in the intelligence result.",
            )
            releases.append(
                DashboardReleaseViewModel(
                    release_id=release_id,
                    artist=artist,
                    title=title,
                    explanation=explanation,
                )
            )
        return tuple(releases), malformed

    @staticmethod
    def _count(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    @staticmethod
    def _release_id(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    @staticmethod
    def _text(value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None


class HistoricalIntelligenceCardPresenter:
    """Map Historical Intelligence results into display-safe fields."""

    module_id = "historical_intelligence"
    title = "Historical Intelligence"
    maximum_releases = 5

    def present(
        self,
        result: IntelligenceResult,
    ) -> HistoricalIntelligenceCardViewModel:
        if result.module_id != self.module_id:
            raise ValueError(
                "HistoricalIntelligenceCardPresenter requires a "
                "historical_intelligence result."
            )

        if result.status == IntelligenceStatus.FAILED:
            return self._card(
                DashboardCardState.FAILED,
                result.summary,
                diagnostics=tuple(result.diagnostics),
            )
        if result.status == IntelligenceStatus.SKIPPED:
            return self._card(
                DashboardCardState.INSUFFICIENT_HISTORY,
                result.summary,
                diagnostics=tuple(result.diagnostics),
            )

        comparison = result.metrics.get("comparison")
        if comparison is None:
            return self._card(
                DashboardCardState.INCOMPLETE,
                result.summary,
                diagnostics=tuple(result.diagnostics) + (
                    "Historical Intelligence comparison data is unavailable.",
                ),
            )

        previous = getattr(comparison, "previous_snapshot", None)
        current = getattr(comparison, "current_snapshot", None)
        required = (
            previous,
            current,
            getattr(comparison, "previous_collection_size", None),
            getattr(comparison, "current_collection_size", None),
        )
        state = (
            DashboardCardState.READY
            if all(item is not None for item in required)
            else DashboardCardState.INCOMPLETE
        )
        diagnostics = tuple(result.diagnostics)
        if state == DashboardCardState.INCOMPLETE:
            diagnostics += ("Historical Intelligence result is incomplete.",)

        return HistoricalIntelligenceCardViewModel(
            module_id=self.module_id,
            title=self.title,
            state=state,
            summary=result.summary,
            latest_snapshot_date=self._date(getattr(current, "timestamp", None)),
            previous_snapshot_date=self._date(getattr(previous, "timestamp", None)),
            releases_added=self._integer(getattr(comparison, "additions_count", None)),
            releases_removed=self._integer(getattr(comparison, "removals_count", None)),
            collection_size_change=self._signed_integer(
                getattr(comparison, "collection_size_change", None)
            ),
            collection_value_change=self._money(
                getattr(comparison, "total_estimated_value_change", None)
            ),
            average_value_change=self._money(
                getattr(comparison, "average_release_value_change", None)
            ),
            median_value_change=self._money(
                getattr(comparison, "median_release_value_change", None)
            ),
            top_gainers=self._changes(
                getattr(comparison, "largest_gainers", ())
            ),
            top_decliners=self._changes(
                getattr(comparison, "largest_decliners", ())
            ),
            evidence_coverage_summary=self._coverage(previous, current),
            diagnostics=diagnostics,
        )

    def unavailable(self) -> HistoricalIntelligenceCardViewModel:
        return self._card(
            DashboardCardState.UNAVAILABLE,
            "Historical Intelligence is unavailable.",
        )

    def _card(
        self,
        state: DashboardCardState,
        summary: str,
        *,
        diagnostics: tuple[str, ...] = (),
    ) -> HistoricalIntelligenceCardViewModel:
        return HistoricalIntelligenceCardViewModel(
            module_id=self.module_id,
            title=self.title,
            state=state,
            summary=summary,
            diagnostics=diagnostics,
        )

    def _changes(self, raw_changes: Any) -> tuple[DashboardReleaseViewModel, ...]:
        if not isinstance(raw_changes, Sequence) or isinstance(raw_changes, (str, bytes)):
            return ()
        releases = []
        for change in raw_changes[: self.maximum_releases]:
            release_id = HiddenGemsCardPresenter._release_id(
                getattr(change, "release_id", None)
            )
            artist = HiddenGemsCardPresenter._text(getattr(change, "artist", None))
            title = HiddenGemsCardPresenter._text(getattr(change, "title", None))
            formatted_change = self._money(getattr(change, "absolute_change", None))
            if release_id is None or artist is None or title is None or formatted_change is None:
                continue
            releases.append(DashboardReleaseViewModel(
                release_id=release_id,
                artist=artist,
                title=title,
                change=formatted_change,
            ))
        return tuple(releases)

    @staticmethod
    def _date(value: Any) -> str | None:
        return value.strftime("%d %b %Y %H:%M") if isinstance(value, datetime) else None

    @staticmethod
    def _integer(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    @staticmethod
    def _signed_integer(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _money(value: Any) -> str | None:
        if not isinstance(value, (Decimal, int, float)) or isinstance(value, bool):
            return None
        try:
            numeric = Decimal(str(value))
        except Exception:
            return None
        if not numeric.is_finite():
            return None
        sign = "+" if numeric > 0 else ""
        return f"{sign}£{numeric:,.2f}" if numeric >= 0 else f"-£{abs(numeric):,.2f}"

    @staticmethod
    def _coverage(previous: Any, current: Any) -> str:
        if previous is None or current is None:
            return "Valuation evidence coverage is unavailable."
        return (
            "Valuation evidence: previous "
            f"{getattr(previous, 'valued_release_count', '?')}/"
            f"{getattr(previous, 'collection_size', '?')} releases; latest "
            f"{getattr(current, 'valued_release_count', '?')}/"
            f"{getattr(current, 'collection_size', '?')} releases."
        )


class IntelligenceDashboardPresenter:
    """Build the current dashboard slice from engine results."""

    def __init__(
        self,
        collection_health: CollectionHealthCardPresenter | None = None,
        hidden_gems: HiddenGemsCardPresenter | None = None,
        historical_intelligence: HistoricalIntelligenceCardPresenter | None = None,
    ) -> None:
        self.collection_health = (
            collection_health or CollectionHealthCardPresenter()
        )
        self.hidden_gems = hidden_gems or HiddenGemsCardPresenter()
        self.historical_intelligence = (
            historical_intelligence or HistoricalIntelligenceCardPresenter()
        )
        self._presenters = (
            self.collection_health,
            self.hidden_gems,
            self.historical_intelligence,
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
        by_module = {result.module_id: result for result in results}
        cards = tuple(
            self._present_safely(presenter, by_module.get(presenter.module_id))
            for presenter in self._presenters
        )

        return IntelligenceDashboardViewModel(cards=cards)

    @staticmethod
    def _present_safely(presenter: Any, result: IntelligenceResult | None):
        if result is None:
            return presenter.unavailable()
        try:
            return presenter.present(result)
        except Exception as exc:
            card = presenter.unavailable()
            return replace(
                card,
                state=DashboardCardState.FAILED,
                summary=f"{presenter.title} could not be displayed.",
                diagnostics=(f"{type(exc).__name__}: {exc}",),
            )
