from datetime import datetime, timezone
import unittest

from dip.app import SupplyChangesExecutionConsistencyError, SupplyChangesExecutionService
from dip.intelligence import IntelligenceEngine, IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import MarketplaceDataStatus, MarketplaceSnapshot, SupplyChangesModule


class Queries:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.calls = 0
    def all_snapshots(self):
        self.calls += 1
        return self.snapshots


class SupplyChangesExecutionServiceTestCase(unittest.TestCase):
    def test_queries_once_for_exactly_two_and_executes_module(self):
        now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        queries = Queries((MarketplaceSnapshot("new", now, "discogs", MarketplaceDataStatus.EMPTY),))
        result = SupplyChangesExecutionService(queries, IntelligenceEngine((SupplyChangesModule(),))).execute()
        self.assertEqual(queries.calls, 1)
        self.assertEqual(result.module_id, "supply_changes")

    def test_exact_current_identity_is_accepted_and_all_others_are_rejected_safely(self):
        class Engine:
            def __init__(self, result): self.result = result
            def execute(self, context): return IntelligenceExecution((self.result,))
        current = IntelligenceResult("supply_changes", IntelligenceStatus.COMPLETED, "done", module_version="2.0")
        self.assertIs(SupplyChangesExecutionService(Queries(()), Engine(current)).execute(), current)
        for module_id, module_version in (
            ("supply_changes", "1.0"),
            ("supply_changes", "99.0"),
            ("listing_price_changes", "1.0"),
            ("TOKEN-SQL-/private/live.sqlite", "2.0"),
        ):
            result = IntelligenceResult(module_id, IntelligenceStatus.COMPLETED, "done", module_version=module_version)
            with self.subTest(module_id=module_id, module_version=module_version):
                with self.assertRaisesRegex(SupplyChangesExecutionConsistencyError, "unexpected result") as raised:
                    SupplyChangesExecutionService(Queries(()), Engine(result)).execute()
                self.assertNotIn(module_id, str(raised.exception))
                self.assertNotIn(module_version, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
