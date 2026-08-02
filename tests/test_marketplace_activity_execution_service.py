import unittest
from dataclasses import replace

from dip.app import (
    MarketplaceActivityExecutionConsistencyError,
    MarketplaceActivityExecutionService,
)
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

    def test_rejects_every_incompatible_required_source_before_engine_execution(self):
        _, price, supply, rare = source_results()
        hostile = "TOKEN-SQL-/private/live.sqlite-99.0"
        cases = (
            (replace(price, module_version="1.0"), supply, rare),
            (replace(price, module_version="99.0"), supply, rare),
            (replace(price, module_id="listing_price_changes", module_version="1.0"), supply, rare),
            (replace(price, module_id=hostile), supply, rare),
            (price, replace(supply, module_version="1.0"), rare),
            (price, replace(supply, module_version="99.0"), rare),
            (price, replace(supply, module_id=hostile), rare),
            (price, replace(supply, module_id="listing_price_changes", module_version="1.0"), rare),
        )
        for sources in cases:
            with self.subTest(identities=tuple((v.module_id, v.module_version) for v in sources)):
                providers = tuple(Provider(value) for value in sources)
                class Engine:
                    def execute(self, context):
                        raise AssertionError("incompatible sources must not execute")
                with self.assertRaisesRegex(
                    MarketplaceActivityExecutionConsistencyError,
                    "incompatible required source result",
                ) as raised:
                    MarketplaceActivityExecutionService(*providers, Engine()).execute()
                self.assertNotIn(hostile, str(raised.exception))

    def test_application_accepts_only_current_weekend_optional_source(self):
        _, price, supply, rare = source_results()
        weekend = replace(price, module_id="weekend_listings", module_version="1.0")
        providers = tuple(Provider(value) for value in (price, supply, rare))
        result = MarketplaceActivityExecutionService(
            *providers,
            IntelligenceEngine((MarketplaceActivityModule(),)),
            weekend_listings=Provider(weekend),
        ).execute()
        self.assertEqual(result.module_id, "marketplace_activity")
        hostile = "TOKEN-SQL-/private/live.sqlite"
        for optional in (
            replace(weekend, module_version="99.0"),
            replace(weekend, module_version="0.9"),
            replace(weekend, module_id=hostile),
            replace(weekend, module_id="listing_price_changes"),
            price,
            supply,
            rare,
        ):
            with self.subTest(identity=(optional.module_id, optional.module_version)):
                providers = tuple(Provider(value) for value in (price, supply, rare))
                with self.assertRaisesRegex(
                    MarketplaceActivityExecutionConsistencyError,
                    "(Optional Marketplace Activity source must be Weekend Listings|duplicate source outputs)",
                ) as raised:
                    MarketplaceActivityExecutionService(
                        *providers,
                        IntelligenceEngine((MarketplaceActivityModule(),)),
                        weekend_listings=Provider(optional),
                    ).execute()
                self.assertNotIn(hostile, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
