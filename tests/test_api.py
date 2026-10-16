"""Contract tests for the shared app endpoints: callers only ever get their own employee and modules."""
import importlib
import unittest
from unittest.mock import MagicMock

from test_ops import OpsTestCase


class ApiTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.api = importlib.import_module("projectit.api")
        self.lookups = []

        def get_value(doctype, filters=None, *args, **kwargs):
            self.lookups.append((doctype, filters))
            mine = isinstance(filters, dict) and filters.get("user_id") == "tech@example.com"
            return "EMP-OWN" if doctype == "Employee" and mine and self.has_employee else None
        self.has_employee = True
        self.ticked = {"EMP-OWN": ["WorkIT"]}
        self.frappe.get_all.side_effect = lambda doctype, **kw: list(self.ticked.get(kw["filters"]["parent"], []))
        self.frappe.db.get_value.side_effect = get_value

    def test_employee_id_is_always_the_callers(self):
        self.assertEqual(self.api.get_employee_id("boss@example.com"), "EMP-OWN")
        self.assertEqual(self.lookups, [("Employee", {"user_id": "tech@example.com"})])

    def test_router_modules_are_the_callers(self):
        self.ticked = {"EMP-OWN": ["WorkIT", "Ops"], "EMP-BOSS": ["ManageIT"]}
        self.frappe.get_roles.return_value = ["Employee"]
        modules = self.api.get_modules_for_router("boss@example.com")
        self.assertEqual(modules[:3], ["home", "ops", "workit"])
        self.assertNotIn("manageit", modules)

    def test_home_is_always_open(self):
        self.has_employee = False
        self.frappe.get_roles.return_value = ["Employee"]
        self.assertEqual(self.api.get_modules_for_router(), ["home"])

    def test_workit_only_people_keep_their_app(self):
        self.frappe.get_roles.return_value = ["Employee", "Projects User"]
        self.assertEqual(self.api.my_apps(), ["WorkIT"])

    def test_maintenance_roles_open_ops_without_the_tick(self):
        for role in ("Maintenance User", "Maintenance Manager", "Projects Manager"):
            self.frappe.get_roles.return_value = ["Employee", role]
            self.assertEqual(self.api.my_apps(), ["Ops", "WorkIT"], role)

    def test_system_managers_get_every_app_they_can_use(self):
        self.frappe.get_roles.return_value = ["System Manager"]
        self.assertEqual(self.api.my_apps(), ["Ops", "WorkIT", "ManageIT"])
        self.has_employee = False  # checking in needs an Employee, so no Techy Work
        self.assertEqual(self.api.my_apps(), ["Ops", "ManageIT"])

    def test_manager_only_ops_pages(self):
        self.frappe.get_roles.return_value = ["Employee", "Maintenance User"]
        self.assertNotIn("ops/dispatch", self.api.get_modules_for_router())
        self.frappe.get_roles.return_value = ["Employee", "Maintenance Manager"]
        self.assertIn("ops/dispatch", self.api.get_modules_for_router())

    def test_guests_get_nothing(self):
        self.frappe.session.user = "Guest"
        self.assertIsNone(self.api.get_employee_id("tech@example.com"))

    def test_removed_endpoints_are_gone(self):
        for name in ("upload_base64_file", "get_project_allocation", "get_instructions", "get_team_members",
                "get_employee_schedule", "project_with_members", "get_project_list", "get_employee_with_workit",
                "get_work_time_settings"):
            self.assertFalse(hasattr(self.api, name), name)


if __name__ == "__main__":
    unittest.main()
