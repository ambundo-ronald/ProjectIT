"""Contract tests for parts on jobs: billing by cover, stock checks and issuing on completion."""
import importlib
import unittest
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class PartsTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.get_time = lambda value: value
        self.frappe.format = lambda value: str(value)
        self.frappe.db.savepoint = MagicMock()
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
        self.frappe.db.get_value.return_value = Dict(status="Active", warranty_until="2025-01-01",
            contract_until="2026-01-01", service_contract="SC-1")  # contract ended
        self.frappe.db.exists.return_value = True
        self.assertEqual(billing(Dict(custom_equipment="EQ-1"), "PF-5"), "Chargeable")

    def test_amount_only_for_chargeable(self):
        self.assertEqual(self.parts._amount(Dict(qty=2, rate=1500, billing="Chargeable")), 3000)
        self.assertEqual(self.parts._amount(Dict(qty=2, rate=1500, billing="Contract")), 0)

    def test_completion_blocked_when_short(self):
        self.frappe.get_all.return_value = [Dict(item_code="MEM", item_name="Membrane", warehouse="Stores", qty=2, uom="Nos")]
        self.frappe.db.get_value.return_value = 1
        with self.assertRaises(ValidationError) as raised:
            self.parts.check_stock("TASK-1")
        self.assertIn("Membrane", str(raised.exception))
        self.frappe.db.get_value.return_value = 5
        self.parts.check_stock("TASK-1")  # enough stock

    def test_issue_posts_one_material_issue(self):
        rows = [Dict(name="P1", item_code="PF-5", qty=2, warehouse="Van"), Dict(name="P2", item_code="CB-10", qty=1, warehouse="Stores")]
        self.frappe.get_all.return_value = rows
        self.frappe.db.get_value.return_value = "Techy Demo Ltd"
        self.frappe.get_cached_doc.return_value = Dict(parts_expense_account="Repairs - TD")
        entry = MagicMock()
        entry.name = "STE-1"
        self.frappe.get_doc.return_value = entry
        task = MagicMock(project=None, subject="Visit")
        task.name = "TASK-1"
        self.assertEqual(self.parts.issue(task), "STE-1")
        data = self.frappe.get_doc.call_args.args[0]
        self.assertEqual((data["stock_entry_type"], len(data["items"]), data["items"][0]["expense_account"]),
            ("Material Issue", 2, "Repairs - TD"))
        entry.submit.assert_called_once()
        self.frappe.db.set_value.assert_any_call("Techy Part Usage", "P1", {"status": "Issued", "stock_entry": "STE-1"})

    def test_failed_issue_keeps_lines_for_retry(self):
        self.frappe.get_all.return_value = [Dict(name="P1", item_code="PF-5", qty=2, warehouse="Van")]
        self.frappe.db.get_value.return_value = "Techy Demo Ltd"
        self.frappe.get_cached_doc.return_value = Dict()
        self.frappe.get_doc.side_effect = RuntimeError("no account")
        task = MagicMock(project=None, subject="Visit")
        self.assertIsNone(self.parts.issue(task))
        self.frappe.db.rollback.assert_called_with(save_point="techy_parts")
        self.frappe.db.set_value.assert_not_called()
        self.assertIn("manager can retry", task.add_comment.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
