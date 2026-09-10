from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, getcontext, localcontext
import sys
import unittest
from unittest.mock import patch

from dip.app import (
    PORTFOLIO_EXECUTION_FAILURE_MESSAGE,
    CurrentCollectionContext,
    CurrentCollectionPortfolioExecutionOutcome,
    CurrentCollectionPortfolioExecutionService,
    CurrentCollectionPortfolioFailureStage,
    PortfolioConcentrationExecutionService,
    PortfolioDistributionExecutionService,
)
from dip.experience.current_collection_portfolio import (
    CurrentCollectionPortfolioPresentationBuilder,
    PortfolioDestination,
    PortfolioPresentationAvailability,
    PresentedRatio,
    format_percentage,
)
from dip.intelligence import IntelligenceEngine
from dip.intelligence import IntelligenceStatus
from dip.portfolio_intelligence import (
    PortfolioConcentrationModule,
    PortfolioDistributionModule,
)


def _row(
    release_id,
    *,
    quantity=1,
    artist="Artist",
    label="Label",
    format_value="Vinyl",
    released="2000",
):
    return {
        "release_id": release_id,
        "quantity": quantity,
        "artist": artist,
        "label": label,
        "format": format_value,
        "released": released,
    }


class _Rows:
    def __init__(self, rows):
        self.rows = rows
        self.reads = 0

    def owned_portfolio_metadata_rows(self):
        self.reads += 1
        return self.rows


def _outcome(rows):
    repository = _Rows(rows)
    distribution = PortfolioDistributionExecutionService(
        repository, IntelligenceEngine((PortfolioDistributionModule(),))
    )
    concentration = PortfolioConcentrationExecutionService(
        distribution, IntelligenceEngine((PortfolioConcentrationModule(),))
    )
    service = CurrentCollectionPortfolioExecutionService(
        CurrentCollectionContext(scope_id="current_collection"),
        distribution,
        concentration,
    )
    result = service.execute()
    assert result.succeeded
    return result, repository


def _context_state(value):
    return (
        value.prec,
        value.rounding,
        value.Emin,
        value.Emax,
        value.capitals,
        value.clamp,
        dict(value.flags),
        dict(value.traps),
    )


