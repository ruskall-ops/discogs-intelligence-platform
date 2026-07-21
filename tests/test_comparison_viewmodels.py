from __future__ import annotations

import unittest
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from typing import Any

from dip.app import HistoricalIntelligenceExecution
from dip.comparison import (
    ComparisonEngine,
    ComparisonResult,
    ExecutionComparison,
    ValueChange,
)
from dip.experience.comparison import (
    ComparisonValueAvailability,
    ComparisonViewModelBuilder,
    ComparisonViewModelConsistencyError,
    ExecutionComparisonViewModel,
    FieldChangeViewModel,
    ModuleComparisonState,
    ModuleComparisonViewModel,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)


class ComparisonViewModelBuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ComparisonViewModelBuilder()
        self.engine = ComparisonEngine()

    def test_identical_comparison_has_unchanged_execution_summary(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(self._record(2, 0, "collection_health"),),
        )

        view_model = self.builder.build(comparison)

        self.assertFalse(view_model.has_changes)
        self.assertEqual(view_model.total_module_count, 1)
        self.assertEqual(view_model.changed_module_count, 0)
        self.assertEqual(view_model.unchanged_module_count, 1)
        self.assertEqual(view_model.added_module_count, 0)
        self.assertEqual(view_model.removed_module_count, 0)

    def test_one_changed_module_updates_execution_and_module_counts(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(
                self._record(
                    2,
                    0,
                    "collection_health",
                    summary="Changed summary.",
                ),
            ),
        )

        view_model = self.builder.build(comparison)

        self.assertTrue(view_model.has_changes)
        self.assertEqual(view_model.changed_module_count, 1)
        self.assertEqual(view_model.unchanged_module_count, 0)
        module = view_model.modules[0]
        self.assertIs(module.state, ModuleComparisonState.CHANGED)
        self.assertTrue(module.has_changes)
        self.assertEqual(module.changed_field_count, 1)
        self.assertEqual(module.unchanged_field_count, 4)

    def test_mixed_module_states_and_counts_are_disjoint(self) -> None:
        comparison = self._comparison(
            previous=(
                self._record(1, 0, "collection_health"),
                self._record(1, 1, "hidden_gems"),
                self._record(1, 2, "removed_module"),
            ),
            current=(
                self._record(
                    2,
                    0,
                    "collection_health",
                    metrics={"score": 81},
                ),
                self._record(2, 1, "hidden_gems"),
                self._record(2, 2, "added_module"),
            ),
        )

        view_model = self.builder.build(comparison)

        self.assertEqual(view_model.total_module_count, 4)
        self.assertEqual(view_model.changed_module_count, 1)
        self.assertEqual(view_model.unchanged_module_count, 1)
        self.assertEqual(view_model.added_module_count, 1)
        self.assertEqual(view_model.removed_module_count, 1)
        self.assertEqual(
            tuple(module.state for module in view_model.modules),
            (
                ModuleComparisonState.CHANGED,
                ModuleComparisonState.UNCHANGED,
                ModuleComparisonState.ADDED,
                ModuleComparisonState.REMOVED,
            ),
        )

    def test_run_context_and_module_versions_are_preserved(self) -> None:
        comparison = self._comparison(
            previous=(
                self._record(
                    1,
                    0,
                    "collection_health",
                    module_version="1.0",
                ),
            ),
            current=(
                self._record(
                    2,
                    0,
                    "collection_health",
                    module_version="1.1",
                ),
            ),
        )

        view_model = self.builder.build(comparison)

        self.assertEqual(view_model.current_run_id, 2)
        self.assertEqual(view_model.previous_run_id, 1)
        self.assertEqual(
            view_model.current_executed_at,
            datetime(2026, 7, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(
            view_model.previous_executed_at,
            datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(view_model.modules[0].previous_module_version, "1.0")
        self.assertEqual(view_model.modules[0].current_module_version, "1.1")

    def test_generic_fields_use_stable_non_alphabetical_order(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(self._record(2, 0, "collection_health"),),
        )

        fields = self.builder.build(comparison).modules[0].fields

        self.assertEqual(
            tuple(field.field_id for field in fields),
            ("status", "summary", "metrics", "evidence", "diagnostics"),
        )
        self.assertEqual(
            tuple(field.label for field in fields),
            ("Status", "Summary", "Metrics", "Evidence", "Diagnostics"),
        )

    def test_field_values_and_changed_flags_are_preserved(self) -> None:
        comparison = self._comparison(
            previous=(
                self._record(
                    1,
                    0,
                    "collection_health",
                    metrics={"score": 80, "nested": {"series": [79, 80]}},
                ),
            ),
            current=(
                self._record(
                    2,
                    0,
                    "collection_health",
                    metrics={"score": 82, "nested": {"series": [80, 82]}},
                ),
            ),
        )

        metrics = self._field(self.builder.build(comparison), "metrics")

        self.assertEqual(metrics.previous_value["score"], 80)
        self.assertEqual(metrics.current_value["score"], 82)
        self.assertTrue(metrics.changed)
        self.assertIs(
            metrics.previous_availability,
            ComparisonValueAvailability.AVAILABLE,
        )
        self.assertIs(
            metrics.current_availability,
            ComparisonValueAvailability.AVAILABLE,
        )

    def test_added_module_has_explicit_unavailable_previous_values(self) -> None:
        comparison = self._comparison(
            previous=(),
            current=(self._record(2, 0, "hidden_gems"),),
        )

        module = self.builder.build(comparison).modules[0]

        self.assertIs(module.state, ModuleComparisonState.ADDED)
        self.assertTrue(module.has_changes)
        self.assertTrue(
            all(
                field.previous_availability
                is ComparisonValueAvailability.UNAVAILABLE
                for field in module.fields
            )
        )
        self.assertTrue(
            all(
                field.current_availability
                is ComparisonValueAvailability.AVAILABLE
                for field in module.fields
            )
        )
        self.assertTrue(all(field.previous_value is None for field in module.fields))

    def test_removed_module_has_explicit_unavailable_current_values(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "hidden_gems"),),
            current=(),
        )

        module = self.builder.build(comparison).modules[0]

        self.assertIs(module.state, ModuleComparisonState.REMOVED)
        self.assertTrue(
            all(
                field.previous_availability
                is ComparisonValueAvailability.AVAILABLE
                for field in module.fields
            )
        )
        self.assertTrue(
            all(
                field.current_availability
                is ComparisonValueAvailability.UNAVAILABLE
                for field in module.fields
            )
        )

    def test_legitimate_none_is_available_not_unavailable(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(self._record(2, 0, "collection_health"),),
        )
        module = comparison.modules[0]
        comparison_with_none = replace(
            comparison,
            modules=(
                replace(
                    module,
                    summary=ValueChange(previous=None, current=None),
                ),
            ),
        )

        summary = self._field(
            self.builder.build(comparison_with_none),
            "summary",
        )

        self.assertIsNone(summary.previous_value)
        self.assertIsNone(summary.current_value)
        self.assertIs(
            summary.previous_availability,
            ComparisonValueAvailability.AVAILABLE,
        )
        self.assertIs(
            summary.current_availability,
            ComparisonValueAvailability.AVAILABLE,
        )
        self.assertFalse(summary.changed)

    def test_known_and_fallback_module_labels_preserve_canonical_ids(self) -> None:
        comparison = self._comparison(
            previous=(
                self._record(1, 0, "collection_health"),
                self._record(1, 1, "future_signal_module"),
            ),
            current=(
                self._record(2, 0, "collection_health"),
                self._record(2, 1, "future_signal_module"),
            ),
        )

        modules = self.builder.build(comparison).modules

        self.assertEqual(modules[0].module_id, "collection_health")
        self.assertEqual(modules[0].label, "Collection Health")
        self.assertEqual(modules[1].module_id, "future_signal_module")
        self.assertEqual(modules[1].label, "Future Signal Module")

    def test_explicit_label_overrides_are_deterministic(self) -> None:
        builder = ComparisonViewModelBuilder(
            module_labels={"future_module": "Future Module Result"},
            field_labels={"metrics": "Structured Metrics"},
        )
        comparison = self._comparison(
            previous=(self._record(1, 0, "future_module"),),
            current=(self._record(2, 0, "future_module"),),
        )

        module = builder.build(comparison).modules[0]

        self.assertEqual(module.label, "Future Module Result")
        self.assertEqual(
            self._field_from_module(module, "metrics").label,
            "Structured Metrics",
        )

    def test_output_is_deterministic_and_preserves_module_order(self) -> None:
        comparison = self._comparison(
            previous=(
                self._record(1, 0, "module_a"),
                self._record(1, 1, "removed_module"),
                self._record(1, 2, "module_b"),
            ),
            current=(
                self._record(2, 0, "module_b"),
                self._record(2, 1, "module_a"),
            ),
        )

        first = self.builder.build(comparison)
        second = self.builder.build(comparison)

        self.assertEqual(first, second)
        self.assertEqual(
            tuple(module.module_id for module in first.modules),
            ("module_b", "module_a", "removed_module"),
        )

    def test_view_models_and_nested_values_are_immutable(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(self._record(2, 0, "collection_health"),),
        )
        view_model = self.builder.build(comparison)
        metrics = self._field(view_model, "metrics")

        with self.assertRaises(FrozenInstanceError):
            view_model.has_changes = True
        with self.assertRaises(FrozenInstanceError):
            view_model.modules[0].label = "Changed"
        with self.assertRaises(TypeError):
            metrics.current_value["score"] = 99

    def test_duplicate_comparison_modules_are_rejected(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(self._record(2, 0, "collection_health"),),
        )
        object.__setattr__(
            comparison,
            "modules",
            (comparison.modules[0], comparison.modules[0]),
        )

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "Duplicate comparison module",
        ):
            self.builder.build(comparison)

    def test_duplicate_field_ids_are_rejected(self) -> None:
        field = self._available_field("summary", changed=False)

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "unique field IDs",
        ):
            ModuleComparisonViewModel(
                module_id="collection_health",
                label="Collection Health",
                state=ModuleComparisonState.UNCHANGED,
                has_changes=False,
                fields=(field, field),
                changed_field_count=0,
                unchanged_field_count=2,
            )

    def test_inconsistent_module_state_is_rejected(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(self._record(2, 0, "collection_health"),),
        )
        object.__setattr__(
            comparison.modules[0],
            "result",
            ComparisonResult.CHANGED,
        )

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "has no changed fields",
        ):
            self.builder.build(comparison)

    def test_inconsistent_changed_flags_are_rejected(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(
                self._record(
                    2,
                    0,
                    "collection_health",
                    summary="Changed summary.",
                ),
            ),
        )
        object.__setattr__(comparison.modules[0].summary, "changed", False)

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "has no changed fields",
        ):
            self.builder.build(comparison)

    def test_malformed_added_module_is_rejected(self) -> None:
        comparison = self._comparison(
            previous=(),
            current=(self._record(2, 0, "added_module"),),
        )
        object.__setattr__(
            comparison.modules[0],
            "previous_record",
            self._record(1, 0, "added_module"),
        )

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "Added module.*malformed",
        ):
            self.builder.build(comparison)

    def test_malformed_removed_module_is_rejected(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "removed_module"),),
            current=(),
        )
        object.__setattr__(
            comparison.modules[0],
            "current_record",
            self._record(2, 0, "removed_module"),
        )

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "Removed module.*malformed",
        ):
            self.builder.build(comparison)

    def test_inconsistent_execution_counts_are_rejected(self) -> None:
        field = self._available_field("summary", changed=False)
        module = ModuleComparisonViewModel(
            module_id="collection_health",
            label="Collection Health",
            state=ModuleComparisonState.UNCHANGED,
            has_changes=False,
            fields=(field,),
            changed_field_count=0,
            unchanged_field_count=1,
        )

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "total_module_count",
        ):
            ExecutionComparisonViewModel(
                current_run_id=2,
                previous_run_id=1,
                current_executed_at=datetime(2026, 7, 2),
                previous_executed_at=datetime(2026, 7, 1),
                has_changes=False,
                total_module_count=2,
                changed_module_count=0,
                unchanged_module_count=1,
                added_module_count=0,
                removed_module_count=0,
                modules=(module,),
            )

    def test_inconsistent_module_field_counts_are_rejected(self) -> None:
        field = self._available_field("summary", changed=True)

        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "changed_field_count",
        ):
            ModuleComparisonViewModel(
                module_id="collection_health",
                label="Collection Health",
                state=ModuleComparisonState.CHANGED,
                has_changes=True,
                fields=(field,),
                changed_field_count=0,
                unchanged_field_count=1,
            )

    def test_unsupported_comparison_shape_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ComparisonViewModelConsistencyError,
            "requires an ExecutionComparison",
        ):
            self.builder.build(object())

    def test_value_copy_failure_has_a_useful_cause(self) -> None:
        comparison = self._comparison(
            previous=(self._record(1, 0, "collection_health"),),
            current=(self._record(2, 0, "collection_health"),),
        )
        object.__setattr__(comparison.modules[0].metrics, "current", object())

        with self.assertRaises(ComparisonViewModelConsistencyError) as raised:
            self.builder.build(comparison)

        self.assertIsInstance(raised.exception.__cause__, TypeError)

    def _comparison(
        self,
        *,
        previous: tuple[IntelligenceHistoryRecord, ...],
        current: tuple[IntelligenceHistoryRecord, ...],
    ) -> ExecutionComparison:
        return self.engine.compare(
            self._execution(2, current),
            self._execution(1, previous),
        )

    @staticmethod
    def _execution(
        run_id: int,
        records: tuple[IntelligenceHistoryRecord, ...],
    ) -> HistoricalIntelligenceExecution:
        return HistoricalIntelligenceExecution(
            run=IntelligenceHistoryRun(
                run_id=run_id,
                executed_at=datetime(2026, 7, run_id, tzinfo=timezone.utc),
                result_count=len(records),
            ),
            records=records,
        )

    @staticmethod
    def _record(
        run_id: int,
        index: int,
        module_id: str,
        *,
        summary: str = "Stable summary.",
        metrics: Mapping[str, Any] | None = None,
        module_version: str | None = "1.0",
    ) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=run_id * 100 + index + 1,
            run_id=run_id,
            module_id=module_id,
            module_version=module_version,
            status=IntelligenceStatus.COMPLETED,
            summary=summary,
            metrics={"score": 80} if metrics is None else metrics,
            evidence=("Stable evidence",),
            diagnostics=(),
        )

    @staticmethod
    def _field(
        view_model: ExecutionComparisonViewModel,
        field_id: str,
    ) -> FieldChangeViewModel:
        return ComparisonViewModelBuilderTestCase._field_from_module(
            view_model.modules[0],
            field_id,
        )

    @staticmethod
    def _field_from_module(
        module: ModuleComparisonViewModel,
        field_id: str,
    ) -> FieldChangeViewModel:
        return next(field for field in module.fields if field.field_id == field_id)

    @staticmethod
    def _available_field(
        field_id: str,
        *,
        changed: bool,
    ) -> FieldChangeViewModel:
        return FieldChangeViewModel(
            field_id=field_id,
            label=field_id.title(),
            previous_value="previous",
            current_value="current" if changed else "previous",
            previous_availability=ComparisonValueAvailability.AVAILABLE,
            current_availability=ComparisonValueAvailability.AVAILABLE,
            changed=changed,
        )


if __name__ == "__main__":
    unittest.main()
