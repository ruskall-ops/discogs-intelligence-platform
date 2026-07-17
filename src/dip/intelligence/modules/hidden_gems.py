"""Explainable Hidden Gems intelligence for Version 0.2."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

from dip.intelligence.context import IntelligenceContext
from dip.intelligence.models import IntelligenceResult, IntelligenceStatus


@dataclass(frozen=True)
class HiddenGemsConfig:
    """All thresholds and weights used by the Hidden Gems module."""

    minimum_wants: float = 25.0
    maximum_marketplace_supply: float = 10.0
    demand_weight: float = 0.30
    scarcity_weight: float = 0.25
    rating_weight: float = 0.15
    ownership_weight: float = 0.15
    price_efficiency_weight: float = 0.15
    minimum_hidden_gem_score: float = 60.0
    demand_ratio_for_full_score: float = 20.0
    minimum_supply_divisor: float = 1.0
    maximum_community_rating: float = 5.0
    minimum_owned_quantity: float = 1.0
    maximum_owned_quantity: float = 5.0
    wants_per_price_unit_for_full_score: float = 5.0
    minimum_price_value: float = 0.01

    def weights(self) -> dict[str, float]:
        return {
            "demand": self.demand_weight,
            "scarcity": self.scarcity_weight,
            "community_rating": self.rating_weight,
            "collection_ownership": self.ownership_weight,
            "price_efficiency": self.price_efficiency_weight,
        }


@dataclass(frozen=True)
class HiddenGemCandidate:
    """Immutable, explainable release surfaced for further research."""

    release_id: int
    artist: str
    title: str
    hidden_gem_score: float
    evidence: tuple[str, ...]
    supporting_metrics: Mapping[str, Any]
    factor_scores: Mapping[str, float | None]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supporting_metrics",
            MappingProxyType(dict(self.supporting_metrics)),
        )
        object.__setattr__(
            self,
            "factor_scores",
            MappingProxyType(dict(self.factor_scores)),
        )


class HiddenGemsModule:
    """Surface unusual collection releases for research, not decisions."""

    module_id = "hidden_gems"
    module_version = "1.0"

    def __init__(self, config: HiddenGemsConfig | None = None) -> None:
        self.config = config or HiddenGemsConfig()
        self._validate_config(self.config)

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        collection = tuple(context.collection)

        if not collection:
            return self._empty_result()

        candidates: list[HiddenGemCandidate] = []
        missing_marketplace = 0
        invalid_marketplace = 0
        missing_rating = 0
        invalid_rating = 0
        missing_price = 0
        inferred_ownership = 0
        invalid_collection_rows = 0
        eligible_releases = 0

        for collection_row in collection:
            release_id = self._release_id(collection_row.get("release_id"))

            if release_id is None:
                invalid_collection_rows += 1
                continue

            marketplace_row = self._marketplace_row(
                context.marketplace,
                release_id,
            )

            if marketplace_row is None:
                missing_marketplace += 1
                continue

            wants = self._number(marketplace_row.get("wants"))
            supply = self._number(marketplace_row.get("copies_for_sale"))

            if wants is None or supply is None:
                invalid_marketplace += 1
                continue

            if (
                wants < self.config.minimum_wants
                or supply > self.config.maximum_marketplace_supply
            ):
                continue

            eligible_releases += 1
            rating, rating_state = self._community_rating(marketplace_row)
            price = self._positive_price(marketplace_row.get("lowest_price"))
            quantity, quantity_was_inferred = self._owned_quantity(
                collection_row
            )

            if rating_state == "missing":
                missing_rating += 1
            elif rating_state == "invalid":
                invalid_rating += 1

            if price is None:
                missing_price += 1

            if quantity_was_inferred:
                inferred_ownership += 1

            candidate = self._candidate(
                collection_row=collection_row,
                release_id=release_id,
                wants=wants,
                supply=supply,
                rating=rating,
                quantity=quantity,
                price=price,
            )

            if candidate.hidden_gem_score >= self.config.minimum_hidden_gem_score:
                candidates.append(candidate)

        ranked_candidates = tuple(
            sorted(
                candidates,
                key=lambda candidate: (
                    -candidate.hidden_gem_score,
                    candidate.release_id,
                ),
            )
        )
        candidate_scores = [
            candidate.hidden_gem_score
            for candidate in ranked_candidates
        ]
        highest_score = max(candidate_scores, default=0.0)
        average_score = (
            round(sum(candidate_scores) / len(candidate_scores), 1)
            if candidate_scores
            else 0.0
        )

        diagnostics = self._diagnostics(
            collection_count=len(collection),
            missing_marketplace=missing_marketplace,
            invalid_marketplace=invalid_marketplace,
            missing_rating=missing_rating,
            invalid_rating=invalid_rating,
            missing_price=missing_price,
            inferred_ownership=inferred_ownership,
            invalid_collection_rows=invalid_collection_rows,
        )
        evidence = tuple(
            (
                f"{candidate.artist} — {candidate.title} "
                f"({candidate.release_id}): "
                + "; ".join(candidate.evidence)
            )
            for candidate in ranked_candidates
        )

        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=IntelligenceStatus.COMPLETED,
            summary=self._summary(len(ranked_candidates), len(collection)),
            insights=tuple(
                f"Research candidate: {candidate.artist} — {candidate.title} "
                f"scored {candidate.hidden_gem_score:.1f}/100."
                for candidate in ranked_candidates
            ),
            metrics={
                "candidate_count": len(ranked_candidates),
                "highest_hidden_gem_score": highest_score,
                "average_hidden_gem_score": average_score,
                "ranked_candidates": ranked_candidates,
                "collection_release_count": len(collection),
                "eligible_release_count": eligible_releases,
                "component_weights": self.config.weights(),
                "minimum_hidden_gem_score": self.config.minimum_hidden_gem_score,
            },
            evidence=evidence,
            diagnostics=diagnostics,
        )

    def _candidate(
        self,
        *,
        collection_row: Mapping[str, Any],
        release_id: int,
        wants: float,
        supply: float,
        rating: float | None,
        quantity: float,
        price: float | None,
    ) -> HiddenGemCandidate:
        demand_ratio = wants / max(
            supply,
            self.config.minimum_supply_divisor,
        )
        demand_score = self._bounded_score(
            demand_ratio,
            self.config.demand_ratio_for_full_score,
        )
        scarcity_score = round(
            (
                1.0
                - min(supply, self.config.maximum_marketplace_supply)
                / self.config.maximum_marketplace_supply
            )
            * 100.0,
            1,
        )
        rating_score = (
            self._bounded_score(
                rating,
                self.config.maximum_community_rating,
            )
            if rating is not None
            else None
        )
        ownership_score = round(
            max(
                0.0,
                (
                    self.config.maximum_owned_quantity - quantity
                )
                / (
                    self.config.maximum_owned_quantity
                    - self.config.minimum_owned_quantity
                ),
            )
            * 100.0,
            1,
        )
        wants_per_price = (
            wants / max(price, self.config.minimum_price_value)
            if price is not None
            else None
        )
        price_efficiency_score = (
            self._bounded_score(
                wants_per_price,
                self.config.wants_per_price_unit_for_full_score,
            )
            if wants_per_price is not None
            else None
        )

        factor_scores: dict[str, float | None] = {
            "demand": demand_score,
            "scarcity": scarcity_score,
            "community_rating": rating_score,
            "collection_ownership": ownership_score,
            "price_efficiency": price_efficiency_score,
        }
        weights = self.config.weights()
        hidden_gem_score = round(
            sum(
                (factor_scores[name] or 0.0) * weights[name]
                for name in factor_scores
            ),
            1,
        )

        evidence = [
            (
                f"Demand is {wants:.0f} Wants against {supply:.0f} current "
                f"marketplace copies ({demand_ratio:.1f} Wants per copy)."
            ),
            (
                f"Current marketplace supply is {supply:.0f}, within the "
                f"configured maximum of {self.config.maximum_marketplace_supply:.0f}."
            ),
            f"The collection contains {quantity:.0f} owned copy or copies.",
        ]

        if rating is not None:
            evidence.append(
                f"Community rating evidence is {rating:.2f}/"
                f"{self.config.maximum_community_rating:.2f}."
            )

        if price is not None and wants_per_price is not None:
            evidence.append(
                f"The current lowest price is {price:.2f}, equal to "
                f"{wants_per_price:.1f} Wants per price unit."
            )

        return HiddenGemCandidate(
            release_id=release_id,
            artist=self._text(collection_row.get("artist"), "Unknown artist"),
            title=self._text(collection_row.get("title"), "Unknown title"),
            hidden_gem_score=hidden_gem_score,
            evidence=tuple(evidence),
            supporting_metrics={
                "wants": wants,
                "copies_for_sale": supply,
                "demand_to_supply_ratio": round(demand_ratio, 2),
                "community_rating": rating,
                "owned_quantity": quantity,
                "lowest_price": price,
                "wants_per_price_unit": (
                    round(wants_per_price, 2)
                    if wants_per_price is not None
                    else None
                ),
            },
            factor_scores=factor_scores,
        )

    def _empty_result(self) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=IntelligenceStatus.SKIPPED,
            summary="Hidden Gems analysis was skipped because the collection is empty.",
            metrics={
                "candidate_count": 0,
                "highest_hidden_gem_score": 0.0,
                "average_hidden_gem_score": 0.0,
                "ranked_candidates": (),
                "collection_release_count": 0,
                "eligible_release_count": 0,
                "component_weights": self.config.weights(),
                "minimum_hidden_gem_score": self.config.minimum_hidden_gem_score,
            },
            evidence=("The prepared context contains 0 collection releases.",),
            diagnostics=("Analysis skipped safely: no collection records were supplied.",),
        )

    @staticmethod
    def _summary(candidate_count: int, collection_count: int) -> str:
        if candidate_count == 0:
            return (
                f"No Hidden Gem research candidates met the configured threshold "
                f"across {collection_count} releases."
            )

        noun = "candidate" if candidate_count == 1 else "candidates"
        return (
            f"Hidden Gems surfaced {candidate_count} research {noun} across "
            f"{collection_count} releases for further investigation."
        )

    @staticmethod
    def _diagnostics(
        *,
        collection_count: int,
        missing_marketplace: int,
        invalid_marketplace: int,
        missing_rating: int,
        invalid_rating: int,
        missing_price: int,
        inferred_ownership: int,
        invalid_collection_rows: int,
    ) -> tuple[str, ...]:
        diagnostics = [
            "Hidden Gems used only the prepared IntelligenceContext; no provider "
            "or database calls were made."
        ]

        details = (
            (missing_marketplace, "collection releases had no marketplace record"),
            (invalid_marketplace, "marketplace records lacked valid Wants or supply"),
            (missing_rating, "eligible releases had no community rating"),
            (invalid_rating, "eligible releases had an invalid community rating"),
            (missing_price, "eligible releases had no usable current lowest price"),
            (
                inferred_ownership,
                "eligible releases had ownership inferred as one copy from collection membership",
            ),
            (invalid_collection_rows, "collection rows had no valid release identifier"),
        )

        diagnostics.extend(
            f"{count}/{collection_count} {message}."
            for count, message in details
            if count
        )
        return tuple(diagnostics)

    @staticmethod
    def _marketplace_row(
        marketplace: Mapping[int, Mapping[str, Any]],
        release_id: int,
    ) -> Mapping[str, Any] | None:
        row = marketplace.get(release_id)

        if row is None:
            row = marketplace.get(str(release_id))  # type: ignore[arg-type]

        return row if isinstance(row, Mapping) else None

    def _community_rating(
        self,
        marketplace_row: Mapping[str, Any],
    ) -> tuple[float | None, str]:
        if "community_rating" not in marketplace_row:
            return None, "missing"

        rating = self._number(
            marketplace_row.get("community_rating")
        )

        if rating is None or rating > self.config.maximum_community_rating:
            return None, "invalid"

        return rating, "available"

    def _owned_quantity(
        self,
        collection_row: Mapping[str, Any],
    ) -> tuple[float, bool]:
        for key in ("quantity", "owned_quantity"):
            if key in collection_row:
                quantity = self._number(collection_row.get(key))

                if (
                    quantity is not None
                    and quantity >= self.config.minimum_owned_quantity
                ):
                    return quantity, False

        return self.config.minimum_owned_quantity, True

    @staticmethod
    def _positive_price(value: Any) -> float | None:
        price = HiddenGemsModule._number(value)
        return price if price is not None and price > 0 else None

    @staticmethod
    def _release_id(value: Any) -> int | None:
        number = HiddenGemsModule._number(value)

        if number is None or not number.is_integer() or number <= 0:
            return None

        return int(number)

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
    def _bounded_score(value: float, full_score_value: float) -> float:
        return round(min(100.0, (value / full_score_value) * 100.0), 1)

    @staticmethod
    def _text(value: Any, fallback: str) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else fallback

    @staticmethod
    def _validate_config(config: HiddenGemsConfig) -> None:
        weights = config.weights()

        if any(
            not math.isfinite(weight) or weight < 0
            for weight in weights.values()
        ):
            raise ValueError("Hidden Gems weights must be finite and non-negative.")

        if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
            raise ValueError("Hidden Gems weights must total 1.0.")

        positive_values = {
            "maximum_marketplace_supply": config.maximum_marketplace_supply,
            "demand_ratio_for_full_score": config.demand_ratio_for_full_score,
            "minimum_supply_divisor": config.minimum_supply_divisor,
            "maximum_community_rating": config.maximum_community_rating,
            "minimum_owned_quantity": config.minimum_owned_quantity,
            "wants_per_price_unit_for_full_score": (
                config.wants_per_price_unit_for_full_score
            ),
            "minimum_price_value": config.minimum_price_value,
        }

        for name, value in positive_values.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and greater than zero.")

        if config.maximum_owned_quantity <= config.minimum_owned_quantity:
            raise ValueError(
                "maximum_owned_quantity must exceed minimum_owned_quantity."
            )

        bounded_values = {
            "minimum_hidden_gem_score": config.minimum_hidden_gem_score,
            "minimum_wants": config.minimum_wants,
        }

        for name, value in bounded_values.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative.")

        if config.minimum_hidden_gem_score > 100:
            raise ValueError("minimum_hidden_gem_score must not exceed 100.")
