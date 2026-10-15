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
            return "EMP-OWN" if doctype == "Employee" and filters == {"user_id": "tech@example.com"} else None
        self.frappe.db.get_value.side_effect = get_value

    def test_employee_id_is_always_the_callers(self):
        self.assertEqual(self.api.get_employee_id("boss@example.com"), "EMP-OWN")
        self.assertEqual(self.lookups, [("Employee", {"user_id": "tech@example.com"})])

    def test_router_modules_are_the_callers(self):
        self.frappe.get_all.side_effect = lambda doctype, **kw: ["WorkIT", "Ops"] if kw["filters"]["parent"] == "EMP-OWN" else ["ManageIT"]
        self.frappe.get_roles.return_value = ["Employee"]
        modules = self.api.get_modules_for_router("boss@example.com")
        self.assertEqual(modules[:3], ["workit", "ops", "home"])
        self.assertNotIn("manageit", modules)

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
