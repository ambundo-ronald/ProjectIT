"""Contract tests for RO normalisation: net driving pressure, temperature and pressure correction, cleaning rules."""
import importlib
import math
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase


def log(day, **v):
    base = dict(feed_p=12.0, conc_p=11.0, perm_p=0.5, feed_c=900.0, perm_c=20.0, perm_q=1000.0, conc_q=333.0, temp=25.0)
    base.update(v)
    return {"on": datetime(2026, 4, 1) + timedelta(days=day), "job": None, **base}


class ROTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.ro = importlib.import_module("projectit.ro")

    def run_perf(self, entries, baseline=None):
        with patch.object(self.ro, "roles", return_value={r: Dict(name=r, meter_name=r) for r in self.ro.METERS}), \
                patch.object(self.ro, "logs", return_value=entries), patch.object(self.ro, "open_cip", return_value=None), \
                patch.object(self.ro, "settings", return_value=dict(self.ro.DEFAULTS)):
            self.frappe.db.get_value = MagicMock(return_value=baseline)
            return self.ro.performance("EQ-1")

    def test_net_driving_pressure_and_recovery(self):
        c = self.ro.compute(log(0))
        self.assertAlmostEqual(c["recovery"], 1000 / 1333, places=3)
        cfc = 900 * math.log(1 / (1 - c["recovery"])) / c["recovery"]
        self.assertAlmostEqual(c["ndp"], 11.5 - 0.5 - 0.0007 * cfc + 0.0007 * 20, places=6)
        self.assertEqual(c["assumed"], [])
        self.assertIsNone(self.ro.compute(log(0, perm_q=None)))  # not a usable log

    def test_missing_readings_are_assumed_and_reported(self):
        c = self.ro.compute(log(0, temp=None, conc_p=None, conc_q=None))
        self.assertEqual(c["assumed"], ["temperature", "concentrate pressure", "concentrate flow"])
        self.assertIsNone(c["dp"])

    def test_a_cold_month_is_not_fouling(self):
        # Same membranes, water 10 degrees colder: to keep the same flow the plant needs more pressure. Raw readings
        # look worse (much higher pressure for the same water); normalised flow shows no change.
        base = self.ro.compute(log(0))
        extra = base["ndp"] * self.ro.tcf(25) / self.ro.tcf(15) - base["ndp"]
        # The same membranes also pass less salt per litre at the higher pressure.
        cold = log(30, temp=15.0, feed_p=12.0 + extra, conc_p=11.0 + extra, perm_c=20.0 * self.ro.tcf(15) / self.ro.tcf(25))
        perf = self.run_perf([log(0), cold])
        self.assertGreater(extra, 3)  # about 3.5 bar more for the same water
        self.assertAlmostEqual(perf["latest"]["flow"], 0, delta=0.5)
        self.assertAlmostEqual(perf["latest"]["salt"], 0, delta=1)
        self.assertEqual(perf["breaches"], [])

    def test_fouling_salt_passage_and_pressure_drop_raise_cleaning(self):
        perf = self.run_perf([log(0), log(60, perm_q=850.0, conc_q=283.0, perm_c=24.0, conc_p=10.0)])
        latest = perf["latest"]
        self.assertLess(latest["flow"], -10)
        self.assertGreater(latest["salt"], 10)
        self.assertGreater(latest["dp"], 15)
        self.assertEqual(len(perf["breaches"]), 3)
        self.assertIn("normalised flow is down", perf["breaches"][0])

    def test_baseline_can_be_chosen(self):
        entries = [log(0), log(30, perm_q=850.0, conc_q=283.0), log(60, perm_q=850.0, conc_q=283.0)]
        perf = self.run_perf(entries, baseline=datetime(2026, 4, 20))  # new membranes after the first log
        self.assertEqual(perf["baseline"]["on"], entries[1]["on"])
        self.assertAlmostEqual(perf["latest"]["flow"], 0, delta=0.1)


if __name__ == "__main__":
    unittest.main()
