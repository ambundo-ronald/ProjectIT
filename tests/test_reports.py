"""Contract tests for manager reports: periods, repair times, PM on time, technicians and job timestamps."""
import importlib
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase

TODAY = date(2026, 10, 11)


def job(name, status="Open", category="Corrective", created="2026-10-01 08:00:00", completed=None, due=None,
        started=None, hours=0, **extra):
    return Dict(name=name, subject=name, status=status, custom_work_category=category, creation=created,
        modified=completed or created, custom_completed_at=completed, custom_started_at=started, exp_end_date=due,
        custom_labour_hours=hours, custom_equipment=extra.get("equipment"), custom_asset=extra.get("asset"))


class ReportsTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.reports = importlib.import_module("projectit.reports")

    def test_hours_between(self):
        self.assertEqual(self.reports.hours_between("2026-10-01 08:00:00", "2026-10-01 14:30:00"), 6.5)
        self.assertIsNone(self.reports.hours_between(None, "2026-10-01 14:30:00"))
        self.assertEqual(self.reports.average([2, None, 4]), 3)
        self.assertIsNone(self.reports.average([None]))

    def test_chart_columns_cover_the_period(self):
        week = self.reports.buckets(date(2026, 10, 5), TODAY, 7)
        self.assertEqual(len(week), 7)
        month = self.reports.buckets(date(2026, 9, 12), TODAY, 30)
        self.assertEqual([c["start"] for c in month][:2], [date(2026, 9, 12), date(2026, 9, 19)])
        self.assertEqual(month[-1]["end"], TODAY)
        year = self.reports.buckets(date(2025, 10, 12), TODAY, 365)
        self.assertEqual([c["label"] for c in year[:3]], ["Oct 25", "Nov", "Dec"])
        self.assertEqual((year[0]["end"], year[-1]["start"]), (date(2025, 10, 31), date(2026, 10, 1)))
        self.assertEqual(year[-1]["end"], TODAY)
        days = sum((c["end"] - c["start"]).days + 1 for c in year)
        self.assertEqual(days, 365)

    def test_pm_on_time_late_missed(self):
        state = self.reports.pm_state
        self.assertEqual(state(job("A", "Completed", completed="2026-10-03 10:00:00", due="2026-10-03"), TODAY), "On time")
        self.assertEqual(state(job("B", "Completed", completed="2026-10-06 10:00:00", due="2026-10-03"), TODAY), "Late")
        self.assertEqual(state(job("C", "Open", due="2026-10-03"), TODAY), "Missed")
        self.assertEqual(state(job("D", "Open", due="2026-10-20"), TODAY), "Upcoming")
        self.assertIsNone(state(job("E", "Cancelled", due="2026-10-03"), TODAY))

    def test_pm_compliance(self):
        jobs = [job("A", "Completed", "Preventive", completed="2026-10-03 10:00:00", due="2026-10-03"),
            job("B", "Completed", "Preventive", completed="2026-10-06 10:00:00", due="2026-10-04"),
            job("C", "Open", "Preventive", due="2026-10-05"), job("D", "Open", "Preventive", due="2026-10-09"),
            job("E", "Open", "Preventive", due="2026-10-30"), job("F", "Open", "Corrective", due="2026-10-02")]
        pm = self.reports.pm_summary(jobs, date(2026, 10, 1), TODAY, TODAY)
        self.assertEqual((pm["on_time"], pm["late"], pm["missed"]), (1, 1, 2))
        self.assertEqual(pm["compliance"], 25)
        self.assertEqual([j["name"] for j in pm["late_jobs"]], ["B", "C", "D"])

    def test_work_summary(self):
        jobs = [job("A", "Completed", created="2026-10-02 08:00:00", started="2026-10-02 09:00:00",
                completed="2026-10-02 12:00:00"),
            job("B", "Completed", created="2026-10-03 08:00:00", completed="2026-10-03 16:00:00"),
            job("C", "Completed", "Preventive", created="2026-10-03 08:00:00", completed="2026-10-05 08:00:00"),
            job("D", "Open", created="2026-10-04 08:00:00", due="2026-10-06"),
            job("E", "Working", created="2026-08-01 08:00:00", started="2026-08-01 10:00:00"),
            job("F", "Completed", created="2026-08-01 08:00:00", completed="2026-08-02 08:00:00")]
        work = self.reports.work_summary(jobs, date(2026, 10, 1), TODAY, TODAY)
        self.assertEqual((work["created"], work["completed"], work["open"], work["overdue"]), (4, 3, 2, 1))
        self.assertEqual(work["repair_hours"], 6)  # repairs only: 4 h and 8 h
        self.assertEqual(work["response_hours"], 1)

    def test_technician_hours_shared(self):
        jobs = [job("A", "Completed", completed="2026-10-02 08:00:00", hours=4),
            job("B", "Open", due="2026-10-01"), job("C", "Working")]
        assigned = {"A": ["tina@x.com", "tom@x.com"], "B": ["tina@x.com"], "C": ["tom@x.com"]}
        self.frappe.get_cached_value = MagicMock(return_value=None)
        rows = {r["user"]: r for r in self.reports.by_technician(jobs, assigned, date(2026, 10, 1), TODAY, TODAY)}
        self.assertEqual(rows["tina@x.com"]["labour_hours"], 2)
        self.assertEqual((rows["tina@x.com"]["open"], rows["tina@x.com"]["overdue"]), (1, 1))
        self.assertEqual((rows["tom@x.com"]["completed"], rows["tom@x.com"]["open"]), (1, 1))

    def test_dashboard_is_for_managers(self):
        self.frappe.get_roles.return_value = ["Employee", "Maintenance User"]
        with self.assertRaises(PermissionError):
            self.reports.dashboard(30)


class JobTimesTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.work_orders = importlib.import_module("projectit.work_orders")

    def doc(self, status, started=None, changed=True):
        doc = Dict(custom_work_order=1, status=status, custom_started_at=started, custom_completed_at=None)
        doc.has_value_changed = lambda field: changed
        return doc

    def test_started_and_completed(self):
        doc = self.doc("Working")
        self.work_orders._stamp_times(doc)
        self.assertEqual(doc.custom_started_at, datetime(2026, 10, 11, 9))
        self.assertIsNone(doc.custom_completed_at)
        doc = self.doc("Completed", started="2026-10-10 08:00:00")
        self.work_orders._stamp_times(doc)
        self.assertEqual(doc.custom_started_at, "2026-10-10 08:00:00")
        self.assertEqual(doc.custom_completed_at, datetime(2026, 10, 11, 9))

    def test_reopening_clears_completion(self):
        doc = self.doc("Open", started="2026-10-10 08:00:00")
        doc.custom_completed_at = "2026-10-10 12:00:00"
        self.work_orders._stamp_times(doc)
        self.assertIsNone(doc.custom_completed_at)

    def test_unchanged_status_keeps_times(self):
        doc = self.doc("Completed", changed=False)
        self.work_orders._stamp_times(doc)
        self.assertIsNone(doc.custom_completed_at)


if __name__ == "__main__":
    unittest.main()
