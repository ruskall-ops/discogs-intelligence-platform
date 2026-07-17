from __future__ import annotations

import unittest

from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceModule,
    IntelligenceRegistry,
    IntelligenceStatus,
)
from dip.intelligence.modules import (
    CollectionHealthConfig,
    CollectionHealthModule,
    CollectionHealthWeights,
)


def _release(
    release_id: int,
    *,
    artist: str = "Artist",
    title: str = "Title",
    label: str = "Label",
) -> dict[str, object]:
    return {
        "release_id": release_id,
        "artist": artist,
        "title": title,
        "label": label,
    }


class CollectionHealthModuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.module = CollectionHealthModule()

    def test_module_implements_protocol_and_is_exposed_to_registry(self) -> None:
        self.assertIsInstance(self.module, IntelligenceModule)

        registry = IntelligenceRegistry([self.module])

        self.assertEqual(registry.module_ids, ("collection_health",))
        self.assertIs(registry.get("collection_health"), self.module)

    def test_strong_collection_scores_100_with_explainable_strengths(self) -> None:
        context = IntelligenceContext(
            collection=(
                _release(1),
                _release(2),
                _release(3),
            ),
            marketplace={
                1: {"wants": 200, "copies_for_sale": 5, "lowest_price": 25},
                2: {"wants": 120, "copies_for_sale": 4, "lowest_price": 18},
                3: {"wants": 80, "copies_for_sale": 2, "lowest_price": 40},
            },
        )

        result = self.module.analyse(context)

        self.assertEqual(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(result.metrics["overall_health_score"], 100.0)
        self.assertEqual(
            result.metrics["component_scores"],
            {
                "metadata_completeness": 100.0,
                "marketplace_coverage": 100.0,
                "demand_strength": 100.0,
                "valuation_coverage": 100.0,
            },
        )
        self.assertIn("strong at 100.0/100", result.summary)
        self.assertEqual(len(result.metrics["strengths"]), 4)
        self.assertEqual(result.metrics["improvement_opportunities"], ())
        self.assertTrue(all(insight.startswith("Strength:") for insight in result.insights))
        self.assertIn("3/3 releases have prepared marketplace evidence.", result.evidence)

    def test_weak_collection_surfaces_specific_improvement_opportunities(self) -> None:
        context = IntelligenceContext(
            collection=(
                _release(1, artist="", title="", label=""),
                _release(2, title="", label=""),
            ),
            marketplace={
                1: {"wants": 0, "copies_for_sale": 25, "lowest_price": 0},
                2: {"wants": 0, "copies_for_sale": 12, "lowest_price": 0},
            },
        )

        result = self.module.analyse(context)

        self.assertEqual(result.metrics["overall_health_score"], 29.2)
        self.assertEqual(
            result.metrics["component_scores"]["metadata_completeness"],
            16.7,
        )
        self.assertEqual(
            result.metrics["component_scores"]["demand_strength"],
            0.0,
        )
        self.assertIn("limited at 29.2/100", result.summary)
        self.assertEqual(len(result.metrics["strengths"]), 1)
        self.assertEqual(
            len(result.metrics["improvement_opportunities"]),
            3,
        )
        self.assertTrue(
            any(
                "Complete missing artist" in opportunity
                for opportunity in result.metrics["improvement_opportunities"]
            )
        )

    def test_empty_collection_is_skipped_safely(self) -> None:
        result = self.module.analyse(IntelligenceContext())

        self.assertEqual(result.status, IntelligenceStatus.SKIPPED)
        self.assertEqual(result.metrics["overall_health_score"], 0.0)
        self.assertEqual(result.metrics["collection_release_count"], 0)
        self.assertEqual(
            set(result.metrics["component_scores"].values()),
            {0.0},
        )
        self.assertIn("collection is empty", result.summary)
        self.assertIn("Analysis skipped safely", result.diagnostics[0])

    def test_partially_populated_collection_discloses_data_gaps(self) -> None:
        context = IntelligenceContext(
            collection=tuple(_release(release_id) for release_id in range(1, 5)),
            marketplace={
                1: {"wants": 40, "copies_for_sale": 2, "lowest_price": 20},
                2: {"wants": None, "copies_for_sale": 4, "lowest_price": "unknown"},
            },
        )

        result = self.module.analyse(context)

        self.assertEqual(result.metrics["overall_health_score"], 72.5)
        self.assertEqual(
            result.metrics["component_scores"],
            {
                "metadata_completeness": 100.0,
                "marketplace_coverage": 50.0,
                "demand_strength": 100.0,
                "valuation_coverage": 25.0,
            },
        )
        self.assertEqual(result.metrics["demand_evidence_count"], 1)
        self.assertEqual(result.metrics["valuation_evidence_count"], 1)
        self.assertTrue(
            any("incomplete for 2 releases" in item for item in result.diagnostics)
        )
        self.assertTrue(
            any("excludes 1 marketplace records" in item for item in result.diagnostics)
        )
        self.assertTrue(
            any("invalid lowest-price" in item for item in result.diagnostics)
        )

    def test_component_weights_are_explicit_and_configurable(self) -> None:
        config = CollectionHealthConfig(
            weights=CollectionHealthWeights(
                metadata_completeness=1.0,
                marketplace_coverage=0.0,
                demand_strength=0.0,
                valuation_coverage=0.0,
            )
        )
        module = CollectionHealthModule(config)

        result = module.analyse(
            IntelligenceContext(collection=(_release(1),))
        )

        self.assertEqual(result.metrics["overall_health_score"], 100.0)
        self.assertEqual(
            result.metrics["component_weights"],
            {
                "metadata_completeness": 1.0,
                "marketplace_coverage": 0.0,
                "demand_strength": 0.0,
                "valuation_coverage": 0.0,
            },
        )

    def test_invalid_weights_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must total 1.0"):
            CollectionHealthModule(
                CollectionHealthConfig(
                    weights=CollectionHealthWeights(
                        metadata_completeness=0.5,
                        marketplace_coverage=0.5,
                        demand_strength=0.5,
                        valuation_coverage=0.5,
                    )
                )
            )

    def test_module_executes_through_collection_intelligence_engine(self) -> None:
        execution = IntelligenceEngine([self.module]).execute(
            IntelligenceContext(collection=(_release(1),))
        )

        result = execution.result_for("collection_health")

        self.assertEqual(execution.module_count, 1)
        self.assertEqual(result.module_version, "1.0")
        self.assertFalse(result.failed)


if __name__ == "__main__":
    unittest.main()
