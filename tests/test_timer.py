"""Contract tests for the job timer: one clock per person, status changes and the labour hours it feeds."""
import importlib
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError

NOW = datetime(2026, 10, 11, 9)


def entry(name, work_order, user="tech@example.com", started="2026-10-11 08:00:00", ended=None):
    return Dict(name=name, work_order=work_order, user=user, started_at=started, ended_at=ended)


class TimerTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.t = importlib.import_module("projectit.timer")
        self.job = Dict(name="TASK-1", status="Open", save=MagicMock())
        self.t._job = MagicMock(return_value=self.job)
        self.t._finished = MagicMock(side_effect=lambda name, changes: changes)
        self.t.logged_total = MagicMock(return_value=1.5)
        self.t._close = MagicMock()
        self.wo._workflow = MagicMock(return_value=None)

    def test_hours_between(self):
        self.assertEqual(self.t._hours("2026-10-11 08:00:00", "2026-10-11 09:25:00"), 1.42)
        self.assertEqual(self.t._hours("2026-10-11 09:00:00", "2026-10-11 08:00:00"), 0)

    def test_start_moves_the_job_to_in_progress(self):
        self.t._running = MagicMock(return_value=[])
        self.t.start("TASK-1")
        inserted = self.frappe.get_doc.call_args.args[0]
        self.assertEqual((inserted["user"], inserted["work_order"], inserted["source"]),
            ("tech@example.com", "TASK-1", "Timer"))
        self.assertEqual(self.job.status, "Working")
        self.job.save.assert_called_once()

    def test_one_clock_per_person(self):
        self.job.status = "Working"
        self.t._running = MagicMock(return_value=[entry("L1", "TASK-9")])
        changes = self.t.start("TASK-1")
        self.t._close.assert_called_once()
        self.assertEqual(self.t._close.call_args.args[0].name, "L1")
        self.assertEqual(changes, {"TASK-9": 1.5})  # the other job's hours are updated too
        self.job.save.assert_not_called()

    def test_starting_again_on_the_same_job_does_nothing(self):
        self.t._running = MagicMock(return_value=[entry("L1", "TASK-1")])
        self.t.start("TASK-1")
        self.frappe.get_doc.assert_not_called()
        self.t._close.assert_not_called()

    def test_closed_jobs_cannot_be_timed(self):
        self.job.status = "Completed"
        with self.assertRaises(ValidationError):
            self.t.start("TASK-1")

    def test_only_managers_stop_someone_elses_clock(self):
        self.t._running = MagicMock(return_value=[entry("L2", "TASK-1", user="tom@example.com")])
        with self.assertRaises(PermissionError):
            self.t.stop("TASK-1", entry="L2")
        with self.assertRaises(ValidationError):
            self.t.stop("TASK-1")  # my own clock is not running
        self.manager()
        self.t.stop("TASK-1", entry="L2")
        self.t._close.assert_called_once()

    def test_hold_or_completion_stops_every_clock(self):
        self.t._running = MagicMock(return_value=[entry("L1", "TASK-1"), entry("L2", "TASK-1", "tom@example.com")])
        self.t._sync = MagicMock(return_value=3.0)
        doc = Dict(name="TASK-1", custom_labour_hours=1.5)
        self.t.stop_all(doc)
        self.assertEqual(self.t._close.call_count, 2)
        self.assertEqual(doc.custom_labour_hours, 3.0)

    def test_labour_hours_follow_the_timer_until_typed(self):
        self.t.logged_total = MagicMock(return_value=2.5)
        self.frappe.db.get_value.return_value = (1.5, None)
        self.assertEqual(self.t._sync("TASK-1", before=1.5), 2.5)
        self.frappe.db.set_value.assert_called_once_with("Task", "TASK-1", "custom_labour_hours", 2.5,
            update_modified=False)
        self.frappe.db.set_value.reset_mock()
        self.frappe.db.get_value.return_value = (4, None)  # a manager billed four hours
        self.assertIsNone(self.t._sync("TASK-1", before=1.5))
        self.frappe.db.get_value.return_value = (1.5, "ACC-SINV-1")  # invoiced
        self.assertIsNone(self.t._sync("TASK-1", before=1.5))
        self.frappe.db.set_value.assert_not_called()

    def test_adding_time_by_hand(self):
        for bad in (0, 1441, "x"):
            with self.assertRaises((ValidationError, ValueError)):
                self.t.add_time("TASK-1", bad)
        with self.assertRaises(PermissionError):
            self.t.add_time("TASK-1", 30, user="tom@example.com")
        self.t.add_time("TASK-1", 90)
        inserted = self.frappe.get_doc.call_args.args[0]
        self.assertEqual((inserted["hours"], inserted["source"], str(inserted["started_at"])),
            (1.5, "Manual", "2026-10-11 07:30:00"))

    def test_people_change_only_their_own_entries(self):
        self.frappe.db.get_value.return_value = entry("L3", "TASK-1", user="tom@example.com", ended="2026-10-11 09:00:00")
        with self.assertRaises(PermissionError):
            self.t.delete_entry("L3")
        self.manager()
        self.t.delete_entry("L3")
        self.frappe.delete_doc.assert_called_once_with("Techy Time Log", "L3", ignore_permissions=True)

    def test_running_entries_cannot_be_resized(self):
        self.frappe.db.get_value.return_value = entry("L1", "TASK-1")
        with self.assertRaises(ValidationError):
            self.t.update_entry("L1", 30)


class TimerReportTests(OpsTestCase):
    def test_technician_hours_come_from_the_timer(self):
        reports = importlib.import_module("projectit.reports")
        self.frappe.get_cached_value = MagicMock(return_value=None)
        jobs = [Dict(name="A", status="Completed", creation="2026-10-02 08:00:00", custom_completed_at="2026-10-02 12:00:00",
                custom_labour_hours=4),
            Dict(name="B", status="Completed", creation="2026-10-02 08:00:00", custom_completed_at="2026-10-02 12:00:00",
                custom_labour_hours=2)]
        assigned = {"A": ["tina@x.com", "tom@x.com"], "B": ["tina@x.com", "tom@x.com"]}
        logged = {"A": {"tina@x.com": 3.0, "tom@x.com": 0.5}}
        rows = {r["user"]: r for r in reports.by_technician(jobs, assigned, date(2026, 10, 1), date(2026, 10, 11),
            date(2026, 10, 11), logged)}
        self.assertEqual(rows["tina@x.com"]["labour_hours"], 4.0)  # 3 logged on A, half of B
        self.assertEqual(rows["tom@x.com"]["labour_hours"], 1.5)


if __name__ == "__main__":
    unittest.main()
