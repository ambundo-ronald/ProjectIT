"""Contract tests for Techy Manage crew and instruction APIs."""
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_ops import OpsTestCase, ValidationError


class ManageTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.DoesNotExistError = LookupError
        self.manage = importlib.import_module("projectit.manage")
        self.frappe.db.get_value.return_value = "HR-EMP-9"
        self.frappe.db.exists.return_value = True
        self.alloc = MagicMock(work_instruction="", allocation=[SimpleNamespace(employee="HR-EMP-1", instructions="")])
        self.alloc.name = "ALLOC-1"
        self.project = MagicMock()
        self.frappe.get_doc.side_effect = lambda doctype, *a, **k: self.project if doctype == "Project" else self.alloc

    def test_requires_manageit_module(self):
        self.frappe.db.exists.return_value = False
        with self.assertRaises(PermissionError):
            self.manage.overview()

    def test_guest_rejected(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.manage.save_instructions("PROJ-1", "x")

    def test_writes_check_role_and_project_permission(self):
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError):
            self.manage.save_instructions("PROJ-1", "x")
        self.frappe.has_permission.return_value = True
        self.alloc.is_new.return_value = False
        self.manage.save_instructions("PROJ-1", "  Wear PPE  ")
        self.frappe.has_permission.assert_called_with("Project Allocation and Instrucions", "write")
        self.project.check_permission.assert_called_with("read")
        self.assertEqual(self.alloc.work_instruction, "Wear PPE")
        self.alloc.save.assert_called_once()

    def test_read_only_project_blocks_writes(self):
        self.project.check_permission.side_effect = PermissionError("no project access")
        with self.assertRaises(PermissionError):
            self.manage.add_member("PROJ-1", "HR-EMP-2")
        self.alloc.save.assert_not_called()

    def test_duplicate_member_rejected(self):
        with self.assertRaises(ValidationError):
            self.manage.add_member("PROJ-1", "HR-EMP-1")
        self.alloc.save.assert_not_called()

    def test_update_and_remove_require_existing_member(self):
        with self.assertRaises(ValidationError):
            self.manage.update_member("PROJ-1", "HR-EMP-404", "x")
        with self.assertRaises(ValidationError):
            self.manage.remove_member("PROJ-1", "HR-EMP-404")
        self.alloc.save.assert_not_called()

    def test_update_member_saves_instructions(self):
        result = self.manage.update_member("PROJ-1", "HR-EMP-1", "Lead isolation")
        self.assertEqual(result, {"employee": "HR-EMP-1", "instructions": "Lead isolation"})
        self.alloc.save.assert_called_once()

    def test_instruction_length_limited(self):
        with self.assertRaises(ValidationError):
            self.manage.save_instructions("PROJ-1", "x" * 4001)

    def test_old_links_resolve_project_name(self):
        self.frappe.db.exists.side_effect = lambda doctype, *a: False
        self.frappe.db.get_value.return_value = "PROJ-7"
        self.assertEqual(self.manage._resolve("Pump Station Upgrade"), "PROJ-7")


if __name__ == "__main__":
    unittest.main()
