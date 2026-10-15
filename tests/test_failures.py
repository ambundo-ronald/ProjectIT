"""Contract tests for failure codes and downtime on jobs, and their reports."""
import importlib
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class FailureTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.f = importlib.import_module("projectit.failures")
        self.job = Dict(name="TASK-1", custom_work_category="Corrective", custom_equipment="EQ-1", status="Completed")

    def test_codes_required_only_when_switched_on_for_repairs_on_machines(self):
        self.frappe.db.get_single_value.return_value = 0
        self.assertEqual(self.f.missing(self.job), [])
        self.frappe.db.get_single_value.return_value = 1
        self.assertEqual(self.f.missing(self.job), ["Problem", "Cause"])
        self.assertEqual(self.f.missing(Dict(self.job, custom_problem_code="LEAK")), ["Cause"])
        self.assertEqual(self.f.missing(Dict(self.job, custom_work_category="Preventive")), [])
        self.assertEqual(self.f.missing(Dict(self.job, custom_equipment=None)), [])

    def test_completion_blocked_without_codes(self):
        self.frappe.db.get_single_value.return_value = 1
        with self.assertRaises(ValidationError) as raised:
            self.f.on_complete(self.job)
        self.assertIn("problem and cause", str(raised.exception))

    def test_completion_puts_the_machine_back_in_service(self):
        self.frappe.db.get_single_value.return_value = 0
        job = Dict(self.job, custom_machine_down=1, custom_down_from="2026-10-11 06:00:00", custom_down_to=None)
        self.f.on_complete(job)
        self.assertEqual(job.custom_down_to, datetime(2026, 10, 11, 9))

    def test_codes_must_be_of_the_right_kind(self):
        self.frappe.db.get_value.return_value = Dict(kind="Cause", disabled=0)
        with self.assertRaises(ValidationError):
            self.f._code("WEAR", "Problem")
        self.assertEqual(self.f._code("WEAR", "Cause"), "WEAR")

    def test_downtime_times(self):
        with self.assertRaises(ValidationError):
            self.f._when("2026-10-12T08:00", "Down from")  # tomorrow in the test clock
        self.assertEqual(self.f._when("2026-10-11T07:30", "Down from"), datetime(2026, 10, 11, 7, 30))
        self.assertEqual(self.f.hours("2026-10-11 06:00:00", "2026-10-11 08:30:00"), 2.5)
        self.assertEqual(self.f.hours("2026-10-11 06:00:00"), 3.0)  # still down: until now

    def test_codes_are_for_managers(self):
        with self.assertRaises(PermissionError):
            self.f.save_code("LEAK", "Leak", "Problem")


class FailureReportTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.reports = importlib.import_module("projectit.reports")
        self.reports.ops.asset_names = MagicMock(return_value={})
        importlib.import_module("projectit.equipment").labels = MagicMock(return_value={})

    def test_downtime_overlap_with_the_period(self):
        jobs = [
            # Down 10 h before the period began and 6 h inside it.
            Dict(name="A", custom_equipment="EQ-1", custom_machine_down=1, custom_down_from="2026-09-30 14:00:00",
                custom_down_to="2026-10-01 06:00:00"),
            Dict(name="B", custom_equipment="EQ-1", custom_machine_down=1, custom_down_from="2026-10-05 08:00:00",
                custom_down_to="2026-10-05 12:00:00"),
            # Still down since 07:00 today (now is 09:00).
            Dict(name="C", custom_asset="AST-1", custom_machine_down=1, custom_down_from="2026-10-11 07:00:00",
                custom_down_to=None),
            Dict(name="D", custom_equipment="EQ-2", custom_machine_down=0, custom_down_from=None, custom_down_to=None),
        ]
        result = self.reports.downtime(jobs, date(2026, 10, 1), date(2026, 10, 11))
        rows = {m["name"]: m for m in result["machines"]}
        self.assertEqual((rows["EQ-1"]["hours"], rows["EQ-1"]["stops"], rows["EQ-1"]["mttr"]), (10.0, 2, 10.0))
        self.assertEqual((rows["AST-1"]["hours"], rows["AST-1"]["down_now"]), (2.0, True))
        self.assertNotIn("EQ-2", rows)
        self.assertEqual((result["hours"], result["stops"], result["down_now"]), (12.0, 3, 1))
        self.assertLess(rows["EQ-1"]["availability"], 100)

    def test_failure_counts(self):
        done = dict(status="Completed", custom_completed_at="2026-10-05 10:00:00", custom_work_category="Corrective")
        jobs = [Dict(done, name="A", custom_problem_code="LEAK", custom_cause_code="SEAL"),
            Dict(done, name="B", custom_problem_code="LEAK", custom_cause_code="WEAR"),
            Dict(done, name="C", custom_problem_code=None, custom_cause_code=None)]
        self.frappe.get_all.return_value = [["LEAK", "Leak"], ["SEAL", "Seal failed"], ["WEAR", "Normal wear"]]
        result = self.reports.failure_counts(jobs, date(2026, 10, 1), date(2026, 10, 11))
        self.assertEqual(result["problems"], [{"code": "LEAK", "title": "Leak", "jobs": 2}])
        self.assertEqual((result["repairs"], result["coded"]), (3, 2))


if __name__ == "__main__":
    unittest.main()
