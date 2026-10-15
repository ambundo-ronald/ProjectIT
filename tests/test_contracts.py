"""Contract tests for service contracts: states, validation, coverage refresh and visit generation."""
import importlib
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class Doc(SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)


class ContractTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.get_time = lambda value: value
        self.frappe.db.savepoint = MagicMock()
        self.sc = importlib.import_module("projectit.contracts")

    def test_states(self):
        state = self.sc.state
        self.assertEqual(state(Dict(status="Active", start_date="2026-01-01", end_date="2027-01-01")), "Active")
        self.assertEqual(state(Dict(status="Active", start_date="2026-12-01", end_date="2027-12-01")), "Upcoming")
        self.assertEqual(state(Dict(status="Active", start_date="2025-01-01", end_date="2026-10-10")), "Expired")
        self.assertEqual(state(Dict(status="Cancelled", start_date="2026-01-01", end_date="2027-01-01")), "Cancelled")

    def contract(self, machines, **extra):
        values = dict(customer="Seaview", customer_name="Seaview Hotel", title=None, start_date="2026-10-01",
            end_date="2027-09-30", visit_frequency="Quarterly", subscription=None, machines=machines)
        values.update(extra)
        return Doc(**values)

    def test_validate_defaults_first_visit_and_title(self):
        self.frappe.db.get_value.return_value = Dict(customer="Seaview", status="Active")
        row = Doc(equipment="EQ-1", next_visit=None)
        doc = self.contract([row])
        self.sc.validate(doc)
        self.assertEqual(row.next_visit, date(2027, 1, 1))  # start + 3 months
        self.assertIn("Seaview Hotel", doc.title)

    def test_validate_rejects_other_customers_and_duplicates(self):
        self.frappe.db.get_value.return_value = Dict(customer="Someone else", status="Active")
        with self.assertRaises(ValidationError):
            self.sc.validate(self.contract([Doc(equipment="EQ-1", next_visit=None)]))
        self.frappe.db.get_value.return_value = Dict(customer="Seaview", status="Active")
        with self.assertRaises(ValidationError):
            self.sc.validate(self.contract([Doc(equipment="EQ-1", next_visit="2026-11-01"), Doc(equipment="EQ-1", next_visit="2026-11-01")]))

    def test_subscription_must_be_the_customers(self):
        self.frappe.db.get_value.return_value = Dict(name="SUB-1", party="Other", status="Active")
        with self.assertRaises(ValidationError):
            self.sc.validate(self.contract([], subscription="SUB-1"))

    def test_refresh_sets_and_clears_cover(self):
        self.frappe.db.sql.return_value = [Dict(name="SC-1", end_date="2027-09-30")]
        self.frappe.db.get_value.return_value = Dict(service_contract=None, contract_until=None)
        self.sc.refresh_equipment(["EQ-1"])
        self.frappe.db.set_value.assert_called_with("Techy Equipment", "EQ-1",
            {"service_contract": "SC-1", "contract_until": "2027-09-30"}, update_modified=False)
        self.frappe.db.set_value.reset_mock()
        self.frappe.db.sql.return_value = []
        self.frappe.db.get_value.return_value = Dict(service_contract="SC-1", contract_until="2027-09-30")
        self.sc.refresh_equipment(["EQ-1"])
        self.frappe.db.set_value.assert_called_with("Techy Equipment", "EQ-1",
            {"service_contract": None, "contract_until": None}, update_modified=False)
        self.frappe.db.set_value.reset_mock()
        self.frappe.db.get_value.return_value = Dict(service_contract=None, contract_until="2027-01-01")
        self.sc.refresh_equipment(["EQ-1"])  # hand-entered date without a Techy contract is kept
        self.frappe.db.set_value.assert_not_called()

    def test_visits_created_once_and_moved_on(self):
        wo = importlib.import_module("projectit.work_orders")
        job = MagicMock()
        job.name = "TASK-9"
        wo.create = MagicMock(return_value=job)
        due = Doc(equipment="EQ-1", next_visit="2026-10-12", last_visit_job=None)
        later = Doc(equipment="EQ-2", next_visit="2026-12-01", last_visit_job=None)
        after_end = Doc(equipment="EQ-3", next_visit="2026-10-12", last_visit_job=None)
        doc = MagicMock(name="SC-1", visit_frequency="Quarterly", end_date="2027-09-30", labour_included=1,
            included_items=[], visit_procedure="PROC-1", machines=[due, later])
        doc.name = "SC-1"
        ended = MagicMock(visit_frequency="Monthly", end_date="2026-10-11", machines=[after_end], included_items=[])
        ended.name = "SC-2"
        self.frappe.get_all.side_effect = [["SC-1", "SC-2"], []]
        self.frappe.get_doc.side_effect = lambda doctype, name: {"SC-1": doc, "SC-2": ended}[name]
        self.frappe.db.get_value.return_value = Dict(equipment_name="RO", customer_name="Seaview", status="Active")
        created = self.sc.generate_visits()
        self.assertEqual(created, ["TASK-9"])
        self.assertEqual((due.last_visit_job, str(due.next_visit)), ("TASK-9", "2027-01-12"))
        self.assertEqual(str(later.next_visit), "2026-12-01")  # not yet within the lead time
        self.assertEqual(wo.create.call_args.kwargs["service_contract"], "SC-1")
        doc.save.assert_called_once()
        ended.save.assert_not_called()  # visit falls after the contract's end date


if __name__ == "__main__":
    unittest.main()
