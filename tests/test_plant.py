"""Contract tests for the customer app's log: when it was taken, the schedule, the unusual-reading check, and alerts
instead of jobs for customers' readings."""
import importlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase

NOW = datetime(2026, 10, 11, 9)


class PlantLogTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.escape_html = lambda v: v
        self.plant = importlib.import_module("projectit.plant")
        self.meters = importlib.import_module("projectit.meters")
        self.ca = importlib.import_module("projectit.customer_accounts")
        self.plant.add_days = lambda value, days: (value if isinstance(value, datetime) else datetime.fromisoformat(str(value))) + timedelta(days=days)
        self.plant.now_datetime = lambda: NOW
        self.frappe.session.user = "otieno@c.test"

    def test_taken_on_keeps_a_late_log_within_a_week(self):
        self.assertEqual(self.plant._taken_on(None), NOW)
        self.assertEqual(self.plant._taken_on("2026-10-09 07:30:00"), datetime(2026, 10, 9, 7, 30))
        self.assertEqual(self.plant._taken_on("2026-10-01 07:30:00"), NOW)  # older than a week
        self.assertEqual(self.plant._taken_on("2026-10-12 07:30:00"), NOW)  # in the future
        self.assertEqual(self.plant._taken_on("not a date"), NOW)

    def test_schedule(self):
        self.plant.getdate = lambda v=None: NOW.date()
        self.plant.nowdate = lambda: "2026-10-11"
        self.frappe.db.get_value = MagicMock(side_effect=lambda dt, *a, **k: "Twice a day" if dt == "Techy Equipment" else None)
        self.frappe.db.count = MagicMock(return_value=1)
        status = self.plant.log_status("EQ-1")
        self.assertEqual((status["expected"], status["done"], status["due"]), (2, 1, True))
        self.frappe.db.get_value = MagicMock(side_effect=lambda dt, *a, **k: "Not expected" if dt == "Techy Equipment" else None)
        self.assertFalse(self.plant.log_status("EQ-1")["due"])

    def test_only_the_author_fixes_and_only_for_a_day(self):
        self.assertTrue(self.plant.can_fix(Dict(logged_by="otieno@c.test", creation=NOW - timedelta(hours=23))))
        self.assertFalse(self.plant.can_fix(Dict(logged_by="otieno@c.test", creation=NOW - timedelta(hours=25))))
        self.assertFalse(self.plant.can_fix(Dict(logged_by="amina@c.test", creation=NOW)))

    def setup_save(self, unusual=None, last=12.0, meter_type="Gauge"):
        meter = Dict(name="M-FEED", meter_name="Feed pressure", unit="bar", meter_type=meter_type, last_reading=last,
            last_reading_on=NOW - timedelta(days=1))
        self.frappe.get_doc = MagicMock(return_value=meter)
        self.frappe.db.get_value = MagicMock(return_value=None)
        meters = [{"name": "M-FEED"}]
        return [patch.object(self.ca, "require_machine"), patch.object(self.plant, "_meters", return_value=meters),
            patch.object(self.meters, "unusual", return_value=unusual), patch.object(self.meters, "_record")]

    def test_unusual_reading_is_asked_about_and_nothing_saved(self):
        p = self.setup_save(unusual="120 bar is far from this meter's usual readings (around 12 bar).")
        with p[0], p[1], p[2], p[3] as record:
            r = self.plant.save_log("EQ-1", {"M-FEED": "120", "M-OTHER-MACHINE": "5"})
        self.assertTrue(r["needs_confirm"])
        self.assertEqual(r["warnings"][0]["meter_name"], "Feed pressure")
        record.assert_not_called()

    def test_counter_cannot_go_down(self):
        p = self.setup_save(last=3775, meter_type="Counter")
        with p[0], p[1], p[2], p[3] as record, self.assertRaises(Exception) as caught:
            self.plant.save_log("EQ-1", {"M-FEED": "3700"})
        self.assertIn("only goes up", str(caught.exception))
        record.assert_not_called()

    def test_empty_log_is_refused(self):
        p = self.setup_save()
        with p[0], p[1], p[2], p[3], self.assertRaises(Exception) as caught:
            self.plant.save_log("EQ-1", {"M-FEED": "", "M-OTHER-MACHINE": "4"})  # another machine's meter is ignored
        self.assertIn("at least one reading", str(caught.exception))


class CustomerAlertTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.meters = importlib.import_module("projectit.meters")
        self.notify = MagicMock()
        self.meters.ops.notify = self.notify
        self.meters._managers = MagicMock(return_value=["boss@x.test"])
        self.meters._machine_label = MagicMock(return_value="RO 1")
        self.meters._job = MagicMock(return_value=None)

    def meter(self, *triggers):
        return Dict(name="M1", meter_name="Running hours", unit="h", equipment="EQ-1", triggers=list(triggers))

    def test_first_crossing_tells_managers_and_raises_nothing(self):
        doc = self.meter(Dict(trigger_type="Every", value=500, next_due=2000, open_job=None))
        self.meters.customer_alerts(doc, 2010, previous=1990)
        self.assertEqual(self.notify.call_count, 1)
        self.assertIn("service is due", self.notify.call_args.args[1])
        self.assertIn("No job was raised", self.notify.call_args.args[1])
        self.assertEqual(doc.triggers[0].next_due, 2000)  # left for our technician's reading to raise the job

    def test_no_repeat_once_already_crossed(self):
        doc = self.meter(Dict(trigger_type="Above", value=15, open_job=None))
        self.meters.customer_alerts(doc, 16, previous=15.5)
        self.notify.assert_not_called()

    def test_no_alert_while_a_job_is_open(self):
        self.meters._job = MagicMock(return_value=Dict(name="T1", status="Open"))
        doc = self.meter(Dict(trigger_type="Below", value=5, open_job="T1"))
        self.meters.customer_alerts(doc, 4, previous=6)
        self.notify.assert_not_called()


class CustomerCleaningAlertTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.ro = importlib.import_module("projectit.ro")
        self.cache = {}
        cache = MagicMock()
        cache.get_value = lambda k: self.cache.get(k)
        cache.set_value = lambda k, v, expires_in_sec=None: self.cache.__setitem__(k, v)
        self.frappe.cache = MagicMock(return_value=cache)
        self.notify = MagicMock()
        self.ro.ops.notify = self.notify
        meters = importlib.import_module("projectit.meters")
        meters._managers = MagicMock(return_value=["boss@x.test"])
        self.wo = importlib.import_module("projectit.work_orders")
        self.wo.create = MagicMock()

    def test_customer_breach_alerts_once_a_week_and_raises_no_job(self):
        with patch.object(self.ro, "performance", return_value={"breaches": ["normalised flow is down 12%"], "cip_job": None}):
            self.ro.after_reading("EQ-1", from_customer=True)
            self.ro.after_reading("EQ-1", from_customer=True)
        self.assertEqual(self.notify.call_count, 1)
        self.assertIn("may need cleaning", self.notify.call_args.args[1])
        self.wo.create.assert_not_called()

    def test_staff_breach_still_raises_the_cleaning_job(self):
        self.wo.create.return_value = Dict(name="T9")
        with patch.object(self.ro, "performance", return_value={"breaches": ["normalised flow is down 12%"], "cip_job": None}):
            self.ro.after_reading("EQ-1")
        self.wo.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
