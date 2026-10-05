import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


class AccessSetupTests(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.get_installed_apps = lambda: ["frappe", "erpnext", "hrms", "projectit"]
        self.frappe.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
        self.frappe.db = MagicMock()
        self.frappe.clear_cache = MagicMock()
        self.frappe.delete_doc = MagicMock()
        self.modules = set()
        self.setter = None
        def exists(doctype, name):
            if doctype == "DocType": return True
            if doctype == "Mobile Module Item": return name in self.modules
            if doctype == "Property Setter": return bool(self.setter)
            return False
        self.frappe.db.exists.side_effect = exists
        def get_doc(arg, name=None):
            if arg == "Property Setter": return self.setter
            doc = MagicMock()
            doc.insert.side_effect = lambda **kwargs: self.modules.add(arg["module"])
            return doc
        self.frappe.get_doc = MagicMock(side_effect=get_doc)
        custom = ModuleType("frappe.custom.doctype.custom_field.custom_field")
        self.create_fields = custom.create_custom_fields = MagicMock()
        spec = importlib.util.spec_from_file_location("setup_under_test", Path(__file__).resolve().parents[1]/"projectit/setup.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"frappe":self.frappe, "frappe.custom.doctype.custom_field.custom_field":custom}):
            spec.loader.exec_module(self.module)

    def test_missing_fields_and_module_choices_are_created(self):
        self.module.ensure_access_fields()
        fields = self.create_fields.call_args.args[0]
        self.assertEqual(fields["Employee"][0]["label"], "Techy App Access")
        self.assertEqual(fields["Employee"][1]["fieldname"], "custom_mobile_module")
        self.assertEqual(fields["Employee"][1]["options"], "Mobile Module")
        self.assertIn("Employee Checkin",fields)
        self.assertEqual(self.modules,{"WorkIT","ManageIT"})

    def test_repeated_setup_does_not_recreate_modules_or_edit_employees(self):
        self.module.ensure_access_fields()
        self.module.ensure_access_fields()
        self.assertEqual(self.frappe.get_doc.call_count,2)
        self.assertEqual(self.modules,{"WorkIT","ManageIT"})
        self.frappe.db.set_value.assert_not_called()

    def test_exact_legacy_layout_removed(self):
        self.setter = SimpleNamespace(module="Projectit", value=json.dumps(self.module.LEGACY_EMPLOYEE_ORDER))
        self.module.ensure_access_fields()
        self.frappe.delete_doc.assert_called_once_with("Property Setter","Employee-main-field_order",ignore_permissions=True)

    def test_custom_layout_preserved(self):
        self.setter = SimpleNamespace(module="Projectit", value=json.dumps(self.module.LEGACY_EMPLOYEE_ORDER + ["custom_customer_field"]))
        self.module.ensure_access_fields()
        self.frappe.delete_doc.assert_not_called()

    def test_other_modules_layout_preserved(self):
        self.setter = SimpleNamespace(module="HR", value=json.dumps(self.module.LEGACY_EMPLOYEE_ORDER))
        self.module.ensure_access_fields()
        self.frappe.delete_doc.assert_not_called()

    def test_uninstalled_app_rejected(self):
        self.frappe.get_installed_apps = lambda: ["frappe"]
        with self.assertRaises(ValueError):self.module.ensure_access_fields()
        self.create_fields.assert_not_called()

    def test_missing_doctypes_requires_migration(self):
        self.frappe.db.exists.side_effect = lambda *args: False
        with self.assertRaises(ValueError):self.module.ensure_access_fields()
        self.create_fields.assert_not_called()

if __name__ == "__main__":unittest.main()
