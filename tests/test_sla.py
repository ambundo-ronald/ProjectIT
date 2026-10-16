"""Contract tests for promised response times: deadlines on new repairs, met or missed, warnings and the report."""
import importlib
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase

NOW = datetime(2026, 10, 11, 9)


def contract(**extra):
    row = Dict(name="SC-1", title="RO service", customer_name="Seaview", status="Active", start_date="2026-01-01",
        end_date="2026-12-31", response_hours=4, fix_hours=24)
    row.update(extra)
    return row


def new_job(**extra):
    doc = Dict(custom_work_order=1, custom_work_category="Corrective", status="Open", custom_equipment="EQ-1",
        custom_service_contract=None, custom_work_request=None, creation="2026-10-11 08:00:00",
        custom_respond_by=None, custom_fix_by=None, custom_sla_contract=None)
    doc.update(extra)
    doc.is_new = lambda: True
    return doc


class PromiseTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.sla = importlib.import_module("projectit.sla")

    def lookups(self, row, request_created=None):
        def get_value(doctype, name, field=None, *args, **kwargs):
            if doctype == "Techy Equipment":
                return "SC-1"
            if doctype == "Issue":
                return request_created
            return row
        self.frappe.db.get_value = MagicMock(side_effect=get_value)

    def test_new_repair_gets_deadlines(self):
        self.lookups(contract())
        doc = new_job()
        self.sla.stamp(doc)
        self.assertEqual((doc.custom_sla_contract, doc.custom_respond_by, doc.custom_fix_by),
            ("SC-1", datetime(2026, 10, 11, 12), datetime(2026, 10, 12, 8)))

    def test_clock_starts_at_the_customers_request(self):
        self.lookups(contract(fix_hours=None), request_created="2026-10-11 06:30:00")
        doc = new_job(custom_work_request="ISS-1")
        self.sla.stamp(doc)
        self.assertEqual((doc.custom_respond_by, doc.custom_fix_by), (datetime(2026, 10, 11, 10, 30), None))

    def test_no_promise_without_an_active_contract_or_for_other_jobs(self):
        for row, extra in ((contract(status="Cancelled"), {}), (contract(end_date="2026-10-01"), {}),
                (contract(response_hours=None, fix_hours=None), {}), (contract(), {"custom_work_category": "Preventive"}),
                (None, {})):
            self.lookups(row)
            doc = new_job(**extra)
            self.sla.stamp(doc)
            self.assertIsNone(doc.custom_respond_by, (row, extra))

    def test_met_missed_and_due(self):
        job = Dict(status="Working", custom_respond_by="2026-10-11 08:00:00", custom_started_at="2026-10-11 07:30:00",
            custom_fix_by="2026-10-11 09:30:00", custom_completed_at=None)
        state = self.sla.state(job, NOW)
        self.assertEqual(state["respond"]["state"], "Met")
        self.assertEqual((state["fix"]["state"], state["fix"]["hours"], state["fix"]["soon"]), ("Due", 0.5, True))
        job.update(status="Completed", custom_completed_at="2026-10-11 11:30:00", custom_started_at="2026-10-11 10:00:00")
        state = self.sla.state(job, NOW)
        self.assertEqual((state["respond"]["state"], state["respond"]["hours"]), ("Missed", 2))
        self.assertEqual((state["fix"]["state"], state["fix"]["hours"]), ("Missed", 2))
        self.assertIsNone(self.sla.state(Dict(job, status="Cancelled"), NOW))

    def test_warnings_once_before_and_once_when_missed(self):
        rows = [Dict(name="T1", subject="Leak", custom_respond_by="2026-10-11 09:30:00", custom_sla_warned=0),
            Dict(name="T2", subject="Noise", custom_respond_by="2026-10-11 08:00:00", custom_sla_warned=1),
            Dict(name="T3", subject="Far off", custom_respond_by="2026-10-11 15:00:00", custom_sla_warned=0),
            Dict(name="T4", subject="Warned", custom_respond_by="2026-10-11 09:20:00", custom_sla_warned=1)]
        self.frappe.get_all = MagicMock(return_value=rows)
        with patch.object(self.sla, "_people", return_value=["tina@x.com"]), patch.object(self.sla.ops, "notify") as notify:
            self.sla.check_due()
        subjects = [c.args[1] for c in notify.call_args_list]
        self.assertEqual(subjects, ["Respond by 2026-10-11 09:30: Leak", "Response time missed (due 2026-10-11 08:00): Noise"])
        levels = {c.args[1]: c.args[3] for c in self.frappe.db.set_value.call_args_list}
        self.assertEqual(levels, {"T1": 1, "T2": 2})

    def test_report_per_contract(self):
        self.frappe.get_all = MagicMock(return_value=[contract()])
        base = dict(custom_sla_contract="SC-1", creation="2026-10-05 08:00:00", subject="x")
        jobs = [Dict(base, name="A", status="Completed", custom_respond_by="2026-10-05 12:00:00", custom_started_at="2026-10-05 10:00:00",
                custom_fix_by="2026-10-06 08:00:00", custom_completed_at="2026-10-06 10:00:00"),
            Dict(base, name="B", status="Working", custom_respond_by="2026-10-05 12:00:00", custom_started_at="2026-10-05 13:00:00",
                custom_fix_by="2026-10-12 08:00:00", custom_completed_at=None),
            Dict(base, name="C", status="Open", custom_respond_by="2026-10-11 12:00:00", custom_started_at=None,
                custom_fix_by=None, custom_completed_at=None),
            Dict(base, name="D", status="Completed", creation="2026-08-01 08:00:00", custom_respond_by="2026-08-01 12:00:00")]
        r = self.sla.report(jobs, date(2026, 10, 1), date(2026, 10, 11), NOW)
        self.assertEqual((r["jobs"], r["respond_met"], r["respond_missed"], r["respond_due"]), (3, 1, 1, 1))
        self.assertEqual((r["fix_met"], r["fix_missed"], r["fix_due"]), (0, 1, 1))
        self.assertEqual((r["respond_kept"], r["fix_kept"]), (50, 0))
        self.assertEqual([m["name"] for m in r["missed"]], ["A", "B"])
        self.assertEqual(r["contracts"][0]["response_hours"], 4)


if __name__ == "__main__":
    unittest.main()
