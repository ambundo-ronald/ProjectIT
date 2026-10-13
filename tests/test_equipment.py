"""Contract tests for customer equipment: coverage, Delivery Note hooks and manager-only registration."""
import importlib
import unittest
from unittest.mock import MagicMock

from types import SimpleNamespace

from test_ops import Dict, OpsTestCase, ValidationError


class Doc(SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)


class EquipmentTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.get_time = lambda value: value
        self.frappe.db.savepoint = MagicMock()
        self.eq = importlib.import_module("projectit.equipment")

    def test_coverage(self):
        cover = self.eq.coverage
        self.assertEqual(cover(Dict(status="Active", warranty_until="2027-01-01"))["kind"], "Warranty")
        self.assertEqual(cover(Dict(status="Active", warranty_until="2025-01-01", contract_until="2026-12-31"))["kind"], "Contract")
        both = cover(Dict(status="Active", warranty_until="2027-01-01", contract_until="2028-01-01"))
        self.assertEqual((both["kind"], both["contract"]), ("Warranty", "2028-01-01"))
        self.assertEqual(cover(Dict(status="Active", warranty_until="2026-10-10"))["kind"], "Chargeable")  # expired
        self.assertEqual(cover(Dict(status="Active", warranty_until="2026-10-11"))["kind"], "Warranty")  # last day
        self.assertIsNone(cover(Dict(status="Decommissioned", contract_until="2030-01-01"))["kind"])

    def delivery_note(self, qty=2, **extra):
        row = Dict(name="dni-1", item_code="RO-500", item_name="RO System 500 LPH", qty=qty, stock_qty=qty, serial_no="")
        other = Dict(name="dni-2", item_code="FILTER", item_name="Filter", qty=5, stock_qty=5)
        return Doc(name="DN-1", customer="Seaview", shipping_address_name="ADDR-1", customer_address=None,
            project=None, posting_date="2026-10-11", items=[row, other], **extra)

    def test_delivery_creates_one_machine_and_job_per_unit(self):
        self.frappe.get_all.return_value = [Dict(name="RO-500", item_name="RO System 500 LPH", warranty_period=365)]
        self.frappe.db.get_value.return_value = Dict(address_title="Seaview Nyali", city="Mombasa")
        created = []
        self.frappe.get_doc.side_effect = lambda data: created.append(data) or MagicMock(**data)
        self.eq._installation_job = MagicMock()
        self.eq.on_delivery_note_submit(self.delivery_note(qty=2))
        self.assertEqual(len(created), 2)  # the untracked filter row is ignored
        first = created[0]
        self.assertEqual((first["customer"], first["site_address"], first["status"], first["delivery_note_item"]),
            ("Seaview", "ADDR-1", "Awaiting installation", "dni-1"))
        self.assertEqual(str(first["warranty_until"]), "2027-10-11")
        self.assertEqual(self.eq._installation_job.call_count, 2)

    def test_returns_and_untracked_items_are_ignored(self):
        self.eq._installation_job = MagicMock()
        self.eq.on_delivery_note_submit(self.delivery_note(is_return=1))
        self.frappe.get_all.return_value = []
        self.eq.on_delivery_note_submit(self.delivery_note())
        self.eq._installation_job.assert_not_called()
        self.frappe.get_doc.assert_not_called()

    def test_failed_machine_does_not_block_delivery(self):
        self.frappe.get_all.return_value = [Dict(name="RO-500", item_name="RO", warranty_period=0)]
        self.frappe.db.get_value.return_value = None
        self.frappe.get_doc.side_effect = RuntimeError("boom")
        self.eq.on_delivery_note_submit(self.delivery_note(qty=1))  # no exception
        self.frappe.db.rollback.assert_called_with(save_point="techy_equipment")
        self.frappe.log_error.assert_called_once()

    def test_only_managers_register(self):
        with self.assertRaises(PermissionError):
            self.eq.save_equipment({"customer": "Seaview", "equipment_name": "RO"})

    def test_site_must_belong_to_customer(self):
        self.manager()
        self.frappe.new_doc = MagicMock(return_value=MagicMock(customer=None, equipment_name=None))
        self.frappe.db.exists.side_effect = lambda doctype, filters=None: doctype == "Customer"
        with self.assertRaises(ValidationError):
            self.eq.save_equipment({"customer": "Seaview", "site_address": "SOMEONE-ELSES", "equipment_name": "RO"})


if __name__ == "__main__":
    unittest.main()
