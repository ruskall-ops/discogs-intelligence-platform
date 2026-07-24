from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import datetime, timezone

from dip.app import HistoricalIntelligenceExecution
from dip.comparison import (
    ComparisonEngine,
    ComparisonRegistry,
    ComparisonResult,
    ExecutionComparison,
    GenericModuleComparer,
    ModuleComparer,
    ModuleComparison,
    ValueChange,
    build_default_comparison_registry,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
    IntelligenceSerializationError,
)


@dataclass(frozen=True)
class _RawExecution:
    run: IntelligenceHistoryRun
    records: tuple[IntelligenceHistoryRecord, ...]


class _TrackingComparer:
    module_id = "collection_health"

    def __init__(self) -> None:
        self.calls: list[
            tuple[
                IntelligenceHistoryRecord | None,
                IntelligenceHistoryRecord | None,
            ]
        ] = []

    def compare(
        self,
        previous: IntelligenceHistoryRecord | None,
        current: IntelligenceHistoryRecord | None,
    ) -> ModuleComparison:
        self.calls.append((previous, current))
        return GenericModuleComparer(self.module_id).compare(previous, current)


class _InvalidComparer:
    module_id = "invalid"


class ComparisonModelsTestCase(unittest.TestCase):
    def test_value_change_computes_change_and_freezes_nested_values(self) -> None:
        previous = {"nested": {"values": [1, 2]}}
        current = {"nested": {"values": [1, 3]}}

        change = ValueChange(previous=previous, current=current)
        previous["nested"]["values"].append(99)

        self.assertTrue(change.changed)
        self.assertEqual(change.previous["nested"]["values"], (1, 2))
        with self.assertRaises(TypeError):
            change.previous["new"] = "value"
        with self.assertRaises(FrozenInstanceError):
            change.current = None

    def test_value_change_rejects_unsupported_values(self) -> None:
        with self.assertRaises(IntelligenceSerializationError):
            ValueChange(previous=object(), current=None)

    def test_value_change_preserves_structural_type_differences(self) -> None:
        self.assertTrue(ValueChange(previous=True, current=1).changed)
        self.assertTrue(ValueChange(previous=1, current=1.0).changed)

        previous = {"b": 2, "a": 1}
        current = {"a": 1, "b": 2}
        self.assertFalse(ValueChange(previous=previous, current=current).changed)

    def test_module_comparison_rejects_inconsistent_result(self) -> None:
        previous = self._record(10, 1, "collection_health")
        current = self._record(20, 2, "collection_health")
        comparison = GenericModuleComparer("collection_health").compare(
            previous,
            current,
        )

        with self.assertRaisesRegex(ValueError, "result must be"):
            replace(comparison, result=ComparisonResult.ADDED)

    def test_execution_comparison_detaches_module_collection(self) -> None:
        previous = self._execution(1, ("collection_health",))
        current = self._execution(2, ("collection_health",))
        module = GenericModuleComparer("collection_health").compare(
            previous.records[0],
            current.records[0],
        )
        mutable_modules = [module]

        comparison = ExecutionComparison(
            previous_run=previous.run,
            current_run=current.run,
            modules=mutable_modules,
        )
        mutable_modules.clear()

        self.assertEqual(comparison.modules, (module,))

    @classmethod
    def _execution(
        cls,
        run_id: int,
        module_ids: tuple[str, ...],
    ) -> HistoricalIntelligenceExecution:
        records = tuple(
            cls._record(run_id * 10 + index, run_id, module_id)
            for index, module_id in enumerate(module_ids)
        )
        return HistoricalIntelligenceExecution(
            run=cls._run(run_id, len(records)),
            records=records,
        )

    @staticmethod
    def _run(run_id: int, result_count: int) -> IntelligenceHistoryRun:
        return IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=datetime(2026, 7, run_id, tzinfo=timezone.utc),
            result_count=result_count,
        )

    @staticmethod
    def _record(
        record_id: int,
        run_id: int,
        module_id: str,
    ) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=record_id,
            run_id=run_id,
            module_id=module_id,
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Stable summary.",
            metrics={"score": 80},
            evidence=("Stable evidence",),
            diagnostics=(),
        )


