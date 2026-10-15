"""Contract tests for the dispatch calendar: who may plan, due dates, and moving jobs between technicians."""
import importlib
import unittest
from datetime import date
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class DispatchTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.d = importlib.import_module("projectit.dispatch")
        self.manager()
        self.job = MagicMock(custom_work_order=1, parent_task=None, status="Open", exp_start_date=None,
            exp_end_date=date(2026, 10, 20), subject="Low flow")
        self.job.name = "TASK-1"
        self.job.has_value_changed.return_value = False
        self.frappe.get_doc.return_value = self.job
        self.assigned = ["tom@x"]
        self.wo._assignees = MagicMock(side_effect=lambda names: {n: list(self.assigned) for n in names})
        self.frappe.get_all.return_value = ["tina@x"]  # active user check

    def test_managers_only(self):
        self.frappe.get_roles.return_value = ["Maintenance User"]
        with self.assertRaises(PermissionError):
            self.d.board()
        with self.assertRaises(PermissionError):
            self.d.schedule("TASK-1", "2026-10-14")

    def test_week_starts_on_monday(self):
        self.d._rows = MagicMock(return_value=[])
        self.d.technicians = MagicMock(return_value=[])
        board = self.d.board("2026-10-15", 7)  # a Thursday
        self.assertEqual((board["start"], board["end"], len(board["days"])), (date(2026, 10, 12), date(2026, 10, 18), 7))
        self.assertEqual(self.d.board("2026-10-15", 1)["days"], [date(2026, 10, 15)])

    def test_planning_after_the_due_date_asks_first(self):
        result = self.d.schedule("TASK-1", "2026-10-22")
        self.assertEqual(result, {"needs_due_move": date(2026, 10, 20)})
        self.job.save.assert_not_called()
        self.d.schedule("TASK-1", "2026-10-22", move_due=1)
        self.assertEqual((self.job.exp_start_date, self.job.exp_end_date), (date(2026, 10, 22), date(2026, 10, 22)))
        self.job.save.assert_called_once()

    def test_moving_between_technicians(self):
        self.d.schedule("TASK-1", "2026-10-14", user="tina@x", from_user="tom@x")
        self.assign.remove.assert_called_once_with("Task", "TASK-1", "tom@x")
        self.assertEqual(self.assign.add.call_args.args[0]["assign_to"], ["tina@x"])
        notified = self.notification.enqueue_create_notification.call_args.args[0]
        self.assertEqual(notified, ["tina@x"])

    def test_closed_jobs_stay_put(self):
        self.job.status = "Completed"
        with self.assertRaises(ValidationError):
            self.d.schedule("TASK-1", "2026-10-14")

    def test_back_to_the_list(self):
        self.job.exp_start_date = date(2026, 10, 14)
        self.d.schedule("TASK-1", None)
        self.assertIsNone(self.job.exp_start_date)
        self.assign.add.assert_not_called()
        self.assign.remove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
