import unittest

from dip.intelligence_history import IntelligenceHistoryRecord, dumps_intelligence_value, loads_intelligence_value
from dip.marketplace_intelligence import ListingLifecycle, ListingLifecycleOutput
from tests.test_listing_lifecycle import history, output


class ListingLifecycleHistorySerializationTestCase(unittest.TestCase):
    def test_typed_lifecycle_result_round_trips_through_existing_wire_format(self):
        result, _ = output(history())
        record = IntelligenceHistoryRecord(None, 1, result.module_id, result.module_version, result.status, result.summary, result.insights, result.metrics, result.evidence, result.diagnostics)
        restored = loads_intelligence_value(dumps_intelligence_value(record))
        self.assertEqual(restored, record)
        typed = restored.metrics["output"]
        self.assertIs(type(typed), ListingLifecycleOutput)
        self.assertTrue(all(type(value) is ListingLifecycle for value in typed.lifecycles))


if __name__ == "__main__":
    unittest.main()
