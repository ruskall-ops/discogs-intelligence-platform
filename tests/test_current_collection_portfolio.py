from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dip import __version__
from dip.app import (
    PORTFOLIO_EXECUTION_FAILURE_MESSAGE,
    CurrentCollectionContext,
    CurrentCollectionPortfolioExecutionService,
    CurrentCollectionPortfolioFailureStage,
    PortfolioConcentrationExecutionService,
    PortfolioDistributionExecutionService,
)
from dip.app.portfolio_concentration import PortfolioConcentrationExecutionEnvelope
from dip.composition import build_desktop_application_dependencies
from dip.intelligence import IntelligenceEngine, IntelligenceStatus
from dip.portfolio_intelligence import (
    PortfolioConcentrationEvidenceCoverage,
    PortfolioConcentrationModule,
    PortfolioDistributionEvidenceCoverage,
    PortfolioDistributionModule,
)
from dip.portfolio_intelligence.portfolio_concentration import (
    validate_portfolio_concentration_output,
)
from dip.portfolio_intelligence.portfolio_distribution import (
    validate_portfolio_distribution_output,
)
from dip.persistence.sqlite import Database


def _row(
    release_id: int,
    *,
    quantity: int = 1,
    artist: str | None = "Artist",
    label: str | None = "Label",
    format_value: str | None = "Vinyl",
    released: str | None = "2000",
) -> dict[str, object]:
    return {
        "release_id": release_id,
        "quantity": quantity,
        "artist": artist,
        "label": label,
        "format": format_value,
        "released": released,
    }


class _Collection:
    def __init__(self, rows: tuple[dict[str, object], ...]) -> None:
        self.rows = rows
        self.reads = 0

    def owned_portfolio_metadata_rows(self):
        self.reads += 1
        return self.rows


class _Engine:
    def __init__(self, module) -> None:
        self._engine = IntelligenceEngine((module,))
        self.contexts = []
        self.executions = []

    def execute(self, context):
        self.contexts.append(context)
        execution = self._engine.execute(context)
        self.executions.append(execution)
        return execution


def _coordinator(rows: tuple[dict[str, object], ...]):
    collection = _Collection(rows)
    distribution_engine = _Engine(PortfolioDistributionModule())
    concentration_engine = _Engine(PortfolioConcentrationModule())
    distribution = PortfolioDistributionExecutionService(
        collection,
        distribution_engine,
    )
    concentration = PortfolioConcentrationExecutionService(
        distribution,
        concentration_engine,
    )
    service = CurrentCollectionPortfolioExecutionService(
        CurrentCollectionContext(scope_id="current_collection"),
        distribution,
        concentration,
    )
    return (
        service,
        collection,
        distribution_engine,
        concentration_engine,
        concentration,
    )


def _valid_results(rows=(_row(1),)):
    service, _, distribution_engine, concentration_engine, _ = _coordinator(rows)
    outcome = service.execute()
    return (
        distribution_engine.executions[0].results[0],
        concentration_engine.executions[0].results[0],
        outcome.portfolio,
    )


class _StaticDistribution:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    def execute(self):
        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class _StaticConcentration:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0
        self.sources = []

    def execute_for_distribution(self, distribution):
        self.calls += 1
        self.sources.append(distribution)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result

    def execute_for_distribution_with_source(self, distribution):
        return PortfolioConcentrationExecutionEnvelope(
            distribution,
            self.execute_for_distribution(distribution),
        )


class CurrentCollectionContextTestCase(unittest.TestCase):
    def test_context_accepts_only_canonical_identity_and_is_immutable(self) -> None:
        context = CurrentCollectionContext(scope_id="current_collection")
        self.assertEqual(context.scope_id, "current_collection")
        with self.assertRaises(FrozenInstanceError):
            context.scope_id = "other"  # type: ignore[misc]
        for value, error in (
            ("other", ValueError),
            ("", ValueError),
            (1, TypeError),
            (True, TypeError),
            (None, TypeError),
        ):
            with self.subTest(value=value), self.assertRaises(error):
                CurrentCollectionContext(scope_id=value)  # type: ignore[arg-type]

        self.assertEqual(
            context,
            CurrentCollectionContext(scope_id="current_collection"),
        )
        self.assertEqual(
            hash(context),
            hash(CurrentCollectionContext(scope_id="current_collection")),
        )
        self.assertEqual(replace(context), context)
        with self.assertRaises(TypeError):
            CurrentCollectionContext("current_collection")  # type: ignore[misc]
        with self.assertRaises(ValueError):
            replace(context, scope_id="other")
        with self.assertRaises(TypeError):
            class DerivedContext(CurrentCollectionContext):
                pass


