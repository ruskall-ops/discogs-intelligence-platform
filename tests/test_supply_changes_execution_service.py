from datetime import datetime, timezone
import unittest

from dip.app import SupplyChangesExecutionService
from dip.intelligence import IntelligenceEngine
from dip.marketplace_intelligence import MarketplaceDataStatus, MarketplaceSnapshot, SupplyChangesModule


class Queries:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.calls = []
    def recent_snapshots(self, limit):
        self.calls.append(limit)
        return self.snapshots


class SupplyChangesExecutionServiceTestCase(unittest.TestCase):
    def test_queries_once_for_exactly_two_and_executes_module(self):
        now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        queries = Queries((MarketplaceSnapshot("new", now, "discogs", MarketplaceDataStatus.EMPTY),))
        result = SupplyChangesExecutionService(queries, IntelligenceEngine((SupplyChangesModule(),))).execute()
        self.assertEqual(queries.calls, [2])
        self.assertEqual(result.module_id, "supply_changes")


if __name__ == "__main__":
    unittest.main()
