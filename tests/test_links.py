"""Contract tests for chat document links: search and resolve follow each screen's visibility."""
import importlib
import unittest

from test_ops import Dict, OpsTestCase


class LinkTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.get_time = lambda value: value  # needed to import projectit.attendance for tasks
        self.links = importlib.import_module("projectit.links")
        self.frappe.get_list.return_value = []
        self.frappe.get_all.return_value = []

    def filters(self, mock):
        return mock.call_args.kwargs["filters"]

    def test_readable_text_for_notifications(self):
        self.assertEqual(self.links.readable("see [[project:PROJ-0001]] and [[work-order:TASK-9]]"),
            "see Project PROJ-0001 and Work order TASK-9")
        self.assertEqual(self.links.readable("[[nope:X]]"), "[[nope:X]]")

    def test_unknown_kind_rejected(self):
        with self.assertRaises(Exception):
            self.links.search_links("employee", "a")

    def test_portal_users_rejected(self):
        self.frappe.get_cached_value.return_value = "Website User"
        with self.assertRaises(PermissionError):
            self.links.search_links("project")
        with self.assertRaises(PermissionError):
            self.links.resolve_links(["project:P-1"])

    def test_project_search_uses_native_permissions(self):
        self.frappe.get_list.return_value = [Dict(name="PROJ-1", title="Pump house", detail="Open")]
        rows = self.links.search_links("project", " pump ")
        self.assertEqual(rows, [{"kind": "project", "name": "PROJ-1", "title": "Pump house", "detail": "Open"}])
        call = self.frappe.get_list.call_args
        self.assertEqual(call.args[0], "Project")
        self.assertEqual(call.kwargs["or_filters"], {"name": ["like", "%pump%"], "project_name": ["like", "%pump%"]})
        self.frappe.get_all.assert_not_called()

    def test_staff_see_only_requests_they_raised(self):
        self.links.search_links("request")
        self.assertEqual(self.filters(self.frappe.get_all)["raised_by"], "tech@example.com")
        self.manager()
        self.links.search_links("request")
        self.assertNotIn("raised_by", self.filters(self.frappe.get_all))

    def test_staff_see_only_their_work_orders(self):
        self.frappe.get_all.side_effect = [["TASK-1"], ["TASK-2"]]  # assigned ToDos, then owned work orders
        self.links.search_links("work-order")
        self.assertEqual(sorted(self.filters(self.frappe.get_list)["name"][1]), ["TASK-1", "TASK-2"])

    def test_assets_hidden_without_asset_access(self):
        self.frappe.has_permission.return_value = False
        self.assertEqual(self.links.search_links("asset"), [])
        self.frappe.get_all.assert_not_called()

    def test_tasks_need_an_employee_for_staff(self):
        self.frappe.get_all.return_value = []  # no Employee for the user
        self.assertEqual(self.links.search_links("task"), [])
        self.frappe.get_list.assert_not_called()

    def test_resolve_only_returns_visible_references(self):
        self.frappe.get_all.side_effect = [["TASK-1"], [], [Dict(name="TASK-1", title="Fix pump", detail="Open")]]
        self.frappe.get_list.side_effect = lambda doctype, **kw: [Dict(name="TASK-1", title="Fix pump",
            detail="Open")] if "TASK-1" in kw["filters"]["name"][1] else []
        found = self.links.resolve_links(["work-order:TASK-1", "work-order:TASK-7", "bogus:1", "project"])
        self.assertEqual(found, {"work-order:TASK-1": {"title": "Fix pump", "detail": "Open"}})
        # TASK-7 is not assigned to or owned by the user, so it is never queried.
        self.assertEqual(self.filters(self.frappe.get_list)["name"], ["in", ["TASK-1"]])

    def test_resolve_caps_batch(self):
        self.manager()
        self.links.resolve_links([f"project:P-{i}" for i in range(500)])
        self.assertEqual(len(self.filters(self.frappe.get_list)["name"][1]), 100)

    def test_chat_notification_shows_readable_links(self):
        channel = Dict(name="dm-1", channel_name="dm-1", is_direct=1, archived=0,
            members=[Dict(user="tech@example.com"), Dict(user="boss@example.com")])
        self.frappe.get_doc.side_effect = lambda doctype, *a, **k: channel if doctype == "Techy Channel" else \
            Dict(name="C-1", content=k.get("content", ""), comment_email="tech@example.com", comment_by="Tech",
                creation="2026-10-11 09:00:00", insert=lambda **kw: None)
        comment = Dict(name="C-1", content="x", comment_email="tech@example.com", comment_by="Tech",
            creation="2026-10-11 09:00:00")
        self.chat._comment = lambda *a, **k: comment
        self.chat.post_message("dm-1", "check [[project:PROJ-1]]")
        subject = self.notification.enqueue_create_notification.call_args.args[1]["subject"]
        self.assertIn("check Project PROJ-1", subject)


if __name__ == "__main__":
    unittest.main()
