"""Contract tests for customers' notifications: who is told, what, and not twice."""
import importlib
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase


class AudienceTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.escape_html = lambda v: v
        self.n = importlib.import_module("projectit.customer_notify")
        self.accounts = [
            Dict(name="admin@c", user="admin@c", access="Customer admin", notify_visits=1, notify_reminders=1),
            Dict(name="op1@c", user="op1@c", access="Operator", notify_visits=1, notify_reminders=0),
            Dict(name="op2@c", user="op2@c", access="Operator", notify_visits=0, notify_reminders=1),
        ]
        self.frappe.db.get_value = MagicMock(return_value="CUST-A")

        def get_all(doctype, filters=None, **kw):
            if doctype == "Techy Customer User":
                return self.accounts
            if doctype == "Techy Customer Machine":
                return [Dict(parent="op1@c"), Dict(parent="op2@c")]  # both operators look after EQ-1
            return []
        self.frappe.get_all = MagicMock(side_effect=get_all)

    def test_everyone_who_sees_the_machine_and_wants_it(self):
        self.assertEqual(self.n.audience("EQ-1", self.n.VISITS), ["admin@c", "op1@c"])
        self.assertEqual(self.n.audience("EQ-1"), ["admin@c", "op1@c", "op2@c"])

    def test_reminders_go_to_operators_first(self):
        self.assertEqual(self.n.audience("EQ-1", self.n.REMINDERS, operators_first=True), ["op2@c"])
        self.accounts = self.accounts[:1]
        self.assertEqual(self.n.audience("EQ-1", self.n.REMINDERS, operators_first=True), ["admin@c"])

    def test_no_customer_no_one(self):
        self.frappe.db.get_value = MagicMock(return_value=None)
        self.assertEqual(self.n.audience("EQ-1"), [])


class VisitNewsTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.escape_html = lambda v: v
        self.n = importlib.import_module("projectit.customer_notify")
        self.n.format_date = lambda v, fmt=None: str(v)
        self.told = []
        self.n._tell = lambda users, subject, doctype, name: self.told.append(subject)
        self.n.audience = MagicMock(return_value=["admin@c"])
        self.n._machine = lambda eq: "RO 1"

    def job(self, before=None, **values):
        doc = Dict(name="T1", custom_work_order=1, custom_equipment="EQ-1", custom_work_category="Preventive",
            parent_task=None, is_template=0, status="Open", exp_start_date=None)
        doc.update(values)
        doc.get_doc_before_save = lambda: Dict(before) if before is not None else None
        return doc

    def test_planned_moved_started_done(self):
        self.n.on_task_update(self.job({"status": "Open", "exp_start_date": None}, exp_start_date="2026-10-30"))
        self.n.on_task_update(self.job({"status": "Open", "exp_start_date": "2026-10-30"}, exp_start_date="2026-11-02"))
        self.n.on_task_update(self.job({"status": "Open"}, status="Working"))
        self.n.on_task_update(self.job({"status": "Working"}, status="Completed"))
        self.assertEqual(self.told, ["Service visit for RO 1 planned on 2026-10-30.", "Service visit for RO 1 moved to 2026-11-02.",
            "Our technician has started work on RO 1.", "Service visit done on RO 1. The service report is ready: tell us how we did."])

    def test_quiet_for_other_changes_and_other_tasks(self):
        self.n.on_task_update(self.job({"status": "Open", "exp_start_date": "2026-10-30"}, exp_start_date="2026-10-30"))
        self.n.on_task_update(self.job({"status": "Pending Review"}, status="Working"))  # sent back, not a new start
        self.n.on_task_update(self.job({"status": "Open"}, status="Completed", custom_equipment=None))
        self.n.on_task_update(self.job({"status": "Open"}, status="Completed", parent_task="T0"))
        self.assertEqual(self.told, [])


    def test_on_the_way(self):
        self.n.on_the_way(self.job(), "Tina", 30)
        self.n.on_the_way(self.job(), "Tina")
        self.assertEqual(self.told, ["Tina, our technician, is on the way to RO 1. They should arrive in about 30 minutes.",
            "Tina, our technician, is on the way to RO 1."])


class ScheduledTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.escape_html = lambda v: v
        self.n = importlib.import_module("projectit.customer_notify")
        self.cache = {}
        cache = MagicMock()
        cache.get_value = lambda k: self.cache.get(k)
        cache.set_value = lambda k, v, expires_in_sec=None: self.cache.__setitem__(k, v)
        self.frappe.cache = MagicMock(return_value=cache)
        self.told = []
        self.n._tell = lambda users, subject, doctype, name: self.told.append((tuple(users), subject))
        self.n._watched_machines = lambda: ["EQ-1"]
        self.n._machine = lambda eq: "RO 1"
        self.n.audience = MagicMock(return_value=["op@c"])
        self.n._setting = lambda field, default: default
        self.plant = importlib.import_module("projectit.plant")

    def test_one_reminder_a_day_after_the_time_while_due(self):
        self.n.nowdate = lambda: "2026-10-21"
        with patch.object(self.plant, "log_status", return_value={"due": True}):
            self.n.now_datetime = lambda: datetime(2026, 10, 21, 9, 45)
            self.n.remind_logs()
            self.assertEqual(self.told, [])  # before 10:00
            self.n.now_datetime = lambda: datetime(2026, 10, 21, 10, 0)
            self.n.remind_logs()
            self.n.remind_logs()
        self.assertEqual(len(self.told), 1)
        self.assertIn("Time to log RO 1", self.told[0][1])

    def test_no_reminder_once_logged(self):
        self.n.nowdate = lambda: "2026-10-21"
        self.n.now_datetime = lambda: datetime(2026, 10, 21, 11, 0)
        with patch.object(self.plant, "log_status", return_value={"due": False}):
            self.n.remind_logs()
        self.assertEqual(self.told, [])

    def test_managers_told_once_per_gap(self):
        notify = MagicMock()
        self.n.ops.notify = notify
        meters = importlib.import_module("projectit.meters")
        meters._managers = MagicMock(return_value=["boss@x"])
        self.n.nowdate = lambda: "2026-10-21"
        self.n.getdate = lambda v=None: date.fromisoformat(str(v)[:10])
        self.frappe.utils.add_days = lambda value, days: date.fromisoformat(str(value)[:10]).fromordinal(date.fromisoformat(str(value)[:10]).toordinal() + days)
        self.frappe.db.get_value = MagicMock(return_value="2026-10-15 09:00:00")
        self.n.missing_logs()
        self.n.missing_logs()
        self.assertEqual(notify.call_count, 1)
        self.assertIn("No customer log for RO 1 for 6 days", notify.call_args.args[1])
        self.frappe.db.get_value = MagicMock(return_value="2026-10-20 09:00:00")  # logged yesterday
        self.n.missing_logs()
        self.assertEqual(notify.call_count, 1)


    def test_someone_with_many_machines_gets_one_reminder(self):
        self.n._watched_machines = lambda: ["EQ-1", "EQ-2", "EQ-3", "EQ-4", "EQ-5"]
        self.n._machine = lambda eq: eq.replace("EQ-", "RO ")
        self.n.nowdate = lambda: "2026-10-21"
        self.n.now_datetime = lambda: datetime(2026, 10, 21, 10, 30)
        with patch.object(self.plant, "log_status", return_value={"due": True}):
            self.n.remind_logs()
        self.assertEqual(len(self.told), 1)
        self.assertIn("5 machines: RO 1, RO 2, RO 3 and 2 more", self.told[0][1])


class PushForCustomersTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.push = importlib.import_module("projectit.push")
        self.ca = importlib.import_module("projectit.customer_accounts")

    def test_customer_accounts_may_use_their_notifications(self):
        self.frappe.get_cached_value.return_value = "Website User"
        with patch.object(self.ca, "account", return_value=Dict(name="op@c")):
            self.push._member()  # no error
        with patch.object(self.ca, "account", return_value=None), self.assertRaises(PermissionError):
            self.push._member()  # another website user

    def test_customer_taps_open_the_plant_app(self):
        row = Dict(document_type="Issue", document_name="ISS-1")
        self.assertEqual(self.push._route(row, customer=True), "/techy-app/plant/service")
        self.assertEqual(self.push._route(Dict(document_type="Techy Equipment", document_name="EQ-1"), customer=True), "/techy-app/plant")
        self.assertTrue(self.push._route(row).startswith("/techy-app/ops"))


if __name__ == "__main__":
    unittest.main()
