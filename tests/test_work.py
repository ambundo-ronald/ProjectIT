"""Contract tests for the Techy Work screen APIs: always scoped to the signed-in employee."""
import importlib
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_ops import Dict, OpsTestCase


class WorkTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.get_time = lambda value: value
        self.frappe.utils.flt = lambda value: float(value or 0)
        self.frappe.utils.get_first_day_of_week = lambda value: "2026-10-05"
        self.work = importlib.import_module("projectit.work")
        self.me = SimpleNamespace(name="HR-EMP-1", company="Co")
        patcher = patch.object(self.work.attendance, "_employee", return_value=self.me)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_endpoints_take_no_employee_argument(self):
        self.assertEqual(list(inspect.signature(self.work.today).parameters), [])
        self.assertEqual(list(inspect.signature(self.work.history).parameters), ["start"])

    def test_history_is_scoped_to_session_employee(self):
        self.frappe.get_all.return_value = []
        self.frappe.db.get_single_value.return_value = "Overtime"
        result = self.work.history()
        first = self.frappe.get_all.call_args_list[0]
        self.assertEqual(first.args[0], "Timesheet")
        self.assertEqual(first.kwargs["filters"]["employee"], "HR-EMP-1")
        self.assertEqual(result["timesheets"], [])

    def test_history_totals_and_overtime(self):
        sheets = [Dict(name="TS-1", start_date="2026-10-11", parent_project="P1", docstatus=1, total_hours=10)]
        logs = [Dict(parent="TS-1", from_time="2026-10-11 08:00:00", to_time="2026-10-11 17:00:00", hours=9, activity_type="Field Work", task=None),
            Dict(parent="TS-1", from_time="2026-10-11 17:00:00", to_time="2026-10-11 18:00:00", hours=1, activity_type="Overtime", task=None)]
        week = [Dict(start_date="2026-10-11", total_hours=10), Dict(start_date="2026-10-06", total_hours=8)]
        self.frappe.get_all.side_effect = [sheets, logs, [("P1", "Pump Station")], [], week]
        self.frappe.db.get_single_value.return_value = "Overtime"
        result = self.work.history()
        sheet = result["timesheets"][0]
        self.assertEqual(sheet.project_name, "Pump Station")
        self.assertEqual(sheet.overtime_hours, 1)
        self.assertEqual(result["totals"], {"today": 10, "week": 18, "week_start": "2026-10-05"})

    def test_no_allocations_means_no_projects(self):
        self.frappe.db.sql.return_value = []
        self.assertEqual(self.work._projects("HR-EMP-1"), [])
        self.assertEqual(self.frappe.db.sql.call_args.args[1], {"employee": "HR-EMP-1"})


if __name__ == "__main__":
    unittest.main()
