"""Signing in from the phone app: device tokens and signed links (projectit.device_auth)."""
import hashlib
import hmac
import importlib.util
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


class AuthenticationError(Exception):
    pass


class Dict(dict):
    __getattr__ = dict.get


def load():
    frappe = ModuleType("frappe")
    frappe.whitelist = lambda **kwargs: lambda fn: fn
    frappe._ = lambda text: text
    frappe.AuthenticationError = AuthenticationError
    frappe.PermissionError = PermissionError

    def throw(message, exc=Exception):
        raise exc(message)
    frappe.throw = throw
    frappe.db = MagicMock()
    frappe.set_user = MagicMock()
    frappe.get_doc = MagicMock()
    frappe.get_all = MagicMock(return_value=[])
    frappe.generate_hash = lambda length=10: "t" * length
    frappe.session = SimpleNamespace(user="Guest")
    frappe.local = SimpleNamespace(site="ops.test", request=None, form_dict={})
    utils = ModuleType("frappe.utils")
    utils.now_datetime = lambda: datetime(2026, 11, 12, 9)
    utils.time_diff_in_seconds = lambda a, b: (a - b).total_seconds()
    utils.get_url = lambda path="": f"https://ops.test{path}"
    frappe.utils = utils
    rl = ModuleType("frappe.rate_limiter")
    rl.rate_limit = lambda **kwargs: lambda fn: fn
    spec = importlib.util.spec_from_file_location("device_auth_under_test",
        Path(__file__).resolve().parents[1] / "projectit/device_auth.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"frappe": frappe, "frappe.utils": utils, "frappe.rate_limiter": rl}):
        spec.loader.exec_module(module)
    return module


TOKEN = "secret-token"
KEY = hashlib.sha256(TOKEN.encode()).hexdigest()


def sign(path, expires):
    """What the app does (data/native.js), to check the server agrees."""
    return hmac.new(KEY.encode(), f"{path}|{expires}".encode(), hashlib.sha256).hexdigest()


class DeviceAuthTests(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.f = self.m.frappe
        self.device = Dict(name="DEV-1", user="tech@example.com", token_hash=KEY, last_seen=datetime(2026, 11, 12, 8, 59))
        self.enabled = 1

        def get_value(doctype, filters, fields=None, **kwargs):
            if doctype == "User":
                return self.enabled
            wanted = filters if isinstance(filters, dict) else {"name": filters}
            match = all(self.device.get(k) == v for k, v in wanted.items() if k != "revoked")
            return self.device if match and not self.device.get("revoked") else None
        self.f.db.get_value = MagicMock(side_effect=get_value)

    def request(self, method="POST", path="/api/method/projectit.ops.bootstrap", headers=None, query=""):
        args = dict(p.split("=", 1) for p in query.split("&") if p)
        self.f.local.request = SimpleNamespace(method=method, path=path, headers=headers or {}, args=args,
            query_string=query.encode())

    # Device token ---------------------------------------------------------------------------------------------
    def test_token_signs_the_request_in(self):
        self.request(headers={"X-Techy-Device": TOKEN})
        self.m.authenticate()
        self.f.set_user.assert_called_once_with("tech@example.com")
        self.assertEqual(self.f.local.techy_device, "DEV-1")

    def test_request_arguments_survive_signing_in(self):
        # frappe.set_user empties form_dict; the job, project or log the phone sent must still arrive.
        args = {"cmd": "projectit.work_orders.get_work_order", "name": "TASK-1"}
        self.f.local.form_dict = args
        self.f.set_user.side_effect = lambda user: setattr(self.f.local, "form_dict", {})
        self.request(headers={"X-Techy-Device": TOKEN})
        self.m.authenticate()
        self.assertEqual(self.f.local.form_dict, args)

    def test_unknown_token_is_refused(self):
        self.request(headers={"X-Techy-Device": "wrong"})
        with self.assertRaises(AuthenticationError):
            self.m.authenticate()
        self.f.set_user.assert_not_called()

    def test_revoked_device_is_refused(self):
        self.device["revoked"] = 1
        self.request(headers={"X-Techy-Device": TOKEN})
        with self.assertRaises(AuthenticationError):
            self.m.authenticate()
        self.f.set_user.assert_not_called()

    def test_disabled_user_is_refused(self):
        self.enabled = 0
        self.request(headers={"X-Techy-Device": TOKEN})
        with self.assertRaises(AuthenticationError):
            self.m.authenticate()
        self.f.set_user.assert_not_called()

    def test_existing_session_is_left_alone(self):
        self.f.session.user = "someone@example.com"
        self.request(headers={"X-Techy-Device": "anything"})
        self.m.authenticate()
        self.f.set_user.assert_not_called()

    def test_last_seen_updated_at_most_every_ten_minutes(self):
        self.request(headers={"X-Techy-Device": TOKEN})
        self.m.authenticate()
        self.f.db.set_value.assert_not_called()  # seen a minute ago
        self.device["last_seen"] = datetime(2026, 11, 12, 8, 30)
        self.m.authenticate()
        self.f.db.set_value.assert_called_once()

    # Signed links ---------------------------------------------------------------------------------------------
    def signed(self, path, query="", expires=None, method="GET", tamper=None):
        expires = expires or int(time.time()) + 3600
        base = path + (f"?{query}" if query else "")
        signature = sign(base, expires)
        q = (f"{query}&" if query else "") + f"_td=DEV-1&_te={expires}&_ts={tamper or signature}"
        self.request(method=method, path=path, query=q)

    def test_signed_private_file_and_download_open(self):
        self.signed("/private/files/pump photo.jpg")
        self.m.authenticate()
        self.signed("/api/method/projectit.service_report.download", "name=TASK-0001")
        self.m.authenticate()
        self.assertEqual(self.f.set_user.call_count, 2)

    def test_signed_link_refused_when_tampered_expired_or_not_allowed(self):
        cases = [
            dict(path="/private/files/a.jpg", tamper="0" * 64),
            dict(path="/private/files/a.jpg", expires=int(time.time()) - 5),
            dict(path="/private/files/a.jpg", expires=int(time.time()) + 3 * 86400),
            dict(path="/private/files/a.jpg", method="POST"),
            dict(path="/api/method/projectit.work_orders.update_work_order", query="name=X&status=Completed"),
            dict(path="/desk/sales-invoice"),
        ]
        for case in cases:
            with self.subTest(**case):
                self.signed(**case)
                with self.assertRaises(AuthenticationError):
                    self.m.authenticate()
        self.f.set_user.assert_not_called()

    def test_signature_covers_the_query(self):
        expires = int(time.time()) + 3600
        good = sign("/api/method/projectit.service_report.download?name=TASK-1", expires)
        self.request(method="GET", path="/api/method/projectit.service_report.download",
            query=f"name=TASK-2&_td=DEV-1&_te={expires}&_ts={good}")
        with self.assertRaises(AuthenticationError):
            self.m.authenticate()

    # Sign in / out --------------------------------------------------------------------------------------------
    def test_sign_in_returns_a_token_and_stores_only_its_hash(self):
        self.m._check_password = MagicMock(return_value="tech@example.com")
        self.f.db.get_value = MagicMock(return_value=Dict(full_name="Tina Tech", user_type="System User"))
        result = self.m.sign_in("tech@example.com", "pw", "Pixel 8", "android", "1.0.0")
        stored = self.f.get_doc.call_args.args[0]
        self.assertEqual(stored["token_hash"], hashlib.sha256(result["token"].encode()).hexdigest())
        self.assertNotIn(result["token"], str(stored))
        self.assertEqual(result["full_name"], "Tina Tech")

    def test_sign_out_revokes_this_device(self):
        self.f.local.techy_device = "DEV-1"
        self.m.sign_out()
        self.f.db.set_value.assert_called_once_with("Techy Device", "DEV-1", "revoked", 1)

    def test_cannot_sign_out_someone_elses_device(self):
        self.f.session.user = "other@example.com"
        with self.assertRaises(PermissionError):
            self.m.sign_out_device("DEV-1")


if __name__ == "__main__":
    unittest.main()