class ComparisonRegistryTestCase(unittest.TestCase):
    def test_registry_preserves_registration_order_and_protocol(self) -> None:
        first = _TrackingComparer()
        second = GenericModuleComparer("hidden_gems")
        registry = ComparisonRegistry((first, second))
        comparer: ModuleComparer = registry.get("collection_health")

        self.assertIs(comparer, first)
        self.assertEqual(
            registry.module_ids,
            ("collection_health", "hidden_gems"),
        )
        self.assertEqual(tuple(registry), (first, second))

    def test_registry_rejects_duplicate_and_invalid_comparers(self) -> None:
        registry = ComparisonRegistry((GenericModuleComparer("hidden_gems"),))

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(GenericModuleComparer("hidden_gems"))
        with self.assertRaisesRegex(TypeError, "define compare"):
            registry.register(_InvalidComparer())

    def test_default_registry_explicitly_registers_current_modules(self) -> None:
        registry = build_default_comparison_registry()

        self.assertEqual(
            registry.module_ids,
            (
                "collection_health",
                "hidden_gems",
                "historical_intelligence",
            ),
        )
        self.assertTrue(
            all(isinstance(comparer, GenericModuleComparer) for comparer in registry)
        )

    def test_missing_comparer_uses_generic_fallback_without_mutating_registry(
        self,
    ) -> None:
        registry = build_default_comparison_registry()

        comparer = registry.get("future_module")

        self.assertIsInstance(comparer, GenericModuleComparer)
        self.assertEqual(comparer.module_id, "future_module")
        self.assertNotIn("future_module", registry.module_ids)


class GenericModuleComparerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = self._record(10, 1)
        self.current = self._record(20, 2)
        self.comparer = GenericModuleComparer("collection_health")

    def test_identical_records_are_unchanged(self) -> None:
        comparison = self.comparer.compare(self.previous, self.current)

        self.assertIs(comparison.result, ComparisonResult.UNCHANGED)
        self.assertFalse(comparison.status.changed)
        self.assertFalse(comparison.summary.changed)
        self.assertFalse(comparison.metrics.changed)
        self.assertFalse(comparison.evidence.changed)
        self.assertFalse(comparison.diagnostics.changed)

    def test_changed_summary_exposes_previous_and_current_values(self) -> None:
        current = replace(self.current, summary="Changed summary.")

        comparison = self.comparer.compare(self.previous, current)

        self.assertIs(comparison.result, ComparisonResult.CHANGED)
        self.assertEqual(comparison.summary.previous, "Stable summary.")
        self.assertEqual(comparison.summary.current, "Changed summary.")
        self.assertTrue(comparison.summary.changed)

    def test_changed_metrics_are_structural_without_a_delta(self) -> None:
        current = replace(self.current, metrics={"score": 83})

        comparison = self.comparer.compare(self.previous, current)

        self.assertEqual(dict(comparison.metrics.previous), {"score": 80})
        self.assertEqual(dict(comparison.metrics.current), {"score": 83})
        self.assertTrue(comparison.metrics.changed)
        self.assertFalse(hasattr(comparison.metrics, "delta"))

    def test_changed_evidence_and_diagnostics_are_detected(self) -> None:
        current = replace(
            self.current,
            evidence=("New evidence",),
            diagnostics=("New diagnostic",),
        )

        comparison = self.comparer.compare(self.previous, current)

        self.assertTrue(comparison.evidence.changed)
        self.assertEqual(comparison.evidence.current, ("New evidence",))
        self.assertTrue(comparison.diagnostics.changed)
        self.assertEqual(
            comparison.diagnostics.current,
            ("New diagnostic",),
        )

    def test_changed_status_is_detected_without_interpretation(self) -> None:
        current = replace(self.current, status=IntelligenceStatus.SKIPPED)

        comparison = self.comparer.compare(self.previous, current)

        self.assertTrue(comparison.status.changed)
        self.assertIs(comparison.status.previous, IntelligenceStatus.COMPLETED)
        self.assertIs(comparison.status.current, IntelligenceStatus.SKIPPED)

    def test_added_module_is_explicit(self) -> None:
        comparison = self.comparer.compare(None, self.current)

        self.assertIs(comparison.result, ComparisonResult.ADDED)
        self.assertIsNone(comparison.previous_record)
        self.assertIsNone(comparison.summary.previous)
        self.assertEqual(comparison.summary.current, "Stable summary.")

    def test_removed_module_is_explicit(self) -> None:
        comparison = self.comparer.compare(self.previous, None)

        self.assertIs(comparison.result, ComparisonResult.REMOVED)
        self.assertIsNone(comparison.current_record)
        self.assertEqual(comparison.summary.previous, "Stable summary.")
        self.assertIsNone(comparison.summary.current)

    @staticmethod
    def _record(record_id: int, run_id: int) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=record_id,
            run_id=run_id,
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Stable summary.",
            metrics={"score": 80},
            evidence=("Stable evidence",),
            diagnostics=(),
        )


