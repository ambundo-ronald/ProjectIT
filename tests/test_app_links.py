"""The Android app's side of the site (projectit.app_links): signing-key fingerprints, assetlinks.json, the version
the app needs, and account deletion requests."""
import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from test_ops import OpsTestCase

KEY = "14:6D:E9:83:C5:73:06:50:D8:EE:B9:95:2F:34:FC:64:16:A0:83:42:E6:1D:BE:A8:8A:04:96:B2:3F:CF:44:E5"


class AppLinksTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        base = ModuleType("frappe.website.page_renderers.base_renderer")
        base.BaseRenderer = type("BaseRenderer", (), {"__init__": lambda self, path=None, http_status_code=None: setattr(self, "path", path)})
        werk = ModuleType("werkzeug.wrappers")
        werk.Response = MagicMock()
        self.frappe.utils.escape_html = lambda v: v
        mods = {"frappe.website": ModuleType("frappe.website"), "frappe.website.page_renderers": ModuleType("frappe.website.page_renderers"),
            "frappe.website.page_renderers.base_renderer": base, "werkzeug": ModuleType("werkzeug"), "werkzeug.wrappers": werk}
        patcher = patch.dict(sys.modules, mods)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.settings = {}
        self.frappe.db.get_single_value = MagicMock(side_effect=lambda dt, f: self.settings.get(f))
        self.m = importlib.import_module("projectit.app_links")

    def test_fingerprints_accept_the_ways_people_paste_them(self):
        bare = KEY.replace(":", "").lower()
        self.settings["android_app_fingerprints"] = f"{KEY}\n {bare} \nnot a key, {KEY[:20]}"
        self.assertEqual(self.m.fingerprints(), [KEY, KEY])

    def test_asset_links_list_the_app_only_with_a_key(self):
        self.assertEqual(self.m.asset_links(), [])  # no key yet: Android does not trust the site, links stay in the browser
        self.settings["android_app_fingerprints"] = KEY
        links = self.m.asset_links()
        self.assertEqual(links[0]["target"]["package_name"], "com.techyapp.field")
        self.assertEqual(links[0]["target"]["sha256_cert_fingerprints"], [KEY])
        self.assertEqual(links[0]["relation"], ["delegate_permission/common.handle_all_urls"])

    def test_only_the_well_known_path_is_answered(self):
        from types import SimpleNamespace
        exc = ModuleType("werkzeug.exceptions")

        class HTTPException(Exception):
            def __init__(self, response=None):
                self.response = response
        exc.HTTPException = HTTPException
        with patch.dict(sys.modules, {"werkzeug.exceptions": exc}):
            self.frappe.local.request = SimpleNamespace(method="GET", path="/techy-app")
            self.assertIsNone(self.m.serve_asset_links())
            self.frappe.local.request = SimpleNamespace(method="GET", path="/.well-known/assetlinks.json")
            with self.assertRaises(HTTPException):
                self.m.serve_asset_links()

    def test_open_in_app_waits_for_the_company_to_publish_the_app(self):
        self.assertFalse(self.m.app_info()["android_app"])
        self.settings["android_app_url"] = "https://play.google.com/store/apps/details?id=com.techyapp.field"
        info = self.m.app_info()
        self.assertTrue(info["android_app"])
        self.assertEqual(info["min_app_version"], self.m.MIN_APP_VERSION)

    def test_deletion_needs_a_signed_in_person_or_a_valid_email(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.m.request_deletion("bye")
        with self.assertRaises(Exception):
            self.m.request_deletion_by_email("not-an-email")

    def test_deletion_request_tells_the_admins_and_says_the_same_for_unknown_emails(self):
        with patch.object(self.m, "_tell_admins") as tell:
            self.assertEqual(self.m.request_deletion_by_email(" Nobody@Example.com "), {"ok": True})
        tell.assert_called_once_with("nobody@example.com", "", False)
