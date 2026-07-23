import unittest

from dip.app import RareAppearancesExecutionService
from dip.intelligence import IntelligenceEngine
from dip.marketplace_intelligence import RareAppearancesModule


class Queries:
    def __init__(self):
        self.calls = 0
    def all_snapshots(self):
        self.calls += 1
        return ()


class RareAppearancesExecutionServiceTestCase(unittest.TestCase):
    def test_queries_complete_history_once_and_executes_once(self):
        queries = Queries()
        result = RareAppearancesExecutionService(queries, IntelligenceEngine((RareAppearancesModule(),))).execute()
        self.assertEqual(queries.calls, 1)
        self.assertEqual(result.module_id, "rare_appearances")


if __name__ == "__main__":
    unittest.main()
