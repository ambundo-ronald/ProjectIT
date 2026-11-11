"""Contract tests for advice to the customer's operator when a reading crosses its meter's limits."""
import importlib
import unittest

from test_ops import Dict, OpsTestCase


class AdviceTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.advice = importlib.import_module("projectit.advice")

    def meter(self, **extra):
        m = Dict(name="M1", meter_name="Feed pressure", unit="bar", advice_high=None, advice_low=None,
            triggers=[Dict(trigger_type="Above", value=16), Dict(trigger_type="Below", value=6), Dict(trigger_type="Every", value=500)])
        m.update(extra)
        return m

    def test_within_limits_no_advice(self):
        self.assertIsNone(self.advice.check(self.meter(), 12, {"M1": "feed_p"}))

    def test_standard_ro_advice(self):
        high = self.advice.check(self.meter(), 17, {"M1": "feed_p"})
        self.assertEqual((high["direction"], high["limit"]), ("high", 16))
        self.assertIn("cartridge filter", high["text"])
        low = self.advice.check(self.meter(), 5, {"M1": "feed_p"})
        self.assertIn("feed pump", low["text"])

    def test_the_meters_own_advice_wins(self):
        found = self.advice.check(self.meter(advice_high="Open valve V3 and call Peter."), 17, {"M1": "feed_p"})
        self.assertEqual(found["text"], "Open valve V3 and call Peter.")

    def test_other_meters_get_plain_advice(self):
        self.assertIn("above its limit", self.advice.check(self.meter(), 17, {})["text"])
        self.assertIn("below its limit", self.advice.check(self.meter(), 5, {})["text"])

    def test_every_trigger_is_not_a_limit(self):
        m = self.meter(triggers=[Dict(trigger_type="Every", value=500)])
        self.assertIsNone(self.advice.check(m, 10000, {}))


if __name__ == "__main__":
    unittest.main()
