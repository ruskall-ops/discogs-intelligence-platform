from dataclasses import FrozenInstanceError
import unittest

from dip.decision_intelligence import (
    MarketplaceOpportunityDomainError,
    MarketplaceOpportunityInput,
    MarketplaceOpportunityModule,
    OpportunityAssessment,
    OpportunityDimensionCategory,
    OpportunityDimensionFact,
    OpportunityEvidenceCoverage,
    OpportunitySourceProvenance,
)
from dip.intelligence import IntelligenceContext, IntelligenceStatus


def provenance(module_id):
    return OpportunitySourceProvenance(
        module_id, "1.0", "1.0", IntelligenceStatus.COMPLETED, True,
        ("a", "b"), (),
    )


def fact(release_id, source, assessment, coverage=OpportunityEvidenceCoverage.COMPLETE):
    return OpportunityDimensionFact(release_id, source, assessment, coverage)


def supplied(releases):
    facts = []
    for release_id, momentum, stability, scarcity, *coverage in releases:
        source_coverage = coverage[0] if coverage else OpportunityEvidenceCoverage.COMPLETE
        facts.extend((
            fact(release_id, "marketplace_momentum", momentum, source_coverage),
            fact(release_id, "marketplace_stability", stability, source_coverage),
            fact(release_id, "marketplace_scarcity", scarcity, source_coverage),
        ))
    return MarketplaceOpportunityInput(
        tuple(provenance(source) for source in (
            "marketplace_momentum", "marketplace_stability", "marketplace_scarcity"
        )),
        tuple(facts),
    )


def analyse(value):
    result = MarketplaceOpportunityModule().analyse(
        IntelligenceContext(marketplace_opportunity_input=value)
    )
    return result, result.metrics["output"]


class MarketplaceOpportunityModuleTestCase(unittest.TestCase):
    def test_source_state_mappings_are_explicit(self):
        cases = (
            ("positive", "stable", "scarce", (
                OpportunityDimensionCategory.SUPPORTIVE,
                OpportunityDimensionCategory.SUPPORTIVE,
                OpportunityDimensionCategory.SUPPORTIVE,
            )),
            ("mixed", "mixed", "limited", (
                OpportunityDimensionCategory.NEUTRAL,
                OpportunityDimensionCategory.NEUTRAL,
                OpportunityDimensionCategory.NEUTRAL,
            )),
            ("neutral", "volatile", "common", (
                OpportunityDimensionCategory.NEUTRAL,
                OpportunityDimensionCategory.LIMITING,
                OpportunityDimensionCategory.LIMITING,
            )),
            ("negative", "stable", "abundant", (
                OpportunityDimensionCategory.ADVERSE,
                OpportunityDimensionCategory.SUPPORTIVE,
                OpportunityDimensionCategory.LIMITING,
            )),
        )
        for momentum, stability, scarcity, expected in cases:
            with self.subTest(momentum=momentum, stability=stability, scarcity=scarcity):
                _, output = analyse(supplied(((1, momentum, stability, scarcity),)))
                dimensions = output.releases[0].dimensions
                self.assertEqual(
                    (dimensions.momentum.category, dimensions.stability.category, dimensions.scarcity.category),
                    expected,
                )

    def test_strong_and_developing_rules(self):
        _, output = analyse(supplied((
            (1, "positive", "stable", "scarce"),
            (2, "positive", "stable", "very_scarce"),
            (3, "positive", "mixed", "scarce"),
            (4, "positive", "stable", "limited"),
            (5, "positive", "stable", "scarce", OpportunityEvidenceCoverage.PARTIAL),
        )))
        by_id = {value.release_id: value for value in output.releases}
        self.assertIs(by_id[1].assessment, OpportunityAssessment.STRONG)
        self.assertIs(by_id[2].assessment, OpportunityAssessment.STRONG)
        self.assertIs(by_id[3].assessment, OpportunityAssessment.DEVELOPING)
        self.assertIs(by_id[4].assessment, OpportunityAssessment.DEVELOPING)
        self.assertIs(by_id[5].assessment, OpportunityAssessment.DEVELOPING)

    def test_balanced_constrained_and_weak_rules(self):
        _, output = analyse(supplied((
            (1, "neutral", "stable", "scarce"),
            (2, "positive", "volatile", "scarce"),
            (3, "positive", "stable", "abundant"),
            (4, "negative", "mixed", "common"),
            (5, "negative", "volatile", "limited"),
        )))
        by_id = {value.release_id: value for value in output.releases}
        self.assertIs(by_id[1].assessment, OpportunityAssessment.BALANCED)
        self.assertIs(by_id[2].assessment, OpportunityAssessment.CONSTRAINED)
        self.assertIs(by_id[3].assessment, OpportunityAssessment.CONSTRAINED)
        self.assertIs(by_id[4].assessment, OpportunityAssessment.WEAK)
        self.assertIs(by_id[5].assessment, OpportunityAssessment.WEAK)

    def test_evidence_coverage_and_missing_dimensions(self):
        _, partial = analyse(supplied(((1, "positive", "stable", "scarce", OpportunityEvidenceCoverage.PARTIAL),)))
        self.assertIs(partial.releases[0].evidence_coverage, OpportunityEvidenceCoverage.PARTIAL)
        _, limited = analyse(supplied(((1, "positive", "stable", "scarce", OpportunityEvidenceCoverage.LIMITED),)))
        self.assertIs(limited.releases[0].evidence_coverage, OpportunityEvidenceCoverage.LIMITED)
        sparse = MarketplaceOpportunityInput(
            tuple(provenance(source) for source in (
                "marketplace_momentum", "marketplace_stability", "marketplace_scarcity"
            )),
            (fact(1, "marketplace_momentum", "positive"),),
        )
        _, sparse_output = analyse(sparse)
        self.assertIs(sparse_output.releases[0].assessment, OpportunityAssessment.INSUFFICIENT)
        self.assertIs(sparse_output.releases[0].evidence_coverage, OpportunityEvidenceCoverage.INSUFFICIENT)
        result, missing = analyse(MarketplaceOpportunityInput())
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertEqual(missing.releases, ())

    def test_order_summary_rule_version_and_immutability(self):
        _, output = analyse(supplied((
            (2, "negative", "mixed", "common"),
            (1, "positive", "stable", "scarce"),
        )))
        self.assertEqual(tuple(value.release_id for value in output.releases), (1, 2))
        self.assertEqual(output.rule_set_version, "1.0")
        self.assertEqual(output.summary.strong_count, 1)
        self.assertEqual(output.summary.weak_count, 1)
        with self.assertRaises(FrozenInstanceError):
            output.summary.release_count = 3

    def test_duplicate_release_dimension_is_rejected(self):
        with self.assertRaisesRegex(MarketplaceOpportunityDomainError, "Duplicate"):
            MarketplaceOpportunityInput(
                tuple(provenance(source) for source in (
                    "marketplace_momentum", "marketplace_stability", "marketplace_scarcity"
                )),
                (
                    fact(1, "marketplace_momentum", "positive"),
                    fact(1, "marketplace_momentum", "positive"),
                ),
            )


if __name__ == "__main__":
    unittest.main()