class ComparisonEngineTestCase(unittest.TestCase):
    def test_engine_dispatches_registered_comparer(self) -> None:
        comparer = _TrackingComparer()
        engine = ComparisonEngine(
            ComparisonRegistry(
                (comparer,),
                fallback_factory=GenericModuleComparer,
            )
        )
        previous = self._execution(1, ("collection_health",))
        current = self._execution(2, ("collection_health",))

        result = engine.compare(current, previous)

        self.assertEqual(
            comparer.calls,
            [(previous.records[0], current.records[0])],
        )
        self.assertIsInstance(result, ExecutionComparison)

    def test_engine_uses_generic_comparer_for_unknown_module(self) -> None:
        previous = self._execution(1, ("future_module",))
        current = self._execution(2, ("future_module",))

        result = ComparisonEngine().compare(current, previous)

        self.assertEqual(result.modules[0].module_id, "future_module")
        self.assertIs(result.modules[0].result, ComparisonResult.UNCHANGED)

    def test_engine_preserves_current_order_then_previous_removed_order(self) -> None:
        previous = self._execution(
            1,
            ("module_a", "module_b", "removed_a", "removed_b"),
        )
        current = self._execution(
            2,
            ("module_b", "module_a", "added"),
        )

        result = ComparisonEngine().compare(current, previous)

        self.assertEqual(
            tuple(module.module_id for module in result.modules),
            ("module_b", "module_a", "added", "removed_a", "removed_b"),
        )
        self.assertIs(result.modules[2].result, ComparisonResult.ADDED)
        self.assertIs(result.modules[3].result, ComparisonResult.REMOVED)

    def test_engine_rejects_comparing_the_same_run(self) -> None:
        execution = self._execution(1, ("collection_health",))

        with self.assertRaisesRegex(ValueError, "with itself"):
            ComparisonEngine().compare(execution, execution)

    def test_engine_rejects_result_count_mismatch(self) -> None:
        execution = self._execution(1, ("collection_health",))
        invalid = _RawExecution(
            run=replace(execution.run, result_count=2),
            records=execution.records,
        )

        with self.assertRaisesRegex(ValueError, "result_count"):
            ComparisonEngine().compare(self._execution(2, ()), invalid)

    def test_engine_rejects_duplicate_modules(self) -> None:
        run = self._run(1, 2)
        invalid = _RawExecution(
            run=run,
            records=(
                self._record(10, 1, "collection_health"),
                self._record(11, 1, "collection_health"),
            ),
        )

        with self.assertRaisesRegex(ValueError, "duplicate module"):
            ComparisonEngine().compare(self._execution(2, ()), invalid)

    def test_engine_rejects_record_associated_with_wrong_run(self) -> None:
        invalid = _RawExecution(
            run=self._run(1, 1),
            records=(self._record(10, 9, "collection_health"),),
        )

        with self.assertRaisesRegex(ValueError, "wrong run"):
            ComparisonEngine().compare(self._execution(2, ()), invalid)

    @classmethod
    def _execution(
        cls,
        run_id: int,
        module_ids: tuple[str, ...],
    ) -> HistoricalIntelligenceExecution:
        records = tuple(
            cls._record(run_id * 100 + index, run_id, module_id)
            for index, module_id in enumerate(module_ids)
        )
        return HistoricalIntelligenceExecution(
            run=cls._run(run_id, len(records)),
            records=records,
        )

    @staticmethod
    def _run(run_id: int, result_count: int) -> IntelligenceHistoryRun:
        return IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=datetime(2026, 7, run_id, tzinfo=timezone.utc),
            result_count=result_count,
        )

    @staticmethod
    def _record(
        record_id: int,
        run_id: int,
        module_id: str,
    ) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=record_id,
            run_id=run_id,
            module_id=module_id,
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Stable summary.",
            metrics={"score": 80},
            evidence=("Stable evidence",),
            diagnostics=(),
        )


if __name__ == "__main__":
    unittest.main()
