from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceModule,
    IntelligenceStatus,
    build_v02_intelligence_registry,
)
from dip.intelligence.modules import (
    HiddenGemCandidate,
    HiddenGemsConfig,
    HiddenGemsModule,
)


def _release(
    release_id: int,
    *,
    artist: str = "Artist",
    title: str = "Title",
    quantity: int | None = 1,
) -> dict[str, object]:
    release: dict[str, object] = {
        "release_id": release_id,
        "artist": artist,
        "title": title,
    }

    if quantity is not None:
        release["quantity"] = quantity

    return release


def _market(
    *,
    wants: object = 200,
    supply: object = 2,
    rating: object = 4.5,
    price: object = 10,
) -> dict[str, object]:
    return {
        "wants": wants,
        "copies_for_sale": supply,
        "community_rating": rating,
        "lowest_price": price,
    }


class HiddenGemsModuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.module = HiddenGemsModule()

    def test_completed_analysis_returns_ranked_immutable_candidates(self) -> None:
        context = IntelligenceContext(
            collection=(
                _release(1, artist="Deep Artist", title="Quiet Classic"),
                _release(2, artist="Common Artist", title="Common Release"),
                _release(3, artist="Scarce Artist", title="Too Little Demand"),
            ),
            marketplace={
                1: _market(),
                2: _market(wants=300, supply=30),
                3: _market(wants=10, supply=1),
            },
        )

        result = self.module.analyse(context)
        candidates = result.metrics["ranked_candidates"]

        self.assertEqual(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(result.metrics["candidate_count"], 1)
        self.assertEqual(result.metrics["highest_hidden_gem_score"], 93.5)
        self.assertEqual(result.metrics["average_hidden_gem_score"], 93.5)
        self.assertIsInstance(candidates, tuple)
        self.assertIsInstance(candidates[0], HiddenGemCandidate)
        self.assertEqual(candidates[0].release_id, 1)
        self.assertEqual(candidates[0].hidden_gem_score, 93.5)
        self.assertIn("1 research candidate", result.summary)
        self.assertNotIn("buy", result.summary.lower())
        self.assertNotIn("sell", result.summary.lower())
        self.assertNotIn("keep", result.summary.lower())

    def test_empty_collection_is_skipped_safely(self) -> None:
        result = self.module.analyse(IntelligenceContext())

        self.assertEqual(result.status, IntelligenceStatus.SKIPPED)
        self.assertEqual(result.metrics["candidate_count"], 0)
        self.assertEqual(result.metrics["ranked_candidates"], ())
        self.assertIn("collection is empty", result.summary)
        self.assertIn("Analysis skipped safely", result.diagnostics[0])

    def test_invalid_and_partial_marketplace_evidence_is_safe(self) -> None:
        context = IntelligenceContext(
            collection=(
                _release(1, quantity=None),
                _release(2),
                _release(3),
            ),
            marketplace={
                1: _market(rating="invalid", price="invalid"),
                2: _market(wants="invalid"),
            },
        )

        result = self.module.analyse(context)
        candidate = result.metrics["ranked_candidates"][0]

        self.assertEqual(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(result.metrics["candidate_count"], 1)
        self.assertIsNone(candidate.factor_scores["community_rating"])
        self.assertIsNone(candidate.factor_scores["price_efficiency"])
        self.assertEqual(candidate.supporting_metrics["owned_quantity"], 1.0)
        self.assertTrue(
            any("no marketplace record" in item for item in result.diagnostics)
        )
        self.assertTrue(
            any("lacked valid Wants" in item for item in result.diagnostics)
        )
        self.assertTrue(
            any("invalid community rating" in item for item in result.diagnostics)
        )
        self.assertTrue(
            any("no usable current lowest price" in item for item in result.diagnostics)
        )
        self.assertTrue(
            any("ownership inferred" in item for item in result.diagnostics)
        )

    def test_configuration_overrides_thresholds_and_weights(self) -> None:
        config = HiddenGemsConfig(
            minimum_wants=10,
            maximum_marketplace_supply=20,
            demand_weight=1.0,
            scarcity_weight=0.0,
            rating_weight=0.0,
            ownership_weight=0.0,
            price_efficiency_weight=0.0,
            minimum_hidden_gem_score=50,
            demand_ratio_for_full_score=4,
        )
        module = HiddenGemsModule(config)
        context = IntelligenceContext(
            collection=(_release(10),),
            marketplace={10: _market(wants=20, supply=5)},
        )

        result = module.analyse(context)
        candidate = result.metrics["ranked_candidates"][0]

        self.assertEqual(result.metrics["candidate_count"], 1)
        self.assertEqual(candidate.factor_scores["demand"], 100.0)
        self.assertEqual(candidate.hidden_gem_score, 100.0)
        self.assertEqual(
            result.metrics["component_weights"]["demand"],
            1.0,
        )

    def test_candidates_are_deterministically_ordered_by_score_then_id(self) -> None:
        context = IntelligenceContext(
            collection=(_release(2), _release(1), _release(3)),
            marketplace={
                2: _market(),
                1: _market(),
                3: _market(wants=100, supply=5, rating=4, price=20),
            },
        )

        first = self.module.analyse(context)
        second = self.module.analyse(context)
        first_ids = tuple(
            candidate.release_id
            for candidate in first.metrics["ranked_candidates"]
        )
        second_ids = tuple(
            candidate.release_id
            for candidate in second.metrics["ranked_candidates"]
        )

        self.assertEqual(first_ids, second_ids)
        self.assertEqual(first_ids[:2], (1, 2))

    def test_candidate_evidence_explains_every_available_factor(self) -> None:
        result = self.module.analyse(
            IntelligenceContext(
                collection=(_release(1),),
                marketplace={1: _market()},
            )
        )
        candidate = result.metrics["ranked_candidates"][0]
        evidence = " ".join(candidate.evidence)

        self.assertIn("Wants against", evidence)
        self.assertIn("marketplace supply", evidence)
        self.assertIn("owned copy", evidence)
        self.assertIn("Community rating", evidence)
        self.assertIn("Wants per price unit", evidence)
        self.assertEqual(
            set(candidate.factor_scores),
            {
                "demand",
                "scarcity",
                "community_rating",
                "collection_ownership",
                "price_efficiency",
            },
        )

    def test_candidate_and_nested_metrics_are_immutable(self) -> None:
        result = self.module.analyse(
            IntelligenceContext(
                collection=(_release(1),),
                marketplace={1: _market()},
            )
        )
        candidate = result.metrics["ranked_candidates"][0]

        with self.assertRaises(FrozenInstanceError):
            candidate.title = "Changed"  # type: ignore[misc]

        with self.assertRaises(TypeError):
            candidate.factor_scores["demand"] = 0.0  # type: ignore[index]

        with self.assertRaises(TypeError):
            candidate.supporting_metrics["wants"] = 0  # type: ignore[index]

    def test_module_implements_contract_and_default_registry_registers_it(self) -> None:
        self.assertIsInstance(self.module, IntelligenceModule)

        registry = build_v02_intelligence_registry()

        self.assertEqual(
            registry.module_ids,
            ("collection_health", "hidden_gems"),
        )
        self.assertIsInstance(registry.get("hidden_gems"), HiddenGemsModule)


class _FailingHiddenGemsModule(HiddenGemsModule):
    def analyse(self, context: IntelligenceContext):
        raise RuntimeError("controlled Hidden Gems failure")


class HiddenGemsEngineFailureTestCase(unittest.TestCase):
    def test_failed_execution_is_isolated_by_engine(self) -> None:
        execution = IntelligenceEngine(
            [_FailingHiddenGemsModule()]
        ).execute(
            IntelligenceContext(collection=(_release(1),))
        )
        result = execution.result_for("hidden_gems")

        self.assertEqual(result.status, IntelligenceStatus.FAILED)
        self.assertIn("RuntimeError", result.diagnostics[0])
        self.assertIn("controlled Hidden Gems failure", result.diagnostics[0])


if __name__ == "__main__":
    unittest.main()
