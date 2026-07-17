from __future__ import annotations

import unittest

from dip.intelligence.context import IntelligenceContext
from dip.intelligence.engine import IntelligenceEngine
from dip.intelligence.models import IntelligenceResult


class _ExampleModule:
    module_id = "example"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=self.module_id,
            status="completed",
            summary=f"Analysed {len(context.collection)} releases",
        )


class PackageStructureTestCase(unittest.TestCase):
    def test_intelligence_engine_uses_standard_context_and_result(self) -> None:
        context = IntelligenceContext(collection=({"release_id": 1},))
        results = IntelligenceEngine([_ExampleModule()]).run(context)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].module_id, "example")
        self.assertEqual(results[0].summary, "Analysed 1 releases")


if __name__ == "__main__":
    unittest.main()
