"""Contract tests for parts on jobs: billing by cover, approval into Material Requests, stock entry sync."""
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class PartsTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.get_time = lambda value: value
        self.frappe.format = lambda value: str(value)
        self.frappe.db.savepoint = MagicMock()
        self.frappe.clear_messages = MagicMock()
        self.parts = importlib.import_module("projectit.parts")

    def test_billing_follows_cover(self):
        billing = self.parts.default_billing
        self.assertEqual(billing(Dict(custom_equipment=None), "PF-5"), "Internal")
        self.frappe.db.get_value.return_value = Dict(status="Active", warranty_until="2027-01-01", contract_until=None,
            service_contract=None)
        self.assertEqual(billing(Dict(custom_equipment="EQ-1"), "PF-5"), "Warranty")
        self.frappe.db.get_value.return_value = Dict(status="Active", warranty_until="2025-01-01",
            contract_until="2027-01-01", service_contract="SC-1")
        self.frappe.db.exists.return_value = True
        self.assertEqual(billing(Dict(custom_equipment="EQ-1"), "PF-5"), "Contract")
        self.frappe.db.exists.return_value = False
        self.assertEqual(billing(Dict(custom_equipment="EQ-1"), "MEM-4040"), "Chargeable")

    def test_amount_only_for_chargeable(self):
        self.assertEqual(self.parts._amount(Dict(qty=2, rate=1500, billing="Chargeable")), 3000)
        self.assertEqual(self.parts._amount(Dict(qty=2, rate=1500, billing="Contract")), 0)

    def test_completion_needs_a_decided_list(self):
        self.frappe.db.count.side_effect = lambda doctype, filters: 2 if filters["status"] == "Draft" else 0
        with self.assertRaises(ValidationError) as raised:
            self.parts.check_open("TASK-1")
        self.assertIn("never sent", str(raised.exception))
        self.frappe.db.count.side_effect = lambda doctype, filters: 1 if filters["status"] == "Requested" else 0
        with self.assertRaises(ValidationError) as raised:
            self.parts.check_open("TASK-1")
        self.assertIn("waiting for approval", str(raised.exception))
        self.frappe.db.count.side_effect = lambda doctype, filters: 0
        self.parts.check_open("TASK-1")

    def test_only_approvers_approve(self):
        self.frappe.get_roles.return_value = ["Employee", "Maintenance User"]
        with self.assertRaises(PermissionError):
            self.parts.approve_parts("TASK-1")
        self.frappe.get_roles.return_value = ["Stock Manager"]
        self.assertTrue(self.parts.can_approve())

    def test_approval_raises_material_request(self):
        self.frappe.get_roles.return_value = ["Stock Manager"]
        task = MagicMock(custom_work_order=1, project="PROJ-1", exp_end_date=None, subject="Visit", owner="boss@x.com")
        task.name = "TASK-1"
        mr = MagicMock()
        mr.name = "MAT-MR-1"
        mr.items = [Dict(name="mri-1"), Dict(name="mri-2")]
        self.frappe.get_doc.side_effect = lambda *a, **k: task if a and a[0] == "Task" else mr
        self.frappe.get_all.side_effect = lambda doctype, **kw: [Dict(name="P1", item_code="PF-5", qty=2, uom="Nos",
            warehouse="Van", owner="tech@example.com"), Dict(name="P2", item_code="CB-10", qty=1, uom="Nos",
            warehouse="Stores", owner="tech@example.com")] if doctype == "Techy Part Usage" else []
        self.frappe.db.get_value.return_value = "Techy Demo Ltd"
        self.frappe.get_cached_doc.return_value = Dict(parts_expense_account=None)
        self.parts._view = MagicMock(return_value=None)
        result = self.parts.approve_parts("TASK-1")
        self.assertEqual(result["material_requests"], ["MAT-MR-1"])
        data = [c.args[0] for c in self.frappe.get_doc.call_args_list if c.args and isinstance(c.args[0], dict)][0]
        self.assertEqual((data["material_request_type"], data["custom_work_order"], len(data["items"])),
            ("Material Issue", "TASK-1", 2))
        mr.submit.assert_called_once()
        self.frappe.db.set_value.assert_any_call("Techy Part Usage", "P2", {"status": "Approved",
            "material_request": "MAT-MR-1", "material_request_item": "mri-2", "approved_by": "tech@example.com"})

    def test_stock_entry_marks_lines_issued_and_back(self):
        entry = SimpleNamespace(name="STE-1", items=[Dict(material_request_item="mri-1"), Dict(material_request_item=None)])
        self.parts.on_stock_entry_submit(entry)
        self.frappe.db.set_value.assert_called_once_with("Techy Part Usage", {"material_request_item": "mri-1",
            "status": "Approved"}, {"status": "Issued", "stock_entry": "STE-1"})
        self.frappe.db.set_value.reset_mock()
        self.parts.on_stock_entry_cancel(entry)
        self.frappe.db.set_value.assert_called_once_with("Techy Part Usage", {"material_request_item": "mri-1",
            "stock_entry": "STE-1"}, {"status": "Approved", "stock_entry": None})


class BillingTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.get_time = lambda value: value
        self.frappe.format = lambda value: str(value)
        self.billing = importlib.import_module("projectit.billing")

    def test_labour_default_follows_cover(self):
        default = self.billing.default_labour
        self.assertEqual(default(Dict(custom_equipment=None)), "No charge")
        eq = Dict(status="Active", warranty_until="2027-01-01", contract_until=None, service_contract=None)
        self.frappe.db.get_value.return_value = eq
        self.assertEqual(default(Dict(custom_equipment="EQ-1")), "Included")
        contract_eq = Dict(status="Active", warranty_until="2024-01-01", contract_until="2027-01-01", service_contract="SC-1")
        terms = Dict(labour_included=1, callouts_included=0, status="Active")
        self.frappe.db.get_value.side_effect = lambda doctype, *a, **k: contract_eq if doctype == "Techy Equipment" else terms
        self.assertEqual(default(Dict(custom_equipment="EQ-1", custom_service_contract="SC-1")), "Included")  # visit
        self.assertEqual(default(Dict(custom_equipment="EQ-1", custom_service_contract=None)), "Chargeable")  # call-out

    def test_labour_amount(self):
        self.billing.default_labour = lambda task: "Chargeable"
        self.frappe.get_cached_doc.return_value = Dict(labour_hour_item=None, flat_fee_item=None)
        hourly = self.billing.labour(Dict(custom_labour_hours=2.5, custom_labour_rate=2000))
        self.assertEqual(hourly["amount"], 5000)
        flat = self.billing.labour(Dict(custom_labour_mode="Flat fee", custom_flat_fee=3500))
        self.assertEqual(flat["amount"], 3500)
        included = self.billing.labour(Dict(custom_labour_billing="Included", custom_labour_hours=3, custom_labour_rate=2000))
        self.assertEqual(included["amount"], 0)

    def test_invoice_one_customer_at_a_time(self):
        self.manager()
        jobs = {"T1": MagicMock(custom_customer="Seaview"), "T2": MagicMock(custom_customer="Bahari")}
        self.frappe.get_doc.side_effect = lambda doctype, name, **k: jobs[name]
        self.frappe.get_cached_doc.return_value = Dict(labour_hour_item="LAB", flat_fee_item="FEE")
        with self.assertRaises(ValidationError):
            self.billing.create_invoice(["T1", "T2"])

    def test_invoice_refuses_already_invoiced(self):
        self.manager()
        job = MagicMock(custom_customer="Seaview", custom_work_order=1, status="Completed", custom_sales_invoice="SINV-1")
        self.frappe.get_doc.return_value = job
        self.frappe.get_cached_doc.return_value = Dict(labour_hour_item="LAB", flat_fee_item="FEE")
        with self.assertRaises(ValidationError) as raised:
            self.billing.create_invoice(["T1"])
        self.assertIn("already invoiced", str(raised.exception))

    def test_technicians_cannot_invoice(self):
        with self.assertRaises(PermissionError):
            self.billing.create_invoice(["T1"])


if __name__ == "__main__":
    unittest.main()
