import unittest

from dip.app import ListingLifecycleExecutionService
from dip.intelligence import IntelligenceEngine
from dip.marketplace_intelligence import ListingLifecycleModule


class Queries:
    def __init__(self):
        self.calls = 0
    def all_snapshots(self):
        self.calls += 1
        return ()


class ListingLifecycleExecutionServiceTestCase(unittest.TestCase):
    def test_queries_complete_history_and_executes_once(self):
        queries = Queries()
        result = ListingLifecycleExecutionService(queries, IntelligenceEngine((ListingLifecycleModule(),))).execute()
        self.assertEqual(queries.calls, 1)
        self.assertEqual(result.module_id, "listing_lifecycle")


if __name__ == "__main__":
    unittest.main()
