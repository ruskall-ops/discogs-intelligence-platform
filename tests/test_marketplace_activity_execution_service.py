import unittest

from dip.app import MarketplaceActivityExecutionService
from dip.intelligence import IntelligenceEngine
from dip.marketplace_intelligence import MarketplaceActivityModule
from tests.test_marketplace_activity import source_results


class Provider:
    def __init__(self, result):
        self.result = result
        self.calls = 0
    def execute(self):
        self.calls += 1
        return self.result


class MarketplaceActivityExecutionServiceTestCase(unittest.TestCase):
    def test_coordinates_each_required_source_and_composite_once(self):
        _, price, supply, rare = source_results()
        providers = tuple(Provider(value) for value in (price, supply, rare))
        service = MarketplaceActivityExecutionService(*providers, IntelligenceEngine((MarketplaceActivityModule(),)))
        result = service.execute()
        self.assertEqual(tuple(value.calls for value in providers), (1, 1, 1))
        self.assertEqual(result.module_id, "marketplace_activity")


if __name__ == "__main__":
    unittest.main()
