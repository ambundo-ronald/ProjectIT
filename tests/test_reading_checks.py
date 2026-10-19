"""Contract tests for checks on typed readings and the downtime question on repairs."""
import importlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase


class ReadingCheckTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.meters = importlib.import_module("projectit.meters")

    def rows(self, values, every_days=7):
        now = datetime(2026, 10, 11, 9)
        return [Dict(value=v, reading_on=now - timedelta(days=every_days * i)) for i, v in enumerate(values)]  # newest first

    def test_gauge_far_from_usual(self):
        self.frappe.get_all = MagicMock(return_value=self.rows([41, 40, 39, 40, 38, 39]))
        meter = Dict(name="M1", meter_type="Gauge", unit="mg/L")
        self.assertIsNone(self.meters.unusual(meter, 42))
        warning = self.meters.unusual(meter, 410)
        self.assertIn("far from this meter's usual readings (around 40 mg/L)", warning)
        self.frappe.get_all = MagicMock(return_value=self.rows([40, 41, 39]))
        self.assertIsNone(self.meters.unusual(meter, 410))  # too few readings to judge

    def test_counter_jumping_far_too_fast(self):
        self.frappe.get_all = MagicMock(return_value=self.rows([1140, 1010, 880, 750]))  # ~18.6 h a day
        meter = Dict(name="M2", meter_type="Counter", unit="h", last_reading=1140, last_reading_on=datetime(2026, 10, 4, 9))
        self.assertIsNone(self.meters.unusual(meter, 1270))  # a normal week
        self.assertIn("it usually goes up about", self.meters.unusual(meter, 11400))  # an extra digit


class DowntimeQuestionTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.failures = importlib.import_module("projectit.failures")
        self.frappe.db.get_single_value = MagicMock(return_value=1)  # the setting is on

    def repair(self, **extra):
        doc = Dict(custom_work_category="Corrective", custom_equipment="EQ-1", custom_problem_code="LEAK",
            custom_cause_code="SEAL", custom_machine_down=0, custom_down_answered=0)
        doc.update(extra)
        return doc

    def test_a_repair_must_say_whether_the_machine_was_down(self):
        with self.assertRaises(Exception) as caught:
            self.failures.check_complete(self.repair(), "completing")
        self.assertIn("Say whether the machine was down", str(caught.exception))
        self.failures.check_complete(self.repair(custom_down_answered=1), "completing")  # "No, it kept running"
        self.failures.check_complete(self.repair(custom_machine_down=1), "completing")

    def test_only_with_the_setting_and_for_repairs(self):
        self.failures.check_complete(self.repair(custom_work_category="Preventive"), "completing")
        self.frappe.db.get_single_value = MagicMock(return_value=0)
        self.failures.check_complete(self.repair(), "completing")


if __name__ == "__main__":
    unittest.main()
