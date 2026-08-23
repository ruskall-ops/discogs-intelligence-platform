"""Run the mandatory Slice 4 production-Tk acceptance suite."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EXPECTED_TESTS = 7
TEST_NAME = (
    "tests.test_results_presentation_dashboard_review."
    "Slice4ProductionTkTestCase"
)


def main() -> int:
    if os.environ.get("DIP_REQUIRE_TK_TESTS") != "1":
        print("DIP_REQUIRE_TK_TESTS=1 is required.", file=sys.stderr)
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromName(TEST_NAME)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = max(
        0,
        result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
    )
    counts = (
        f"run={result.testsRun} pass={passed} "
        f"skip={len(result.skipped)} error={len(result.errors)} failure={len(result.failures)}"
    )
    print(f"Slice 4 production Tk counts: {counts}")
    valid = (
        result.testsRun == EXPECTED_TESTS
        and not result.skipped
        and not result.errors
        and not result.failures
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