class CurrentCollectionPortfolioExecutionTestCase(unittest.TestCase):
    def test_success_reads_and_executes_each_boundary_once_atomically(self) -> None:
        (
            service,
            collection,
            distribution_engine,
            concentration_engine,
            concentration,
        ) = _coordinator((_row(1, quantity=2), _row(2, artist="Other")))
        supplied_distributions = []
        execute_for_distribution = concentration.execute_for_distribution

        def capture(distribution):
            supplied_distributions.append(distribution)
            return execute_for_distribution(distribution)

        concentration.execute_for_distribution = capture

        outcome = service.execute()

        self.assertTrue(outcome.succeeded)
        self.assertIs(outcome.portfolio, service.published)
        self.assertEqual(collection.reads, 1)
        self.assertEqual(len(distribution_engine.contexts), 1)
        self.assertEqual(len(concentration_engine.contexts), 1)
        portfolio = outcome.portfolio
        self.assertIsNotNone(portfolio)
        self.assertEqual(portfolio.context.scope_id, "current_collection")
        self.assertEqual(portfolio.distribution.module_id, "portfolio_distribution")
        self.assertEqual(portfolio.concentration.module_id, "portfolio_concentration")
        self.assertEqual(len(supplied_distributions), 1)
        self.assertIs(
            supplied_distributions[0],
            distribution_engine.executions[0].results[0],
        )
        supplied = concentration_engine.contexts[0].portfolio_concentration_input
        distribution_output = portfolio.distribution.metrics["output"]
        self.assertEqual(
            supplied.source_provenance.distribution_provenance,
            distribution_output.provenance,
        )
        self.assertEqual(
            supplied.dimensions,
            distribution_output.dimensions,
        )
        with self.assertRaises(FrozenInstanceError):
            portfolio.context = CurrentCollectionContext(  # type: ignore[misc]
                scope_id="current_collection"
            )

    def test_distribution_failure_is_safe_and_publishes_no_partial_pair(self) -> None:
        class Distribution:
            def execute(self):
                raise RuntimeError("private distribution detail")

        class Concentration:
            calls = 0

            def execute_for_distribution_with_source(self, distribution):
                self.calls += 1
                raise AssertionError("must not execute")

        concentration = Concentration()
        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"),
            Distribution(),
            concentration,
        )

        outcome = service.execute()

        self.assertFalse(outcome.succeeded)
        self.assertIsNone(outcome.portfolio)
        self.assertIsNone(service.published)
        self.assertIs(
            outcome.failure_stage,
            CurrentCollectionPortfolioFailureStage.DISTRIBUTION,
        )
        self.assertEqual(outcome.message, PORTFOLIO_EXECUTION_FAILURE_MESSAGE)
        self.assertNotIn("private", outcome.message)
        self.assertEqual(concentration.calls, 0)

    def test_later_failure_retains_identical_previous_successful_pair(self) -> None:
        service, collection, _, concentration_engine, _ = _coordinator((_row(1),))
        first = service.execute()
        previous = first.portfolio
        self.assertIsNotNone(previous)

        original_distribution_execute = service._distribution.execute

        def fail_distribution():
            raise RuntimeError("private distribution detail")

        service._distribution.execute = fail_distribution
        distribution_failed = service.execute()
        self.assertFalse(distribution_failed.succeeded)
        self.assertIs(distribution_failed.portfolio, previous)
        self.assertIs(service.published, previous)
        self.assertIs(
            distribution_failed.failure_stage,
            CurrentCollectionPortfolioFailureStage.DISTRIBUTION,
        )
        service._distribution.execute = original_distribution_execute

        original_execute = service._concentration.execute_for_distribution_with_source

        def fail(distribution):
            raise RuntimeError("private concentration detail")

        service._concentration.execute_for_distribution_with_source = fail
        failed = service.execute()

        self.assertFalse(failed.succeeded)
        self.assertIs(failed.portfolio, previous)
        self.assertIs(service.published, previous)
        self.assertIs(
            failed.failure_stage,
            CurrentCollectionPortfolioFailureStage.CONCENTRATION,
        )
        self.assertEqual(failed.message, PORTFOLIO_EXECUTION_FAILURE_MESSAGE)
        self.assertEqual(collection.reads, 2)
        self.assertEqual(len(concentration_engine.contexts), 1)

        service._concentration.execute_for_distribution_with_source = original_execute
        second = service.execute()
        self.assertTrue(second.succeeded)
        self.assertIsNot(second.portfolio, previous)

    def test_empty_and_partial_outputs_are_valid_atomic_results(self) -> None:
        empty_service, empty_collection, _, _, _ = _coordinator(())
        empty = empty_service.execute().portfolio
        self.assertIsNotNone(empty)
        self.assertIs(empty.distribution.status, IntelligenceStatus.SKIPPED)
        self.assertIs(empty.concentration.status, IntelligenceStatus.SKIPPED)
        self.assertIs(
            empty.distribution.metrics["output"].summary.evidence_coverage,
            PortfolioDistributionEvidenceCoverage.INSUFFICIENT,
        )
        self.assertIs(
            empty.concentration.metrics["output"].summary.evidence_coverage,
            PortfolioConcentrationEvidenceCoverage.INSUFFICIENT,
        )
        self.assertEqual(empty_collection.reads, 1)

        partial_service, partial_collection, _, _, _ = _coordinator(
            (
                _row(1, artist=None, label=None, format_value=None, released=None),
                _row(2),
            )
        )
        partial = partial_service.execute().portfolio
        self.assertIsNotNone(partial)
        self.assertIs(
            partial.distribution.metrics["output"].summary.evidence_coverage,
            PortfolioDistributionEvidenceCoverage.PARTIAL,
        )
        self.assertIs(
            partial.concentration.metrics["output"].summary.evidence_coverage,
            PortfolioConcentrationEvidenceCoverage.PARTIAL,
        )
        self.assertEqual(partial_collection.reads, 1)

        limited_service, _, _, _, _ = _coordinator(
            (_row(3, label=None, format_value=None, released=None),)
        )
        limited = limited_service.execute().portfolio
        self.assertIsNotNone(limited)
        self.assertIs(
            limited.distribution.metrics["output"].summary.evidence_coverage,
            PortfolioDistributionEvidenceCoverage.LIMITED,
        )

        insufficient_service, _, _, _, _ = _coordinator(
            (_row(4, artist=None, label=None, format_value=None, released=None),)
        )
        insufficient = insufficient_service.execute().portfolio
        self.assertIsNotNone(insufficient)
        self.assertIs(insufficient.distribution.status, IntelligenceStatus.SKIPPED)
        self.assertIs(insufficient.concentration.status, IntelligenceStatus.SKIPPED)

    def test_rejects_malformed_distribution_results_before_concentration(self) -> None:
        distribution, concentration, _ = _valid_results()
        output = distribution.metrics["output"]
        corrupt_output = copy.copy(output)
        object.__setattr__(corrupt_output, "rule_set_version", "unsupported")
        cases = (
            replace(distribution, status=IntelligenceStatus.FAILED),
            replace(distribution, status=IntelligenceStatus.SKIPPED),
            replace(distribution, module_id="other"),
            replace(distribution, module_version="other"),
            replace(distribution, metrics={}),
            replace(distribution, metrics={"output": object()}),
            replace(distribution, metrics={"output": output, "extra": 1}),
            replace(distribution, metrics={"output": corrupt_output}),
            replace(distribution, insights=["mutable"]),
        )
        for malformed in cases:
            with self.subTest(malformed=malformed):
                source = _StaticDistribution(malformed)
                target = _StaticConcentration(concentration)
                service = CurrentCollectionPortfolioExecutionService(
                    CurrentCollectionContext(scope_id="current_collection"),
                    source,
                    target,
                )
                outcome = service.execute()
                self.assertFalse(outcome.succeeded)
                self.assertIs(
                    outcome.failure_stage,
                    CurrentCollectionPortfolioFailureStage.DISTRIBUTION,
                )
                self.assertEqual(source.calls, 1)
                self.assertEqual(target.calls, 0)
                self.assertIsNone(service.published)

    def test_rejects_malformed_concentration_results_atomically(self) -> None:
        distribution, concentration, _ = _valid_results()
        output = concentration.metrics["output"]
        corrupt_output = copy.copy(output)
        object.__setattr__(corrupt_output, "rule_set_version", "unsupported")
        cases = (
            replace(concentration, status=IntelligenceStatus.FAILED),
            replace(concentration, status=IntelligenceStatus.SKIPPED),
            replace(concentration, module_id="other"),
            replace(concentration, module_version="other"),
            replace(concentration, metrics={}),
            replace(concentration, metrics={"output": object()}),
            replace(concentration, metrics={"output": output, "extra": 1}),
            replace(concentration, metrics={"output": corrupt_output}),
            replace(concentration, diagnostics=["mutable"]),
        )
        for malformed in cases:
            with self.subTest(malformed=malformed):
                source = _StaticDistribution(distribution)
                target = _StaticConcentration(malformed)
                service = CurrentCollectionPortfolioExecutionService(
                    CurrentCollectionContext(scope_id="current_collection"),
                    source,
                    target,
                )
                outcome = service.execute()
                self.assertFalse(outcome.succeeded)
                self.assertIs(
                    outcome.failure_stage,
                    CurrentCollectionPortfolioFailureStage.CONCENTRATION,
                )
                self.assertEqual(source.calls, 1)
                self.assertEqual(target.calls, 1)
                self.assertIs(target.sources[0], distribution)
                self.assertIsNone(service.published)

    def test_rejects_individually_valid_but_unlinked_results(self) -> None:
        distribution, _, _ = _valid_results((_row(1),))
        _, unrelated_concentration, _ = _valid_results((_row(2), _row(3)))
        source = _StaticDistribution(distribution)
        target = _StaticConcentration(unrelated_concentration)
        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"), source, target
        )

        outcome = service.execute()

        self.assertFalse(outcome.succeeded)
        self.assertIs(
            outcome.failure_stage,
            CurrentCollectionPortfolioFailureStage.CONCENTRATION,
        )
        self.assertIs(target.sources[0], distribution)
        self.assertIsNone(service.published)

    def test_rejects_source_inaccurate_concentration_coverage_and_state(self) -> None:
        distribution, concentration, _ = _valid_results((_row(1), _row(2)))
        output = concentration.metrics["output"]
        altered_outputs = (
            replace(
                output,
                summary=replace(
                    output.summary,
                    evidence_coverage=PortfolioConcentrationEvidenceCoverage.PARTIAL,
                ),
            ),
            replace(
                output,
                analysis_state=type(output.analysis_state).PARTIAL,
            ),
            replace(
                output,
                analysis_state=type(output.analysis_state).PARTIAL,
                summary=replace(
                    output.summary,
                    evidence_coverage=PortfolioConcentrationEvidenceCoverage.PARTIAL,
                ),
            ),
        )

        for altered_output in altered_outputs:
            with self.subTest(
                coverage=altered_output.summary.evidence_coverage,
                state=altered_output.analysis_state,
            ):
                source = _StaticDistribution(distribution)
                target = _StaticConcentration(
                    replace(concentration, metrics={"output": altered_output})
                )
                service = CurrentCollectionPortfolioExecutionService(
                    CurrentCollectionContext(scope_id="current_collection"),
                    source,
                    target,
                )

                outcome = service.execute()

                self.assertFalse(outcome.succeeded)
                self.assertIs(
                    outcome.failure_stage,
                    CurrentCollectionPortfolioFailureStage.CONCENTRATION,
                )
                self.assertEqual(target.calls, 1)
                self.assertIs(target.sources[0], distribution)
                self.assertIsNone(service.published)

        source = _StaticDistribution(distribution)
        target = _StaticConcentration(concentration)
        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"), source, target
        )
        previous = service.execute().portfolio
        self.assertIsNotNone(previous)
        target.result = replace(
            concentration,
            metrics={"output": altered_outputs[-1]},
        )

        failed = service.execute()

        self.assertFalse(failed.succeeded)
        self.assertIs(failed.portfolio, previous)
        self.assertIs(service.published, previous)
        self.assertEqual(target.calls, 2)

    def test_domain_validators_preserve_authoritative_nan_policy(self) -> None:
        distribution, concentration, _ = _valid_results((_row(1), _row(2)))
        validated_distribution = validate_portfolio_distribution_output(
            distribution.metrics["output"]
        )
        output = concentration.metrics["output"]
        dimension = output.dimensions[0]
        difference = replace(
            dimension.difference,
            largest_category_share_delta=Decimal("NaN"),
        )
        changed_output = replace(
            output,
            dimensions=(replace(dimension, difference=difference),)
            + output.dimensions[1:],
        )
        validated_concentration = validate_portfolio_concentration_output(
            changed_output
        )
        self.assertTrue(
            validated_concentration.dimensions[0]
            .difference.largest_category_share_delta.is_nan()
        )

        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"),
            _StaticDistribution(
                replace(distribution, metrics={"output": validated_distribution})
            ),
            _StaticConcentration(
                replace(concentration, metrics={"output": validated_concentration})
            ),
        )
        self.assertTrue(service.execute().succeeded)

    def test_revalidates_complete_typed_output_graphs_fail_closed(self) -> None:
        distribution, concentration, _ = _valid_results()
        malformed_outputs = []
        output = copy.copy(distribution.metrics["output"])
        object.__setattr__(output, "analysis_state", "complete")
        malformed_outputs.append(output)
        summary = copy.copy(distribution.metrics["output"].summary)
        object.__setattr__(summary, "evidence_coverage", "complete")
        output = copy.copy(distribution.metrics["output"])
        object.__setattr__(output, "summary", summary)
        malformed_outputs.append(output)
        ownership = copy.copy(distribution.metrics["output"].summary.ownership)
        object.__setattr__(ownership, "total_owned_copies", True)
        summary = copy.copy(distribution.metrics["output"].summary)
        object.__setattr__(summary, "ownership", ownership)
        output = copy.copy(distribution.metrics["output"])
        object.__setattr__(output, "summary", summary)
        malformed_outputs.append(output)
        dimension = copy.copy(distribution.metrics["output"].dimensions[0])
        entry = copy.copy(dimension.entries[0])
        object.__setattr__(entry, "release_ratio", Decimal("NaN"))
        object.__setattr__(dimension, "entries", (entry,) + dimension.entries[1:])
        output = copy.copy(distribution.metrics["output"])
        object.__setattr__(output, "dimensions", (dimension,) + output.dimensions[1:])
        malformed_outputs.append(output)

        for malformed_output in malformed_outputs:
            with self.subTest(output=type(malformed_output)):
                source = _StaticDistribution(
                    replace(distribution, metrics={"output": malformed_output})
                )
                target = _StaticConcentration(concentration)
                service = CurrentCollectionPortfolioExecutionService(
                    CurrentCollectionContext(scope_id="current_collection"),
                    source,
                    target,
                )
                outcome = service.execute()
                self.assertFalse(outcome.succeeded)
                self.assertEqual(source.calls, 1)
                self.assertEqual(target.calls, 0)
                self.assertIsNone(service.published)

        concentration_output = copy.copy(concentration.metrics["output"])
        object.__setattr__(concentration_output, "analysis_state", "complete")
        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"),
            _StaticDistribution(distribution),
            _StaticConcentration(
                replace(concentration, metrics={"output": concentration_output})
            ),
        )
        outcome = service.execute()
        self.assertFalse(outcome.succeeded)
        self.assertIs(
            outcome.failure_stage,
            CurrentCollectionPortfolioFailureStage.CONCENTRATION,
        )

    def test_snapshot_failure_and_base_exceptions_always_clear_guard(self) -> None:
        distribution, concentration, _ = _valid_results()
        source = _StaticDistribution(distribution)

        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"),
            source,
            _StaticConcentration(concentration),
        )
        previous = service.execute().portfolio
        self.assertIsNotNone(previous)
        previous_output = previous.distribution.metrics["output"]

        class MutatingConcentration(_StaticConcentration):
            def execute_for_distribution(self, supplied):
                result = super().execute_for_distribution(supplied)
                object.__setattr__(supplied, "summary", object())
                return result

        fresh_distribution, fresh_concentration, _ = _valid_results()
        source.result = fresh_distribution
        service._concentration = MutatingConcentration(fresh_concentration)
        failed = service.execute()
        self.assertFalse(failed.succeeded)
        self.assertIs(
            failed.failure_stage,
            CurrentCollectionPortfolioFailureStage.CONCENTRATION,
        )
        self.assertIs(failed.portfolio, previous)
        self.assertIs(service.published, previous)
        self.assertIs(previous.distribution.metrics["output"], previous_output)
        clean_distribution, clean_concentration, _ = _valid_results()
        source.result = clean_distribution
        service._concentration = _StaticConcentration(clean_concentration)
        self.assertTrue(service.execute().succeeded)
        previous = service.published

        source.result = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            service.execute()
        source.result = clean_distribution
        self.assertTrue(service.execute().succeeded)

        service._concentration = _StaticConcentration(SystemExit(7))
        with self.assertRaises(SystemExit):
            service.execute()
        service._concentration = _StaticConcentration(clean_concentration)
        recovered = service.execute()
        self.assertTrue(recovered.succeeded)
        self.assertIsNot(recovered.portfolio, previous)

    def test_published_pair_is_a_deeply_immutable_snapshot(self) -> None:
        distribution, concentration, _ = _valid_results()
        distribution_metrics = distribution.metrics
        concentration_metrics = concentration.metrics
        distribution_output = distribution.metrics["output"]
        concentration_output = concentration.metrics["output"]
        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"),
            _StaticDistribution(distribution),
            _StaticConcentration(concentration),
        )
        published = service.execute().portfolio
        self.assertIsNotNone(published)
        self.assertIsNot(published.distribution, distribution)
        self.assertIsNot(published.concentration, concentration)
        self.assertEqual(published.distribution.output, distribution_output)
        self.assertEqual(published.concentration.output, concentration_output)
        self.assertEqual(published.distribution.summary, distribution.summary)
        self.assertEqual(published.concentration.summary, concentration.summary)
        self.assertIs(distribution.metrics, distribution_metrics)
        self.assertIs(concentration.metrics, concentration_metrics)
        self.assertIs(distribution.metrics["output"], distribution_output)
        self.assertIs(concentration.metrics["output"], concentration_output)
        self.assertIsNot(published.distribution.metrics["output"], distribution_output)
        self.assertIsNot(published.concentration.metrics["output"], concentration_output)
        self.assertIs(
            concentration_output.provenance.distribution_provenance,
            distribution_output.provenance,
        )
        self.assertEqual(
            published.concentration.metrics["output"].provenance
            .distribution_provenance,
            published.distribution.metrics["output"].provenance,
        )
        with self.assertRaises(TypeError):
            published.distribution.metrics["new"] = object()  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            published.distribution.metrics["output"].dimensions[0].entries[
                0
            ].display_name = "changed"  # type: ignore[misc]
        self.assertIs(service.published, published)

    def test_overlap_and_same_thread_reentry_are_rejected_deterministically(self) -> None:
        distribution, concentration, _ = _valid_results()
        entered = Event()
        release = Event()

        class BlockingDistribution(_StaticDistribution):
            def execute(self):
                self.calls += 1
                entered.set()
                if not release.wait(5):
                    raise AssertionError("test did not release execution")
                return self.result

        source = BlockingDistribution(distribution)
        target = _StaticConcentration(concentration)
        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"), source, target
        )
        completed = []
        worker = Thread(target=lambda: completed.append(service.execute()))
        worker.start()
        self.assertTrue(entered.wait(5))
        overlap = service.execute()
        self.assertFalse(overlap.succeeded)
        self.assertIs(
            overlap.failure_stage,
            CurrentCollectionPortfolioFailureStage.EXECUTION_ACTIVE,
        )
        self.assertIsNone(overlap.portfolio)
        self.assertEqual(source.calls, 1)
        self.assertEqual(target.calls, 0)
        release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(completed[0].succeeded)

        class ReentrantDistribution(_StaticDistribution):
            nested = None

            def execute(inner_self):
                inner_self.calls += 1
                inner_self.nested = reentrant_service.execute()
                return inner_self.result

        reentrant_source = ReentrantDistribution(distribution)
        reentrant_target = _StaticConcentration(concentration)
        reentrant_service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"),
            reentrant_source,
            reentrant_target,
        )
        outer = reentrant_service.execute()
        self.assertTrue(outer.succeeded)
        self.assertFalse(reentrant_source.nested.succeeded)
        self.assertIs(
            reentrant_source.nested.failure_stage,
            CurrentCollectionPortfolioFailureStage.EXECUTION_ACTIVE,
        )
        self.assertEqual(reentrant_source.calls, 1)
        self.assertEqual(reentrant_target.calls, 1)

    def test_overlap_observes_the_pair_published_at_its_start(self) -> None:
        distribution, concentration, _ = _valid_results()
        source = _StaticDistribution(distribution)
        target = _StaticConcentration(concentration)
        service = CurrentCollectionPortfolioExecutionService(
            CurrentCollectionContext(scope_id="current_collection"), source, target
        )
        previous = service.execute().portfolio
        self.assertIsNotNone(previous)
        entered = Event()
        release = Event()

        def blocking_execute():
            source.calls += 1
            entered.set()
            if not release.wait(5):
                raise AssertionError("test did not release execution")
            raise RuntimeError("private later failure")

        source.execute = blocking_execute
        completed = []
        worker = Thread(target=lambda: completed.append(service.execute()))
        worker.start()
        self.assertTrue(entered.wait(5))
        overlap = service.execute()
        self.assertIs(overlap.portfolio, previous)
        self.assertIs(service.published, previous)
        release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertIs(completed[0].portfolio, previous)
        self.assertIs(service.published, previous)
        self.assertEqual(target.calls, 1)

    def test_execution_has_no_write_provider_or_history_boundary(self) -> None:
        service, collection, _, _, _ = _coordinator((_row(1),))

        for forbidden in (
            "import_releases",
            "start_analysis_run",
            "add_snapshot",
            "upsert_score",
            "record_execution",
            "provider_factory",
            "get_release",
        ):
            self.assertFalse(hasattr(service, forbidden))
            self.assertFalse(hasattr(collection, forbidden))
        outcome = service.execute()
        self.assertTrue(outcome.succeeded)

    def test_real_sqlite_execution_performs_one_read_and_no_writes(self) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "portfolio.sqlite3"
            database = Database(database_path)

            def manifest(connection):
                schema = tuple(
                    tuple(row)
                    for row in connection.execute(
                        """
                        SELECT type, name, tbl_name, sql
                        FROM sqlite_master
                        WHERE name NOT LIKE 'sqlite_%'
                        ORDER BY type, name
                        """
                    )
                )
                tables = tuple(
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                        """
                    )
                )
                contents = tuple(
                    (
                        table,
                        tuple(
                            tuple(row)
                            for row in connection.execute(
                                f'SELECT * FROM "{table}" ORDER BY rowid'
                            )
                        ),
                    )
                    for table in tables
                )
                return schema, contents

            try:
                database.import_releases(
                    (
                        {
                            "release_id": "1",
                            "Artist": "Artist",
                            "Title": "Title",
                            "Label": "Label",
                            "Format": "Vinyl",
                            "Released": "2000",
                        },
                    ),
                    "release_id",
                )
                distribution = PortfolioDistributionExecutionService(
                    database,
                    IntelligenceEngine((PortfolioDistributionModule(),)),
                )
                concentration = PortfolioConcentrationExecutionService(
                    distribution,
                    IntelligenceEngine((PortfolioConcentrationModule(),)),
                )
                service = CurrentCollectionPortfolioExecutionService(
                    CurrentCollectionContext(scope_id="current_collection"),
                    distribution,
                    concentration,
                )
                before = manifest(database.conn)
                table_names = tuple(table for table, _ in before[1])
                self.assertEqual(
                    table_names,
                    (
                        "analysis_runs",
                        "app_settings",
                        "collection_ownership",
                        "decisions",
                        "desktop_session",
                        "intelligence_results",
                        "intelligence_runs",
                        "market_snapshots",
                        "marketplace_snapshots",
                        "project_state",
                        "projects",
                        "releases",
                        "schema_migrations",
                        "scores",
                        "weekend_review_queue",
                    ),
                )
                changes = database.conn.total_changes
                statements = []
                with (
                    patch("dip.composition.DiscogsClient") as provider,
                    patch("socket.create_connection") as network,
                ):
                    database.conn.set_trace_callback(statements.append)
                    outcome = service.execute()
                    database.conn.set_trace_callback(None)
                after = manifest(database.conn)
                self.assertTrue(outcome.succeeded)
                self.assertEqual(database.conn.total_changes, changes)
                self.assertEqual(after, before)
                provider.assert_not_called()
                network.assert_not_called()
                portfolio_reads = [
                    statement
                    for statement in statements
                    if statement.lstrip().upper().startswith("SELECT")
                    and "COLLECTION_OWNERSHIP" in statement.upper()
                ]
                self.assertEqual(len(portfolio_reads), 1)
                self.assertFalse(
                    any(
                        statement.lstrip().upper().startswith(
                            ("INSERT", "UPDATE", "DELETE", "REPLACE")
                        )
                        for statement in statements
                    )
                )
            finally:
                database.close()
            for suffix in ("-journal", "-wal", "-shm"):
                self.assertFalse(Path(f"{database_path}{suffix}").exists())
            read_only = sqlite3.connect(
                f"file:{database_path}?mode=ro",
                uri=True,
            )
            try:
                read_only.execute("PRAGMA foreign_keys = ON")
                self.assertEqual(read_only.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(read_only.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(read_only.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(
                    tuple(
                        row[0]
                        for row in read_only.execute(
                            "SELECT version FROM schema_migrations ORDER BY version"
                        )
                    ),
                    tuple(range(1, 8)),
                )
                self.assertEqual(manifest(read_only), before)
            finally:
                read_only.close()
            self.assertEqual(tuple(Path(directory).iterdir()), (database_path,))


class CurrentCollectionPortfolioCompositionTestCase(unittest.TestCase):
    def test_composition_exposes_context_and_coordinator_without_execution(self) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "composition.sqlite3"
            with (
                patch(
                    "dip.composition.SETTINGS",
                    SimpleNamespace(
                        database_path=database_path,
                        application_version=__version__,
                        discogs_request_delay_seconds=0,
                    ),
                ),
                patch.object(
                    PortfolioDistributionExecutionService,
                    "execute",
                    side_effect=AssertionError("composition executed Distribution"),
                ) as distribution_execute,
                patch.object(
                    PortfolioConcentrationExecutionService,
                    "execute_for_distribution_with_source",
                    side_effect=AssertionError("composition executed Concentration"),
                ) as concentration_execute,
                patch.object(
                    Database,
                    "owned_portfolio_metadata_rows",
                    side_effect=AssertionError("composition queried Portfolio"),
                ) as portfolio_query,
                patch("dip.composition.DiscogsClient") as provider,
            ):
                dependencies = build_desktop_application_dependencies()
            try:
                coordinator = dependencies.current_collection_portfolio_execution
                self.assertIsInstance(
                    coordinator,
                    CurrentCollectionPortfolioExecutionService,
                )
                self.assertEqual(coordinator.context.scope_id, "current_collection")
                self.assertIsNone(coordinator.published)
                distribution_execute.assert_not_called()
                concentration_execute.assert_not_called()
                portfolio_query.assert_not_called()
                provider.assert_not_called()
            finally:
                dependencies.database.close()


if __name__ == "__main__":
    unittest.main()
