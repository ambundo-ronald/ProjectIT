"""Contract tests for machine health: trend lines, readings against limits, and the score."""
import importlib
import unittest
from datetime import datetime, timedelta

from test_ops import Dict, OpsTestCase


def series(name, kind, last, limits=(), next_due=None):
    return {"meter_name": name, "meter_type": kind, "last": last, "unit": "u", "next_due": next_due,
        "limits": [{"type": t, "value": v} for t, v in limits]}


class HealthTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.health = importlib.import_module("projectit.health")

    def test_trend_is_a_least_squares_rate_per_day(self):
        t0 = datetime(2026, 10, 1)
        fit = self.health.trend([(t0 + timedelta(days=d), 100 + 2 * d) for d in range(0, 10, 2)])
        self.assertAlmostEqual(fit["rate"], 2.0)
        self.assertAlmostEqual(fit["at_last"], 116.0)
        self.assertIsNone(self.health.trend([(t0, 1)]))
        self.assertIsNone(self.health.trend([(t0, 1), (t0, 2)]))  # no time between readings

    def test_condition_against_limits(self):
        c = self.health._condition([series("TDS", "Gauge", 30, [("Above", 50)]), series("Flow", "Gauge", 880, [("Below", 850)])])
        self.assertEqual(c["share"], 0.75)  # inside; close to its limit
        self.assertIn("Flow is close to its limit", c["detail"])
        c = self.health._condition([series("Pressure", "Gauge", 17, [("Above", 16), ("Below", 6)])])
        self.assertEqual(c["share"], 0)
        self.assertIn("above its limit", c["detail"])
        self.assertIsNone(self.health._condition([series("Hours", "Counter", 10), series("TDS", "Gauge", 30)]))

    def test_score_scales_to_what_is_measured(self):
        row = Dict(name="EQ-1")
        r = self.health.score(row, [], [], None, 0, False, [])
        # No limits and no schedule: only reliability, availability and open repairs count, all perfect.
        self.assertEqual((r["score"], r["grade"]), (100, "Good"))
        self.assertEqual([f["points"] for f in r["factors"]][:2], [None, None])

    def test_breakdowns_downtime_and_open_repairs_lower_the_score(self):
        today = datetime(2026, 10, 11)
        jobs = [Dict(custom_work_category="Corrective", creation=today - timedelta(days=d)) for d in (5, 20, 40)]
        repairs = [Dict(exp_end_date="2026-10-01"), Dict(exp_end_date=None)]
        r = self.health.score(Dict(name="EQ-1"), [series("TDS", "Gauge", 30, [("Above", 50)])], jobs, [], 30, False, repairs)
        points = {f["key"]: f["points"] for f in r["factors"]}
        self.assertEqual(points, {"condition": 30, "service": 25, "reliability": 2, "availability": 11.2, "repairs": 2})
        self.assertEqual((r["score"], r["grade"]), (70, "Watch"))

    def test_down_now_is_at_risk(self):
        r = self.health.score(Dict(name="EQ-1"), [], [], [], 2, True, [])
        self.assertEqual((r["score"] <= 40, r["grade"]), (True, "At risk"))


if __name__ == "__main__":
    unittest.main()
