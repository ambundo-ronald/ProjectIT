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
        custom_labour_hours=hours, custom_equipment=extra.get("equipment"), custom_asset=extra.get("asset"),
        custom_problem_code=extra.get("problem"), custom_cause_code=extra.get("cause"),
        custom_sent_back=extra.get("sent_back", 0))


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

    def test_repeat_repairs_within_30_days(self):
        jobs = [job("A", "Completed", created="2026-09-01 08:00:00", completed="2026-09-02 08:00:00", equipment="EQ-1"),
            job("B", "Completed", created="2026-09-20 08:00:00", completed="2026-09-21 08:00:00", equipment="EQ-1"),
            job("C", "Open", created="2026-10-30 08:00:00", equipment="EQ-1"),
            job("D", "Completed", "Preventive", created="2026-09-03 08:00:00", completed="2026-09-03 10:00:00", equipment="EQ-1"),
            job("E", "Completed", created="2026-09-05 08:00:00", completed="2026-09-05 10:00:00", equipment="EQ-2")]
        repeats = self.reports.repeat_repairs(jobs)
        self.assertEqual(repeats["A"].name, "B")  # 18 days later
        self.assertNotIn("B", repeats)  # the next repair came 39 days later
        self.assertNotIn("E", repeats)

    def test_technician_scorecard(self):
        self.frappe.get_cached_value = MagicMock(return_value=None)
        done = dict(status="Completed", equipment="EQ-1", problem="P", cause="C")
        jobs = [job("A", created="2026-10-01 08:00:00", completed="2026-10-02 08:00:00", due="2026-10-02", **done),
            job("B", created="2026-10-03 08:00:00", completed="2026-10-04 08:00:00", due="2026-10-03", **done),
            job("C", created="2026-10-05 08:00:00", completed="2026-10-05 12:00:00", **{**done, "equipment": "EQ-2", "cause": None}),
            job("D", "Completed", "Preventive", created="2026-10-06 08:00:00", completed="2026-10-06 10:00:00", sent_back=1),
            job("E", "Completed", created="2026-10-07 08:00:00", completed="2026-10-07 09:00:00", problem="P", cause="C")]
        assigned = {"A": ["tina@x.com"], "B": ["tina@x.com"], "C": ["tina@x.com"], "D": ["tina@x.com"], "E": ["tom@x.com"]}
        rows = {r["user"]: r for r in self.reports.by_technician(jobs, assigned, date(2026, 10, 1), TODAY, TODAY)}
        tina = rows["tina@x.com"]
        self.assertEqual((tina["due"], tina["on_time"], tina["on_time_rate"]), (2, 1, 50))
        self.assertEqual((tina["fixes"], tina["first_fix"], tina["first_fix_rate"]), (3, 2, 67))  # A was repaired again by B
        self.assertEqual((tina["repairs"], tina["coded"], tina["coded_rate"]), (3, 2, 67))
        self.assertEqual(tina["reopened"], 1)
        # (30 x 50 + 35 x 67 + 20 x 75 + 15 x 67) / 100
        self.assertEqual(tina["score"], 64)
        self.assertEqual({i["kind"] for i in tina["issues"]}, {"late", "repeat", "uncoded", "reopened"})
        self.assertEqual(next(i for i in tina["issues"] if i["kind"] == "repeat")["other"], "B")
        self.assertIsNone(rows["tom@x.com"]["score"])  # too few jobs to judge
        self.assertEqual(rows["tom@x.com"]["first_fix_rate"], None)  # no machine on the job
        self.assertEqual(list(rows)[0], "tina@x.com")

    def test_machine_costs_and_mtbf(self):
        self.frappe.get_all = MagicMock(return_value=[])
        self.frappe.db.sql = MagicMock(return_value=[("A", 300.0), ("C", 50.0)])
        down = dict(custom_machine_down=1, custom_down_from="2026-10-02 08:00:00", custom_down_to="2026-10-03 08:00:00")
        jobs = [job("A", "Completed", created="2026-10-02 08:00:00", completed="2026-10-03 08:00:00", hours=2, equipment="EQ-1", **down),
            job("B", "Open", created="2026-10-06 08:00:00", equipment="EQ-1"),
            job("C", "Completed", "Preventive", created="2026-10-04 08:00:00", completed="2026-10-04 12:00:00", equipment="EQ-2"),
            job("D", "Completed", created="2026-08-01 08:00:00", completed="2026-08-02 08:00:00", equipment="EQ-2", hours=5)]
        for j in jobs[:1]:
            j.update(down)
        r = self.reports.machine_costs(jobs, date(2026, 10, 1), TODAY, {"C": {"tina@x.com": 1.5}}, cost_rate=100)
        rows = {m["name"]: m for m in r["machines"]}
        one, two = rows["EQ-1"], rows["EQ-2"]
        self.assertEqual((one["jobs"], one["breakdowns"], one["parts_cost"], one["labour_cost"], one["cost"]), (1, 2, 300, 200, 500))
        self.assertEqual(one["down_hours"], 24)
        # 1 Oct 00:00 to 11 Oct 09:00 is 249 h, less 24 h down, over 2 breakdowns
        self.assertEqual(one["mtbf_hours"], 112.5)
        self.assertEqual((two["jobs"], two["breakdowns"], two["cost"], two["mtbf_hours"]), (1, 0, 200, None))
        self.assertEqual(r["total"], 700)
        self.assertEqual([m["name"] for m in r["machines"]], ["EQ-1", "EQ-2"])

    def test_pm_by_customer(self):
        self.frappe.get_all = MagicMock(return_value=[])
        jobs = [job("A", "Completed", "Preventive", completed="2026-10-03 10:00:00", due="2026-10-03", equipment="EQ-1"),
            job("B", "Open", "Preventive", due="2026-10-05", equipment="EQ-1"),
            job("C", "Completed", "Preventive", completed="2026-10-03 10:00:00", due="2026-10-04", equipment="EQ-2"),
            job("D", "Open", "Preventive", due="2026-10-06", asset="AST-1")]
        for j in jobs[:3]:
            j.custom_customer = "CUST-1"
        rows = self.reports.pm_by_customer(jobs, date(2026, 10, 1), TODAY, TODAY)
        self.assertEqual([(c["customer"], c["compliance"]) for c in rows], [(None, 0), ("CUST-1", 67)])
        self.assertEqual([(m["name"], m["compliance"]) for m in rows[1]["machines"]], [("EQ-1", 50), ("EQ-2", 100)])

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

    def test_sent_back_counts_returns_to_work(self):
        for before, after, expected in (("Pending Review", "Working", 2), ("Completed", "Open", 2),
                ("Completed", "Cancelled", 1), ("Working", "Pending Review", 1), ("Pending Review", "Completed", 1)):
            doc = self.doc(after, started="2026-10-10 08:00:00")
            doc.custom_sent_back = 1
            doc.get_doc_before_save = lambda status=before: Dict(status=status)
            self.work_orders._stamp_times(doc)
            self.assertEqual(doc.custom_sent_back, expected, (before, after))

    def test_unchanged_status_keeps_times(self):
        doc = self.doc("Completed", changed=False)
        self.work_orders._stamp_times(doc)
        self.assertIsNone(doc.custom_completed_at)


if __name__ == "__main__":
    unittest.main()
