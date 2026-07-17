"""Explainable Collection Health analysis for Version 0.2."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from dip.intelligence.context import IntelligenceContext
from dip.intelligence.models import IntelligenceResult, IntelligenceStatus


@dataclass(frozen=True)
class CollectionHealthWeights:
    """Explicit component weights used by the overall health score."""

    metadata_completeness: float = 0.25
    marketplace_coverage: float = 0.25
    demand_strength: float = 0.30
    valuation_coverage: float = 0.20

    def as_dict(self) -> dict[str, float]:
        return {
            "metadata_completeness": self.metadata_completeness,
            "marketplace_coverage": self.marketplace_coverage,
            "demand_strength": self.demand_strength,
            "valuation_coverage": self.valuation_coverage,
        }


@dataclass(frozen=True)
class CollectionHealthConfig:
    """Configurable, deterministic rules for Collection Health."""

    weights: CollectionHealthWeights = CollectionHealthWeights()
    metadata_fields: tuple[str, ...] = ("artist", "title", "label")
    demand_ratio_for_full_score: float = 20.0
    strength_threshold: float = 75.0
    improvement_threshold: float = 60.0


class CollectionHealthModule:
    """Assess collection evidence without accessing providers or persistence."""

    module_id = "collection_health"
    module_version = "1.0"

    _COMPONENT_LABELS = {
        "metadata_completeness": "Metadata completeness",
        "marketplace_coverage": "Marketplace coverage",
        "demand_strength": "Demand strength",
        "valuation_coverage": "Valuation coverage",
    }

    _STRENGTH_MESSAGES = {
        "metadata_completeness": "Core artist, title and label metadata is well populated.",
        "marketplace_coverage": "Marketplace evidence covers most of the collection.",
        "demand_strength": "Observed demand is strong relative to current supply.",
        "valuation_coverage": "Most releases have a usable current lowest-price value.",
    }

    _IMPROVEMENT_MESSAGES = {
        "metadata_completeness": "Complete missing artist, title or label metadata.",
        "marketplace_coverage": "Refresh marketplace data for uncovered releases.",
        "demand_strength": "Review releases with weak demand relative to current supply.",
        "valuation_coverage": "Improve current price coverage before relying on valuation totals.",
    }

    def __init__(
        self,
        config: CollectionHealthConfig | None = None,
    ) -> None:
        self.config = config or CollectionHealthConfig()
        self._validate_config(self.config)

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        collection = tuple(context.collection)

        if not collection:
            return self._empty_result()

        marketplace_rows, marketplace_count = self._marketplace_rows(
            collection,
            context.marketplace,
        )

        metadata_score, complete_metadata_count = self._metadata_score(
            collection
        )
        marketplace_score = self._percentage(
            marketplace_count,
            len(collection),
        )
        demand_score, demand_evidence_count, invalid_demand_count = (
            self._demand_score(marketplace_rows, len(collection))
        )
        valuation_score, valuation_evidence_count, invalid_price_count = (
            self._valuation_score(marketplace_rows, len(collection))
        )

        component_scores = {
            "metadata_completeness": metadata_score,
            "marketplace_coverage": marketplace_score,
            "demand_strength": demand_score,
            "valuation_coverage": valuation_score,
        }
        weights = self.config.weights.as_dict()
        overall_score = round(
            sum(
                component_scores[name] * weights[name]
                for name in component_scores
            ),
            1,
        )

        strengths = tuple(
            self._STRENGTH_MESSAGES[name]
            for name, score in component_scores.items()
            if score >= self.config.strength_threshold
        )
        opportunities = tuple(
            self._IMPROVEMENT_MESSAGES[name]
            for name, score in component_scores.items()
            if score < self.config.improvement_threshold
        )

        evidence = self._evidence(
            collection_count=len(collection),
            complete_metadata_count=complete_metadata_count,
            marketplace_count=marketplace_count,
            demand_evidence_count=demand_evidence_count,
            valuation_evidence_count=valuation_evidence_count,
        )
        diagnostics = self._diagnostics(
            collection_count=len(collection),
            marketplace_count=marketplace_count,
            demand_evidence_count=demand_evidence_count,
            invalid_demand_count=invalid_demand_count,
            invalid_price_count=invalid_price_count,
        )

        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=IntelligenceStatus.COMPLETED,
            summary=self._summary(overall_score, len(collection)),
            insights=self._insights(strengths, opportunities),
            metrics={
                "overall_health_score": overall_score,
                "component_scores": component_scores,
                "component_weights": weights,
                "collection_release_count": len(collection),
                "marketplace_release_count": marketplace_count,
                "demand_evidence_count": demand_evidence_count,
                "valuation_evidence_count": valuation_evidence_count,
                "strengths": strengths,
                "improvement_opportunities": opportunities,
            },
            evidence=evidence,
            diagnostics=diagnostics,
        )

    def _empty_result(self) -> IntelligenceResult:
        component_scores = {
            name: 0.0
            for name in self._COMPONENT_LABELS
        }
        opportunity = "Import collection records before assessing collection health."

        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=IntelligenceStatus.SKIPPED,
            summary="Collection Health could not be assessed because the collection is empty.",
            insights=(f"Improvement opportunity: {opportunity}",),
            metrics={
                "overall_health_score": 0.0,
                "component_scores": component_scores,
                "component_weights": self.config.weights.as_dict(),
                "collection_release_count": 0,
                "marketplace_release_count": 0,
                "demand_evidence_count": 0,
                "valuation_evidence_count": 0,
                "strengths": (),
                "improvement_opportunities": (opportunity,),
            },
            evidence=("The prepared context contains 0 collection releases.",),
            diagnostics=("Analysis skipped safely: no collection records were supplied.",),
        )

    def _metadata_score(
        self,
        collection: tuple[Mapping[str, Any], ...],
    ) -> tuple[float, int]:
        total_fields = len(collection) * len(self.config.metadata_fields)
        populated_fields = sum(
            self._has_value(row.get(field_name))
            for row in collection
            for field_name in self.config.metadata_fields
        )
        complete_records = sum(
            all(self._has_value(row.get(field_name)) for field_name in self.config.metadata_fields)
            for row in collection
        )

        return self._percentage(populated_fields, total_fields), complete_records

    @staticmethod
    def _marketplace_rows(
        collection: tuple[Mapping[str, Any], ...],
        marketplace: Mapping[int, Mapping[str, Any]],
    ) -> tuple[tuple[Mapping[str, Any], ...], int]:
        rows: list[Mapping[str, Any]] = []

        for collection_row in collection:
            release_id = CollectionHealthModule._release_id(
                collection_row.get("release_id")
            )

            if release_id is None:
                continue

            marketplace_row = marketplace.get(release_id)

            if marketplace_row is None:
                marketplace_row = marketplace.get(str(release_id))  # type: ignore[arg-type]

            if isinstance(marketplace_row, Mapping):
                rows.append(marketplace_row)

        return tuple(rows), len(rows)

    def _demand_score(
        self,
        marketplace_rows: tuple[Mapping[str, Any], ...],
        collection_count: int,
    ) -> tuple[float, int, int]:
        scores: list[float] = []
        invalid_count = 0

        for row in marketplace_rows:
            wants = self._number(row.get("wants"))
            supply = self._number(row.get("copies_for_sale"))

            if wants is None or supply is None:
                if "wants" in row or "copies_for_sale" in row:
                    invalid_count += 1
                continue

            ratio = wants / max(supply, 1.0)
            scores.append(
                min(
                    100.0,
                    (ratio / self.config.demand_ratio_for_full_score) * 100.0,
                )
            )

        if not scores:
            return 0.0, 0, invalid_count

        observed_score = sum(scores) / len(scores)
        evidence_coverage = len(scores) / collection_count
        confidence_adjusted_score = observed_score * evidence_coverage

        return (
            round(confidence_adjusted_score, 1),
            len(scores),
            invalid_count,
        )

    def _valuation_score(
        self,
        marketplace_rows: tuple[Mapping[str, Any], ...],
        collection_count: int,
    ) -> tuple[float, int, int]:
        usable_prices = 0
        invalid_count = 0

        for row in marketplace_rows:
            price = self._number(row.get("lowest_price"))

            if price is None:
                if "lowest_price" in row:
                    invalid_count += 1
                continue

            if price > 0:
                usable_prices += 1

        return (
            self._percentage(usable_prices, collection_count),
            usable_prices,
            invalid_count,
        )

    def _evidence(
        self,
        *,
        collection_count: int,
        complete_metadata_count: int,
        marketplace_count: int,
        demand_evidence_count: int,
        valuation_evidence_count: int,
    ) -> tuple[str, ...]:
        return (
            f"{collection_count} collection releases were assessed.",
            (
                f"{complete_metadata_count}/{collection_count} releases contain "
                "all configured core metadata fields."
            ),
            f"{marketplace_count}/{collection_count} releases have prepared marketplace evidence.",
            (
                f"{demand_evidence_count}/{collection_count} releases have usable "
                "Wants and supply evidence."
            ),
            (
                f"{valuation_evidence_count}/{collection_count} releases have a "
                "positive current lowest-price value."
            ),
        )

    @staticmethod
    def _diagnostics(
        *,
        collection_count: int,
        marketplace_count: int,
        demand_evidence_count: int,
        invalid_demand_count: int,
        invalid_price_count: int,
    ) -> tuple[str, ...]:
        diagnostics = [
            "Collection Health used only the prepared IntelligenceContext; "
            "no provider or database calls were made."
        ]

        if marketplace_count < collection_count:
            diagnostics.append(
                "Marketplace coverage is incomplete for "
                f"{collection_count - marketplace_count} releases."
            )

        if demand_evidence_count < marketplace_count:
            diagnostics.append(
                "Demand strength excludes "
                f"{marketplace_count - demand_evidence_count} marketplace records "
                "without complete Wants and supply values."
            )

        if invalid_demand_count:
            diagnostics.append(
                f"Ignored invalid demand values in {invalid_demand_count} marketplace records."
            )

        if invalid_price_count:
            diagnostics.append(
                f"Ignored invalid lowest-price values in {invalid_price_count} marketplace records."
            )

        return tuple(diagnostics)

    @staticmethod
    def _insights(
        strengths: tuple[str, ...],
        opportunities: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(
            [f"Strength: {message}" for message in strengths]
            + [
                f"Improvement opportunity: {message}"
                for message in opportunities
            ]
        )

    @staticmethod
    def _summary(score: float, collection_count: int) -> str:
        if score >= 80:
            assessment = "strong"
        elif score >= 60:
            assessment = "healthy"
        elif score >= 40:
            assessment = "mixed"
        else:
            assessment = "limited"

        return (
            f"Collection health is {assessment} at {score:.1f}/100 across "
            f"{collection_count} releases."
        )

    @staticmethod
    def _release_id(value: Any) -> int | None:
        try:
            release_id = int(value)
        except (TypeError, ValueError):
            return None

        return release_id if release_id > 0 else None

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None

        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(number) or number < 0:
            return None

        return number

    @staticmethod
    def _has_value(value: Any) -> bool:
        return value is not None and (
            not isinstance(value, str) or bool(value.strip())
        )

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0

        return round((numerator / denominator) * 100.0, 1)

    @staticmethod
    def _validate_config(config: CollectionHealthConfig) -> None:
        weights = config.weights.as_dict()

        if any(
            not math.isfinite(value) or value < 0
            for value in weights.values()
        ):
            raise ValueError("Collection Health weights must be finite and non-negative.")

        if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
            raise ValueError("Collection Health weights must total 1.0.")

        if not config.metadata_fields:
            raise ValueError("At least one metadata field must be configured.")

        if config.demand_ratio_for_full_score <= 0:
            raise ValueError("demand_ratio_for_full_score must be greater than zero.")

        if not 0 <= config.improvement_threshold <= 100:
            raise ValueError("improvement_threshold must be between 0 and 100.")

        if not 0 <= config.strength_threshold <= 100:
            raise ValueError("strength_threshold must be between 0 and 100.")
