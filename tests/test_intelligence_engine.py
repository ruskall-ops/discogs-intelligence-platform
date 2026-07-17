from __future__ import annotations

import unittest

from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceRegistry,
    IntelligenceResult,
    IntelligenceStatus,
)


class _SuccessfulModule:
    module_id = "successful"
    module_version = "1.2"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=self.module_id,
            status=IntelligenceStatus.COMPLETED,
            summary="Analysis completed.",
            metrics={"release_count": len(context.collection)},
            evidence=("Prepared collection context",),
        )


class _FailingModule:
    module_id = "failing"
    module_version = "1.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        raise RuntimeError("controlled module failure")


class _LaterModule:
    module_id = "later"
    module_version = "2.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=self.module_id,
            status="completed",
            summary="Later module still ran.",
        )


class _InvalidResultModule:
    module_id = "invalid"
    module_version = "1.0"

    def analyse(self, context: IntelligenceContext):
        return {"status": "completed"}


class _MismatchedResultModule:
    module_id = "expected"
    module_version = "1.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        return IntelligenceResult(
            module_id="unexpected",
            status="completed",
            summary="Wrong identity.",
        )


class IntelligenceRegistryTestCase(unittest.TestCase):
    def test_registry_preserves_registration_order(self) -> None:
        registry = IntelligenceRegistry(
            [_SuccessfulModule(), _LaterModule()]
        )

        self.assertEqual(
            registry.module_ids,
            ("successful", "later"),
        )
        self.assertIsInstance(registry.get("successful"), _SuccessfulModule)

    def test_registry_rejects_duplicate_module_ids(self) -> None:
        registry = IntelligenceRegistry([_SuccessfulModule()])

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(_SuccessfulModule())

    def test_registry_can_unregister_a_module(self) -> None:
        registry = IntelligenceRegistry([_SuccessfulModule()])

        removed = registry.unregister("successful")

        self.assertIsInstance(removed, _SuccessfulModule)
        self.assertEqual(len(registry), 0)


class IntelligenceEngineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.context = IntelligenceContext(
            collection=({"release_id": 1001}, {"release_id": 1002}),
            analysis_run_id=42,
            filters={"collection_folder": "Main"},
        )

    def test_execute_returns_standard_execution_summary(self) -> None:
        execution = IntelligenceEngine([_SuccessfulModule()]).execute(
            self.context
        )

        self.assertEqual(execution.module_count, 1)
        self.assertEqual(execution.completed_count, 1)
        self.assertEqual(execution.failed_count, 0)
        self.assertTrue(execution.successful)
        self.assertEqual(
            execution.result_for("successful").metrics["release_count"],
            2,
        )
        self.assertEqual(
            execution.result_for("successful").module_version,
            "1.2",
        )

    def test_module_failure_does_not_stop_later_modules(self) -> None:
        execution = IntelligenceEngine(
            [_SuccessfulModule(), _FailingModule(), _LaterModule()]
        ).execute(self.context)

        self.assertEqual(
            tuple(result.module_id for result in execution.results),
            ("successful", "failing", "later"),
        )
        self.assertEqual(execution.completed_count, 2)
        self.assertEqual(execution.failed_count, 1)
        self.assertFalse(execution.successful)
        self.assertTrue(execution.result_for("failing").failed)
        self.assertIn(
            "RuntimeError: controlled module failure",
            execution.result_for("failing").diagnostics,
        )
        self.assertTrue(execution.result_for("later").succeeded)

    def test_invalid_result_is_isolated_as_failure(self) -> None:
        execution = IntelligenceEngine(
            [_InvalidResultModule(), _LaterModule()]
        ).execute(self.context)

        invalid = execution.result_for("invalid")

        self.assertTrue(invalid.failed)
        self.assertIn("TypeError", invalid.diagnostics[0])
        self.assertTrue(execution.result_for("later").succeeded)

    def test_mismatched_result_identity_is_isolated_as_failure(self) -> None:
        execution = IntelligenceEngine(
            [_MismatchedResultModule()]
        ).execute(self.context)

        result = execution.result_for("expected")

        self.assertTrue(result.failed)
        self.assertIn("ValueError", result.diagnostics[0])

    def test_run_preserves_tuple_result_api(self) -> None:
        results = IntelligenceEngine([_SuccessfulModule()]).run(self.context)

        self.assertIsInstance(results, tuple)
        self.assertEqual(results[0].module_id, "successful")


if __name__ == "__main__":
    unittest.main()