class CurrentCollectionPortfolioPresentationTestCase(unittest.TestCase):
    def setUp(self):
        self.builder = CurrentCollectionPortfolioPresentationBuilder()

    def test_workspace_is_closed_current_collection_and_distribution_first(self):
        outcome, _ = _outcome((_row(1),))
        workspace = self.builder.build(outcome)
        self.assertEqual(workspace.scope_id, "current_collection")
        self.assertEqual(workspace.title, "Current Collection Portfolio")
        self.assertEqual(
            tuple((item.destination, item.title) for item in workspace.navigation),
            (
                (PortfolioDestination.DISTRIBUTION, "Distribution"),
                (PortfolioDestination.CONCENTRATION, "Concentration"),
            ),
        )
        self.assertIs(workspace.selected_destination, PortfolioDestination.DISTRIBUTION)
        fixed = repr(workspace.navigation)
        for forbidden in ("Overview", "Opportunity", "History", "Research"):
            self.assertNotIn(forbidden, fixed)
        with self.assertRaises((FrozenInstanceError, TypeError)):
            workspace.title = "Other"  # type: ignore[misc]

    def test_fixed_copy_is_derived_and_cannot_be_replaced(self):
        workspace = self.builder.build(_outcome((_row(1),))[0])
        assert workspace.distribution is not None and workspace.concentration is not None
        derived = (
            (workspace, "title"),
            (workspace, "source_copy"),
            (workspace, "navigation"),
            (workspace, "message"),
            (workspace.distribution, "state_copy"),
            (workspace.distribution, "rounding_copy"),
            (workspace.distribution.dimensions[0], "title"),
            (workspace.distribution.dimensions[0], "missing_metadata_copy"),
            (workspace.concentration, "state_copy"),
            (workspace.concentration, "interpretation_copy"),
            (workspace.concentration.dimensions[0], "denominator_copy"),
            (workspace.concentration.dimensions[0].release_basis, "denominator_label"),
            (workspace.concentration.dimensions[0].release_basis.first_three, "title"),
            (workspace.distribution.dimensions[0].release_coverage, "percentage"),
        )
        for model, name in derived:
            with self.subTest(name=name), self.assertRaises(TypeError):
                replace(model, **{name: "Traceback SELECT /Users/private token"})

    def test_public_models_reject_structural_contradictions(self):
        workspace = self.builder.build(_outcome((_row(1, quantity=2), _row(2, artist=None)))[0])
        distribution = workspace.distribution
        concentration = workspace.concentration
        assert distribution is not None and concentration is not None
        dimension = distribution.dimensions[0]
        concentrated = concentration.dimensions[0]
        release_basis = concentrated.release_basis
        assert release_basis.first_three is not None
        invalid = (
            lambda: replace(distribution, dimensions=tuple(reversed(distribution.dimensions))),
            lambda: replace(distribution, dimensions=distribution.dimensions[:-1]),
            lambda: replace(distribution, dimensions=(distribution.dimensions[0],) + distribution.dimensions[:-1]),
            lambda: replace(dimension, dimension_id="arbitrary"),
            lambda: replace(dimension, releases_with_metadata=999),
            lambda: replace(concentrated, release_basis=concentrated.copy_basis, copy_basis=release_basis),
            lambda: replace(release_basis, first_three=replace(release_basis.first_three, requested_count=5)),
            lambda: replace(release_basis.first_three, included_count=0),
            lambda: replace(release_basis.first_three, contributors=()),
            lambda: replace(release_basis.first_three.membership_share, numerator=999),
            lambda: replace(dimension.release_coverage, denominator=999),
            lambda: replace(dimension.release_coverage, domain_ratio=Decimal("0.25")),
            lambda: replace(
                release_basis,
                first_three=release_basis.first_five,
                first_five=release_basis.first_three,
            ),
        )
        for index, constructor in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises((TypeError, ValueError)):
                constructor()

    def test_selection_is_typed_and_preserves_presentations(self):
        outcome, _ = _outcome((_row(1),))
        workspace = self.builder.build(outcome)
        selected = self.builder.select(workspace, PortfolioDestination.CONCENTRATION)
        self.assertIs(selected.distribution, workspace.distribution)
        self.assertIs(selected.concentration, workspace.concentration)
        self.assertIs(selected.selected_destination, PortfolioDestination.CONCENTRATION)
        for value in ("overview", "history", "distribution", None, True):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.builder.select(workspace, value)  # type: ignore[arg-type]

    def test_unavailable_outcome_uses_only_stable_safe_copy(self):
        outcome = CurrentCollectionPortfolioExecutionOutcome(
            None,
            CurrentCollectionPortfolioFailureStage.DISTRIBUTION,
            PORTFOLIO_EXECUTION_FAILURE_MESSAGE,
        )
        workspace = self.builder.build(outcome)
        self.assertIs(workspace.availability, PortfolioPresentationAvailability.UNAVAILABLE)
        self.assertIsNone(workspace.distribution)
        self.assertIsNone(workspace.concentration)
        self.assertEqual(workspace.message, PORTFOLIO_EXECUTION_FAILURE_MESSAGE)
        for forbidden in ("Traceback", "SELECT", "/Users/", "token", "None"):
            self.assertNotIn(forbidden, workspace.message)

    def test_internal_result_text_never_enters_fixed_public_copy(self):
        outcome, _ = _outcome((_row(1),))
        portfolio = outcome.portfolio
        assert portfolio is not None
        hostile = "Traceback SELECT /Users/private token=None provider_payload"
        changed = replace(
            portfolio,
            distribution=replace(
                portfolio.distribution,
                summary=hostile,
                diagnostics=(hostile,),
                evidence=(hostile,),
            ),
            concentration=replace(
                portfolio.concentration,
                summary=hostile,
                diagnostics=(hostile,),
                evidence=(hostile,),
            ),
        )
        workspace = self.builder.build(replace(outcome, portfolio=changed))
        public_copy = repr(workspace)
        self.assertNotIn(hostile, public_copy)

    def test_projection_is_value_deterministic_and_does_not_mutate_source(self):
        outcome, repository = _outcome((_row(1, quantity=2), _row(2)))
        source = outcome.portfolio
        before = repr(source)
        first = self.builder.build(outcome)
        second = self.builder.build(outcome)
        self.assertEqual(first, second)
        self.assertEqual(repr(source), before)
        self.assertEqual(repository.reads, 1)

    def test_malformed_or_mismatched_snapshots_fail_without_partial_presentation(self):
        outcome, _ = _outcome((_row(1),))
        portfolio = outcome.portfolio
        assert portfolio is not None
        malformed = replace(
            portfolio,
            concentration=replace(
                portfolio.concentration,
                output=replace(
                    portfolio.concentration.output,
                    provenance=replace(
                        portfolio.concentration.output.provenance,
                        source_module_id="other",
                    ),
                ),
            ),
        )
        with self.assertRaises(ValueError):
            self.builder.build(replace(outcome, portfolio=malformed))
        bad_status = replace(
            portfolio,
            distribution=replace(
                portfolio.distribution,
                status=IntelligenceStatus.SKIPPED,
            ),
        )
        with self.assertRaises(ValueError):
            self.builder.build(replace(outcome, portfolio=bad_status))
        with self.assertRaises(TypeError):
            self.builder.build(object())  # type: ignore[arg-type]

    def test_distribution_preserves_totals_dimensions_denominators_and_order(self):
        long_label = "A very long label retained without abbreviation"
        outcome, _ = _outcome(
            (
                _row(1, quantity=2, artist="Same", label=long_label, released="1999"),
                _row(2, artist="same", label="Label", released="2001"),
                _row(3, artist=None, label=None, format_value=None, released=None),
            )
        )
        source = outcome.portfolio.distribution.output  # type: ignore[union-attr]
        view = self.builder.build(outcome).distribution
        assert view is not None
        self.assertEqual((view.unique_owned_releases, view.owned_copies, view.duplicate_copies), (3, 4, 1))
        self.assertEqual(tuple(item.title for item in view.dimensions), ("Artist", "Label", "Format", "Release year", "Decade"))
        for shown, domain in zip(view.dimensions, source.dimensions, strict=True):
            self.assertEqual(shown.releases_with_metadata, domain.releases_with_metadata)
            self.assertEqual(shown.copies_with_metadata, domain.copies_with_metadata)
            self.assertEqual(shown.release_coverage.denominator, 3)
            self.assertEqual(shown.copy_coverage.denominator, 4)
            self.assertEqual(shown.missing_release_ids, domain.missing_release_ids)
            self.assertEqual(tuple(row.category_id for row in shown.categories), tuple(row.category_id for row in domain.entries))
            self.assertEqual(tuple(row.release_ids for row in shown.categories), tuple(row.release_ids for row in domain.entries))
            self.assertNotIn("Unknown", tuple(row.label for row in shown.categories))
        labels = tuple(row.label for dimension in view.dimensions for row in dimension.categories)
        self.assertIn(long_label, labels)
        self.assertIn("Same", labels)
        self.assertIn("same", labels)

    def test_distribution_shares_use_full_denominator_and_can_total_below_100(self):
        outcome, _ = _outcome((_row(1, artist="One"), _row(2, artist=None), _row(3, artist="Two")))
        artist = self.builder.build(outcome).distribution.dimensions[0]  # type: ignore[union-attr]
        self.assertEqual(artist.release_coverage.numerator, 2)
        self.assertEqual(artist.release_coverage.denominator, 3)
        self.assertLess(
            sum(row.release_share.domain_ratio for row in artist.categories),
            Decimal("1"),
        )
        self.assertEqual(tuple(row.release_share.denominator for row in artist.categories), (3, 3))
        self.assertIn("not relabelled Unknown", artist.missing_metadata_copy)

    def test_distribution_ties_zero_and_state_variants_are_truthful(self):
        complete = self.builder.build(_outcome((_row(1, quantity=2), _row(2)))[0]).distribution
        self.assertEqual(complete.duplicate_copies, 1)  # type: ignore[union-attr]
        self.assertGreaterEqual(complete.dimensions[0].tied_largest_category_count, 1)  # type: ignore[union-attr]
        empty = self.builder.build(_outcome(())[0]).distribution
        insufficient = self.builder.build(_outcome((_row(1, artist=None, label=None, format_value=None, released=None),))[0]).distribution
        limited = self.builder.build(_outcome((_row(1, label=None, format_value=None, released=None),))[0]).distribution
        partial = self.builder.build(_outcome((_row(1), _row(2, artist=None),))[0]).distribution
        self.assertEqual(empty.unique_owned_releases, 0)  # type: ignore[union-attr]
        self.assertEqual(empty.duplicate_copies, 0)  # type: ignore[union-attr]
        self.assertEqual(insufficient.state, "insufficient_data")  # type: ignore[union-attr]
        self.assertEqual(limited.evidence_coverage, "limited")  # type: ignore[union-attr]
        self.assertEqual(partial.evidence_coverage, "partial")  # type: ignore[union-attr]

    def test_percentage_formatter_uses_half_even_and_handles_non_finite_safely(self):
        precision = getcontext().prec
        self.assertEqual(format_percentage(Decimal("0")), "0.00%")
        self.assertEqual(format_percentage(Decimal("0.01225")), "1.22%")
        self.assertEqual(format_percentage(Decimal("0.01235")), "1.24%")
        self.assertEqual(format_percentage(Decimal("-0.125")), "-12.50%")
        self.assertEqual(format_percentage(Decimal("NaN")), "Unavailable")
        self.assertEqual(format_percentage(Decimal("Infinity")), "Unavailable")
        self.assertEqual(getcontext().prec, precision)
        with self.assertRaises(TypeError):
            format_percentage(1)  # type: ignore[arg-type]

    def test_ratio_validation_is_independent_of_ambient_decimal_context(self):
        with localcontext() as source_context:
            source_context.prec = 28
            source_context.rounding = ROUND_HALF_EVEN
            ratio = Decimal(1) / Decimal(3)
        original = _context_state(getcontext())
        for precision, rounding in ((6, ROUND_HALF_EVEN), (50, ROUND_DOWN)):
            with self.subTest(precision=precision, rounding=rounding), localcontext() as presentation_context:
                presentation_context.prec = precision
                presentation_context.rounding = rounding
                before = _context_state(presentation_context)
                shown = PresentedRatio(1, 3, ratio)
                self.assertIs(shown.domain_ratio, ratio)
                self.assertEqual(_context_state(presentation_context), before)
        self.assertEqual(_context_state(getcontext()), original)
        for numerator, denominator, value in ((2, 3, ratio), (1, 4, ratio), (1, 3, Decimal("0.25"))):
            with self.subTest(values=(numerator, denominator, value)), self.assertRaises(ValueError):
                PresentedRatio(numerator, denominator, value)

    def test_concentration_separates_bases_denominators_and_coverage(self):
        outcome, _ = _outcome((_row(1, quantity=2, artist="One"), _row(2, artist=None), _row(3, artist="Two")))
        view = self.builder.build(outcome).concentration
        assert view is not None
        artist = view.dimensions[0]
        self.assertEqual(artist.release_coverage.denominator, 3)
        self.assertEqual(artist.release_basis.membership_total, 2)
        self.assertEqual(artist.release_basis.denominator_label, "represented releases")
        self.assertEqual(artist.copy_coverage.denominator, 4)
        self.assertEqual(artist.copy_basis.membership_total, 3)
        self.assertEqual(artist.copy_basis.denominator_label, "represented copies")
        self.assertIn("missing", artist.denominator_copy)
        self.assertIn("Full collection coverage", artist.denominator_copy)

    def test_concentration_preserves_first_n_distribution_order_and_metrics(self):
        rows = tuple(_row(i, quantity=7-i, artist=f"Artist {i}", released=str(1980 + i)) for i in range(1, 7))
        outcome, _ = _outcome(rows)
        source = outcome.portfolio.concentration.output  # type: ignore[union-attr]
        view = self.builder.build(outcome).concentration
        assert view is not None
        for shown, domain in zip(view.dimensions, source.dimensions, strict=True):
            self.assertEqual(shown.release_basis.first_three.title, "First 3 categories in Distribution order")
            self.assertEqual(shown.copy_basis.first_five.title, "First 5 categories in Distribution order")
            self.assertEqual(
                tuple(item.category_id for item in shown.copy_basis.first_three.contributors),
                tuple(item.category_id for item in domain.copy_concentration.top_three.contributions),
            )
            self.assertIs(shown.release_basis.hhi.domain_value, domain.release_concentration.hhi)
            self.assertIs(shown.copy_basis.normalized_hhi.domain_value, domain.copy_concentration.normalized_hhi)
            self.assertIs(shown.copy_basis.effective_category_count.domain_value, domain.copy_concentration.effective_category_count)
        decade = next(item for item in view.dimensions if item.dimension_id == "decade")
        ids = tuple(item.category_id for item in decade.copy_basis.first_three.contributors)
        self.assertEqual(ids, tuple(sorted(ids, key=int))[:3])

    def test_concentration_largest_ties_negative_deltas_and_non_advisory_copy(self):
        outcome, _ = _outcome((_row(1, quantity=3, artist="One"), _row(2, artist="Two"), _row(3, artist="Two")))
        view = self.builder.build(outcome).concentration
        assert view is not None
        artist = view.dimensions[0]
        self.assertGreaterEqual(len(artist.release_basis.largest_categories), 1)
        delta = artist.difference.effective_category_count_delta.domain_value
        self.assertIsInstance(delta, Decimal)
        self.assertTrue(any(
            value.domain_value is not None and value.domain_value < 0
            for value in (
                artist.difference.largest_category_share_delta,
                artist.difference.first_three_share_delta,
                artist.difference.first_five_share_delta,
                artist.difference.hhi_delta,
                artist.difference.normalized_hhi_delta,
                artist.difference.effective_category_count_delta,
            )
        ))
        for forbidden in ("advice", "recommendation", "valuation", "risk", "aggregate Portfolio score"):
            self.assertIn(forbidden, view.interpretation_copy)

    def test_distribution_release_and_copy_ties_are_independent_and_exact(self):
        independent = self.builder.build(
            _outcome((_row(1, quantity=3, artist="A"), _row(2, artist="B")))[0]
        ).distribution.dimensions[0]  # type: ignore[union-attr]
        self.assertEqual(tuple(item.category_id for item in independent.largest_release_categories), ("A", "B"))
        self.assertEqual(tuple(item.category_id for item in independent.largest_copy_categories), ("A",))
        with self.assertRaises(TypeError):
            replace(independent, tied_largest_category_count=2)

        tied = self.builder.build(
            _outcome((_row(1, artist="A"), _row(2, artist="B")))[0]
        ).distribution.dimensions[0]  # type: ignore[union-attr]
        self.assertEqual(tied.tied_largest_category_count, 2)
        with self.assertRaises(TypeError):
            replace(tied, tied_largest_category_count=1)

    def test_concentration_largest_contributors_are_complete_and_ordered(self):
        tied = self.builder.build(
            _outcome((_row(1, artist="A"), _row(2, artist="B"), _row(3, artist="C")))[0]
        )
        basis = tied.concentration.dimensions[0].release_basis  # type: ignore[union-attr]
        self.assertEqual(basis.largest_categories, basis.contributors)
        for changed in (
            basis.largest_categories[:-1],
            basis.largest_categories + (basis.largest_categories[0],),
            tuple(reversed(basis.largest_categories)),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                replace(basis, largest_categories=changed)

        single = self.builder.build(
            _outcome((_row(1, quantity=3, artist="A"), _row(2, artist="B")))[0]
        ).concentration.dimensions[0].copy_basis  # type: ignore[union-attr]
        self.assertEqual(tuple(item.category_id for item in single.largest_categories), ("A",))

    def test_workspace_links_complete_contributor_sequences_after_first_five(self):
        workspace = self.builder.build(
            _outcome(tuple(_row(value, quantity=8 - value, artist=f"Artist {value}") for value in range(1, 8)))[0]
        )
        distribution = workspace.distribution
        concentration = workspace.concentration
        assert distribution is not None and concentration is not None
        source = distribution.dimensions[0]
        dimension = concentration.dimensions[0]
        self.assertEqual(len(source.categories), 7)

        def install_basis(basis_name, basis):
            changed_dimension = replace(dimension, **{basis_name: basis})
            changed_concentration = replace(
                concentration,
                dimensions=(changed_dimension,) + concentration.dimensions[1:],
            )
            return replace(workspace, concentration=changed_concentration)

        release = dimension.release_basis
        release_tail = release.contributors[:5] + tuple(reversed(release.contributors[5:]))
        changed_release = replace(
            release,
            contributors=release_tail,
            largest_categories=release_tail,
        )
        with self.assertRaises(ValueError):
            install_basis("release_basis", changed_release)

        changed_categories = source.categories[:5] + tuple(reversed(source.categories[5:]))
        changed_source = replace(source, categories=changed_categories)
        changed_distribution = replace(
            distribution,
            dimensions=(changed_source,) + distribution.dimensions[1:],
        )
        with self.assertRaises(ValueError):
            replace(workspace, distribution=changed_distribution)

        for changed in (
            release.contributors[:-1],
            release.contributors + (release.contributors[-1],),
        ):
            with self.subTest(length=len(changed)), self.assertRaises(ValueError):
                replace(release, contributors=changed)

        for field, replacement in (
            ("category_id", "Substituted category"),
            ("label", "Substituted label"),
            ("release_ids", (999,)),
        ):
            contributors = release.contributors[:-1] + (
                replace(release.contributors[-1], **{field: replacement}),
            )
            changed = replace(release, contributors=contributors, largest_categories=contributors)
            with self.subTest(field=field), self.assertRaises(ValueError):
                install_basis("release_basis", changed)

        release_counts = release.contributors[:-2] + (
            replace(release.contributors[-2], membership_count=2),
            replace(release.contributors[-1], membership_count=0),
        )
        changed_release = replace(
            release,
            contributors=release_counts,
            largest_categories=(release_counts[-2],),
            largest_share=PresentedRatio(2, release.membership_total, Decimal(2) / Decimal(release.membership_total)),
        )
        with self.assertRaises(ValueError):
            install_basis("release_basis", changed_release)

        copy = dimension.copy_basis
        copy_counts = copy.contributors[:-2] + (
            replace(copy.contributors[-2], membership_count=copy.contributors[-2].membership_count + 1),
            replace(copy.contributors[-1], membership_count=copy.contributors[-1].membership_count - 1),
        )
        changed_copy = replace(copy, contributors=copy_counts)
        with self.assertRaises(ValueError):
            install_basis("copy_basis", changed_copy)

        self.assertEqual(
            tuple(item.category_id for item in release.contributors),
            tuple(item.category_id for item in source.categories),
        )
        for rows in ((), (_row(1),), (_row(1), _row(2), _row(3), _row(4))):
            self.assertTrue(self.builder.build(_outcome(rows)[0]).availability is PortfolioPresentationAvailability.AVAILABLE)

    def test_single_category_and_no_membership_are_not_fabricated_zero(self):
        single = self.builder.build(_outcome((_row(1),))[0]).concentration
        basis = single.dimensions[0].release_basis  # type: ignore[union-attr]
        self.assertEqual(basis.hhi.domain_value, Decimal("1"))
        self.assertEqual(basis.normalized_hhi.domain_value, Decimal("1"))
        self.assertEqual(basis.effective_category_count.domain_value, Decimal("1"))
        empty = self.builder.build(_outcome(())[0]).concentration
        self.assertEqual(empty.state, "insufficient_data")  # type: ignore[union-attr]
        self.assertEqual(empty.dimensions, ())  # type: ignore[union-attr]

    def test_non_finite_derived_value_is_retained_but_never_leaks_into_copy(self):
        outcome, _ = _outcome((_row(1), _row(2)))
        portfolio = outcome.portfolio
        assert portfolio is not None
        output = portfolio.concentration.output
        dimension = output.dimensions[0]
        difference = replace(dimension.difference, largest_category_share_delta=Decimal("NaN"))
        changed_output = replace(output, dimensions=(replace(dimension, difference=difference),) + output.dimensions[1:])
        changed = replace(portfolio, concentration=replace(portfolio.concentration, output=changed_output))
        view = self.builder.build(replace(outcome, portfolio=changed)).concentration
        presented = view.dimensions[0].difference.largest_category_share_delta  # type: ignore[union-attr]
        self.assertTrue(presented.domain_value.is_nan())
        self.assertEqual(presented.value_text, "Unavailable")
        self.assertEqual(presented.percentage, "Unavailable")

    def test_builder_has_no_query_write_provider_history_network_or_tk_boundary(self):
        outcome, repository = _outcome((_row(1),))
        before_modules = set(sys.modules)
        with (
            patch("socket.create_connection") as network,
            patch("builtins.open", wraps=open) as file_open,
        ):
            view = self.builder.build(outcome)
        self.assertIsNotNone(view.distribution)
        self.assertEqual(repository.reads, 1)
        network.assert_not_called()
        file_open.assert_not_called()
        self.assertNotIn("tkinter", set(sys.modules) - before_modules)
        for forbidden in ("execute", "refresh", "query", "write", "provider", "history"):
            self.assertFalse(hasattr(self.builder, forbidden))


if __name__ == "__main__":
    unittest.main()
