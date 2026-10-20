"""Contract tests for customer accounts: who sees which machines, who may invite whom, and the request guard."""
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase

ADMIN = Dict(name="amina@c.test", user="amina@c.test", customer="CUST-A", customer_name="Customer A", access="Customer admin")
OPERATOR = Dict(name="otieno@c.test", user="otieno@c.test", customer="CUST-A", customer_name="Customer A", access="Operator")


class CustomerAccountTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.ca = importlib.import_module("projectit.customer_accounts")
        self.frappe.session.user = "otieno@c.test"
        self.frappe.get_roles.return_value = ["Techy Operator"]
        self.frappe.utils.now_datetime = MagicMock(return_value="2026-10-20 09:00:00")
        self.frappe.utils.escape_html = lambda v: v
        self.ca.now_datetime = self.frappe.utils.now_datetime

    def use(self, acc):
        self.frappe.session.user = acc.user if acc else "boss@x.test"
        return patch.object(self.ca, "account", return_value=acc)

    def test_operator_sees_only_listed_machines_of_their_customer(self):
        def get_all(doctype, filters=None, pluck=None, **kw):
            if doctype == "Techy Customer Machine":
                return ["EQ-1"]
            self.assertEqual(filters["customer"], "CUST-A")  # never another customer's machine
            return [n for n in ("EQ-1", "EQ-2") if n in filters.get("name", ["in", ["EQ-1", "EQ-2"]])[1]]
        self.frappe.get_all = MagicMock(side_effect=get_all)
        self.assertEqual(self.ca.machines(OPERATOR), ["EQ-1"])
        self.assertEqual(self.ca.machines(ADMIN), ["EQ-1", "EQ-2"])

    def test_operator_without_machines_sees_none(self):
        self.frappe.get_all = MagicMock(return_value=[])
        self.assertEqual(self.ca.machines(OPERATOR), [])
        self.assertEqual(self.frappe.get_all.call_count, 1)  # never falls back to every machine

    def test_require_machine_refuses_others(self):
        with self.use(OPERATOR), patch.object(self.ca, "machines", return_value=["EQ-1"]):
            self.assertEqual(self.ca.require_machine("EQ-1"), OPERATOR)
            with self.assertRaises(PermissionError):
                self.ca.require_machine("EQ-9")
        with self.use(None), self.assertRaises(PermissionError):
            self.ca.require_machine("EQ-1")

    def test_operator_cannot_manage_accounts(self):
        with self.use(OPERATOR), self.assertRaises(PermissionError):
            self.ca.list_accounts()

    def test_customer_admin_is_kept_to_their_own_customer(self):
        with self.use(ADMIN):
            self.assertEqual(self.ca._scope(customer="CUST-B"), ("CUST-A", False))

    def test_customer_admin_cannot_invite_another_admin(self):
        with self.use(ADMIN), self.assertRaises(PermissionError):
            self.ca.invite("Someone", "s@c.test", "Customer admin")

    def test_staff_account_email_is_refused(self):
        self.frappe.get_roles.return_value = ["Maintenance Manager"]
        self.frappe.db.exists = MagicMock(return_value=True)
        self.frappe.db.get_value = MagicMock(side_effect=lambda dt, *a, **k: Dict(name="tech@x.test", user_type="System User") if dt == "User" else None)
        with self.use(None), patch.object(self.ca, "_machines_for", return_value=[]):
            with self.assertRaises(Exception) as caught:
                self.ca.invite("Tech", "tech@x.test", "Operator", customer="CUST-A")
        self.assertIn("staff account", str(caught.exception))

    def test_one_customer_per_person(self):
        self.frappe.get_roles.return_value = ["Maintenance Manager"]
        self.frappe.db.exists = MagicMock(return_value=True)
        def get_value(dt, *a, **k):
            return Dict(name="x", customer="CUST-B") if dt == "Techy Customer User" else None
        self.frappe.db.get_value = MagicMock(side_effect=get_value)
        with self.use(None), patch.object(self.ca, "_machines_for", return_value=[]):
            with self.assertRaises(Exception) as caught:
                self.ca.invite("Pat", "pat@c.test", "Operator", customer="CUST-A")
        self.assertIn("another customer", str(caught.exception))

    def test_machines_must_belong_to_the_customer(self):
        self.frappe.get_all = MagicMock(return_value=["EQ-1"])
        self.assertEqual(self.ca._machines_for("CUST-A", '["EQ-1", "EQ-1"]'), ["EQ-1"])
        with self.assertRaises(Exception):
            self.ca._machines_for("CUST-A", ["EQ-1", "EQ-B"])

    def test_admin_cannot_change_an_admin_or_themselves(self):
        doc = MagicMock(user="amina@c.test", access="Customer admin", enabled=1)
        with self.use(ADMIN), patch.object(self.ca, "_record", return_value=doc):
            with self.assertRaises(PermissionError):
                self.ca.update_account("amina@c.test", enabled=0)

    def test_switching_off_stops_sign_in(self):
        doc = MagicMock(user="otieno@c.test", access="Operator", enabled=1, machines=[])
        with self.use(ADMIN), patch.object(self.ca, "_record", return_value=doc), patch.object(self.ca, "_row", return_value={}):
            self.ca.update_account("otieno@c.test", enabled=0)
        self.assertEqual(doc.enabled, 0)
        self.frappe.db.set_value.assert_any_call("User", "otieno@c.test", "enabled", 0)

    # The guard on every request -----------------------------------------------------------------------------

    def guard(self, path, form=None, acc=OPERATOR):
        self.frappe.local.request = SimpleNamespace(path=path)
        self.frappe.local.form_dict = form or {}
        with patch.object(self.ca, "account", return_value=acc):
            self.ca.guard()

    def test_guard_allows_the_plant_app(self):
        self.guard("/api/method/projectit.plant.me")
        self.guard("/api/v2/method/projectit.customer_accounts.list_accounts")
        self.guard("/api/method/frappe.auth.get_logged_user")
        self.guard("/techy-app/plant")
        self.guard("/api/method/logout", acc=None)  # a switched-off account can still sign out

    def test_guard_refuses_everything_else(self):
        for path in ("/api/method/projectit.work_orders.list_work_orders", "/api/resource/Techy Equipment",
                "/api/v2/method/projectit.health.machine_health", "/api/method/frappe.client.get_list", "/api/method/upload_file",
                "/api/v2/document/Customer"):
            with self.subTest(path=path), self.assertRaises(PermissionError):
                self.guard(path)
        with self.assertRaises(PermissionError):
            self.guard("/", form={"cmd": "frappe.client.get_list"})

    def test_guard_refuses_a_switched_off_account(self):
        with self.assertRaises(PermissionError):
            self.guard("/api/method/projectit.plant.me", acc=None)

    def test_guard_leaves_staff_alone(self):
        self.frappe.get_roles.return_value = ["Maintenance User"]
        self.guard("/api/method/projectit.work_orders.list_work_orders")


if __name__ == "__main__":
    unittest.main()
