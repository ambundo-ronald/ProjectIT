"""Contract tests for meter readings: counters only rise, triggers raise one job at a time, forecasts."""
import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


def trigger(kind, value, next_due=None, open_job=None, **extra):
    return Dict(name=f"T-{kind}", trigger_type=kind, value=value, next_due=next_due, open_job=open_job,
        priority=extra.get("priority"), procedure=None, job_title=extra.get("job_title"))


def meter(kind="Counter", last=None, triggers=(), **extra):
    doc = Dict(name="MTR-1", meter_name=extra.get("meter_name", "Running hours"), unit=extra.get("unit", "h"),
        meter_type=kind, active=1, equipment="EQ-1", asset=None, last_reading=last,
        last_reading_on="2026-10-01 08:00:00" if last is not None else None, triggers=list(triggers))
    doc.save = MagicMock()
    return doc


class MeterTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.meters = importlib.import_module("projectit.meters")
        self.created = []
        work_orders = sys.modules["projectit.work_orders"]

        def create(subject, **kwargs):
            job = SimpleNamespace(name=f"TASK-{len(self.created) + 1}", subject=subject, **kwargs)
            self.created.append(job)
            return job
        work_orders.create = create
        self.frappe.db.get_value.return_value = None
        self.frappe.get_all.return_value = []

    def test_triggers_fire(self):
        crossed = self.meters.crossed
        self.assertTrue(crossed(trigger("Every", 500, next_due=1000), 1000))
        self.assertFalse(crossed(trigger("Every", 500, next_due=1000), 999.5))
        self.assertTrue(crossed(trigger("Above", 50), 51))
        self.assertFalse(crossed(trigger("Above", 50), 50))
        self.assertTrue(crossed(trigger("Below", 2), 1.5))

    def test_next_due_moves_past_the_reading(self):
        self.assertEqual(self.meters.advance(1000, 500, 1000), 1500)
        self.assertEqual(self.meters.advance(1000, 500, 2240), 2500)
        self.assertEqual(self.meters.advance(1000, 0, 2240), 1000)

    def test_forecast(self):
        rows = [Dict(value=1300, reading_on="2026-10-11 08:00:00"), Dict(value=1000, reading_on="2026-10-01 08:00:00")]
        self.assertEqual(str(self.meters.forecast(rows, 1500)), "2026-10-17")  # 30 h/day, 200 h to go
        self.assertEqual(str(self.meters.forecast(rows, 1200)), "2026-10-11")  # already past: due today
        old = [Dict(value=1300, reading_on="2026-09-11 08:00:00"), Dict(value=1000, reading_on="2026-09-01 08:00:00")]
        self.assertEqual(str(self.meters.forecast(old, 1320)), "2026-10-11")  # read long ago: not in the past
        self.assertIsNone(self.meters.forecast(rows[:1], 1500))
        self.assertIsNone(self.meters.forecast([rows[1], rows[0]], 1500))  # falling: no estimate

    def test_service_job_every_interval(self):
        doc = meter(triggers=[trigger("Every", 500, next_due=1000)])
        raised = self.meters.evaluate(doc, Dict(value=1020))
        self.assertEqual(len(raised), 1)
        self.assertEqual(self.created[0].category, "Preventive")
        self.assertEqual(self.created[0].equipment, "EQ-1")
        self.assertEqual(doc.triggers[0].next_due, 1500)
        self.assertEqual(doc.triggers[0].open_job, "TASK-1")

    def test_limit_raises_one_job_at_a_time(self):
        doc = meter("Gauge", triggers=[trigger("Above", 50)], meter_name="Permeate TDS", unit="ppm")
        self.meters.evaluate(doc, Dict(value=78))
        self.assertEqual((self.created[0].category, self.created[0].priority), ("Corrective", "High"))
        self.assertIn("should not go over 50 ppm", self.created[0].description)
        self.frappe.db.get_value.return_value = Dict(name="TASK-1", subject="TDS", status="Open")
        self.assertEqual(self.meters.evaluate(doc, Dict(value=90)), [])
        self.assertEqual(len(self.created), 1)
        self.frappe.get_doc.return_value.add_comment.assert_called()
        self.frappe.db.get_value.return_value = Dict(name="TASK-1", subject="TDS", status="Completed")
        self.meters.evaluate(doc, Dict(value=80))
        self.assertEqual(len(self.created), 2)

    def test_reading_in_range_raises_nothing(self):
        doc = meter("Gauge", triggers=[trigger("Above", 50), trigger("Below", 5)])
        self.assertEqual(self.meters.evaluate(doc, Dict(value=20)), [])

    def test_counter_cannot_go_down(self):
        doc = meter(last=1200)
        self.frappe.get_doc.return_value = doc
        self.frappe.get_cached_value = MagicMock(return_value="System User")
        with self.assertRaises(ValidationError) as raised:
            self.meters.record_reading("MTR-1", 1100)
        self.assertIn("only goes up", str(raised.exception))
        with self.assertRaises(PermissionError):
            self.meters.record_reading("MTR-1", 1100, reset=1)

    def test_reading_must_be_a_number(self):
        for bad in ("abc", None, "nan", 1e13):
            with self.assertRaises(ValidationError):
                self.meters._value(bad)

    def test_gauges_cannot_trigger_by_interval(self):
        self.frappe.get_roles.return_value = ["Maintenance Manager"]
        self.frappe.db.exists.return_value = True
        self.frappe.new_doc = MagicMock()
        self.frappe.new_doc.return_value = Dict(triggers=[], last_reading=None, last_reading_on=None,
            set=lambda field, rows: None, append=MagicMock(), save=MagicMock(), flags=SimpleNamespace())
        with self.assertRaises(ValidationError) as raised:
            self.meters.save_meter({"meter_name": "TDS", "unit": "ppm", "meter_type": "Gauge", "equipment": "EQ-1",
                "triggers": [{"trigger_type": "Every", "value": 100}]})
        self.assertIn("Only counters", str(raised.exception))

    def test_only_managers_set_up_meters(self):
        with self.assertRaises(PermissionError):
            self.meters.save_meter({"meter_name": "Hours", "unit": "h", "equipment": "EQ-1"})


if __name__ == "__main__":
    unittest.main()
