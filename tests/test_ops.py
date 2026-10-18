"""Contract tests for Techy Ops work orders, requests, PM and chat (no live Bench required)."""
import importlib
import json
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


class ValidationError(Exception):
    pass


def fail(message, exception=ValidationError):
    raise exception(message)


class Dict(dict):
    __getattr__ = dict.get

    def __setattr__(self, key, value):
        self[key] = value


class OpsTestCase(unittest.TestCase):
    """Loads projectit.{ops,work_orders,maintenance,work_requests,chat} against a stub frappe."""

    def setUp(self):
        frappe = ModuleType("frappe")
        frappe.whitelist = lambda **kwargs: lambda fn: fn
        frappe._ = lambda text: text
        frappe.throw = fail
        frappe.PermissionError = PermissionError
        frappe.parse_json = json.loads
        frappe._dict = Dict
        frappe.session = SimpleNamespace(user="tech@example.com")
        frappe.local = SimpleNamespace(site="site.test", form_dict={"cmd": "x"},
            session=SimpleNamespace(user="tech@example.com", sid="sid-1", data={"csrf_token": "t"}))
        frappe.conf = SimpleNamespace(socketio_port=9000)
        frappe.get_roles = MagicMock(return_value=["Employee"])
        for name in ("get_doc", "get_list", "get_all", "has_permission", "get_cached_doc", "publish_realtime",
                "delete_doc", "log_error", "set_user", "enqueue"):
            setattr(frappe, name, MagicMock())
        frappe.get_cached_value = MagicMock(return_value="System User")
        frappe.get_cached_doc.return_value = SimpleNamespace(allow_guest_requests=0, pm_lead_days=3)
        frappe.db = MagicMock()
        frappe.db.escape = lambda value: f"'{value}'"
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value: int(value or 0)
        utils.flt = lambda value: float(value or 0)
        def add_months(value, months):
            d = date.fromisoformat(str(value)[:10])
            m = d.month - 1 + months
            return date(d.year + m // 12, m % 12 + 1, min(d.day, 28))
        utils.add_months = add_months
        utils.strip_html = lambda text: text
        utils.getdate = lambda value=None: date.fromisoformat(str(value)[:10]) if value else date(2026, 10, 11)
        utils.nowdate = lambda: "2026-10-11"
        utils.add_days = lambda value, days: str(date.fromisoformat(str(value)) .__add__(__import__("datetime").timedelta(days=days)))
        utils.get_datetime = lambda value: datetime.fromisoformat(str(value))
        utils.now_datetime = lambda: datetime(2026, 10, 11, 9)
        utils.add_to_date = lambda value, minutes=0, hours=0: utils.get_datetime(value) + timedelta(minutes=minutes,
            hours=hours)
        utils.time_diff_in_seconds = lambda end, start: (utils.get_datetime(end) - utils.get_datetime(start)).total_seconds()
        utils.format_date = lambda value, fmt=None: str(value)[:10] if value else ""
        utils.format_datetime = lambda value, fmt=None: str(value)[:16] if value else ""
        utils.get_fullname = lambda user=None: (user or frappe.session.user).split("@")[0].title()
        utils.validate_email_address = lambda value, throw=False: value if "@" in value else fail("Invalid email")
        frappe.utils = utils
        rate = ModuleType("frappe.rate_limiter")
        rate.rate_limit = lambda **kwargs: lambda fn: fn
        notification = ModuleType("frappe.desk.doctype.notification_log.notification_log")
        notification.enqueue_create_notification = MagicMock()
        assign = ModuleType("frappe.desk.form.assign_to")
        assign.add, assign.remove = MagicMock(), MagicMock()
        self.notification, self.assign = notification, assign
        modules = {"frappe": frappe, "frappe.utils": utils, "frappe.rate_limiter": rate,
            "frappe.desk.doctype.notification_log.notification_log": notification,
            "frappe.desk.form.assign_to": assign}
        for name in ("frappe.desk", "frappe.desk.doctype", "frappe.desk.doctype.notification_log", "frappe.desk.form"):
            modules[name] = ModuleType(name)
        patcher = patch.dict(sys.modules, modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        sys.path.insert(0, str(ROOT))
        self.addCleanup(sys.path.remove, str(ROOT))
        for name in [m for m in sys.modules if m == "projectit" or m.startswith("projectit.")]:
            del sys.modules[name]
        self.addCleanup(lambda: [sys.modules.pop(m) for m in list(sys.modules) if m == "projectit" or m.startswith("projectit.")])
        self.ops = importlib.import_module("projectit.ops")
        self.wo = importlib.import_module("projectit.work_orders")
        self.pm = importlib.import_module("projectit.maintenance")
        self.req = importlib.import_module("projectit.work_requests")
        self.chat = importlib.import_module("projectit.chat")
        self.frappe = frappe

    def manager(self):
        self.frappe.get_roles.return_value = ["Maintenance Manager"]


class WorkOrderTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.doc = MagicMock()
        self.doc.name, self.doc.owner, self.doc.custom_work_order = "TASK-1", "boss@example.com", 1
        self.doc.modified, self.doc.status = "2026-10-01 10:00:00", "Open"
        self.frappe.get_doc.return_value = self.doc

    def test_portal_users_rejected(self):
        self.frappe.get_cached_value.return_value = "Website User"
        with self.assertRaises(PermissionError):
            self.wo.list_work_orders()

    def test_guest_rejected(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.wo.list_work_orders()

    def test_technician_cannot_list_everyone(self):
        self.frappe.get_all.return_value = ["TASK-1"]
        self.frappe.get_list.return_value = []
        self.wo.list_work_orders(scope="all")
        or_filters = self.frappe.get_list.call_args.kwargs["or_filters"]
        self.assertEqual(or_filters, {"name": ["in", ["TASK-1"]], "owner": "tech@example.com"})

    def test_manager_lists_everyone(self):
        self.manager()
        self.frappe.get_list.return_value = []
        self.wo.list_work_orders(scope="all")
        self.assertIsNone(self.frappe.get_list.call_args.kwargs["or_filters"])

    def test_unassigned_technician_cannot_open_work_order(self):
        self.frappe.get_all.return_value = []
        self.doc.status = "Working"  # not an open job anyone may pick up
        with self.assertRaises(PermissionError) as caught:
            self.wo._work_order("TASK-1")
        self.assertIn("not assigned to you", str(caught.exception))  # the app's clear message, before ERPNext's

    def test_plain_task_is_not_a_work_order(self):
        self.manager()
        self.doc.custom_work_order = 0
        with self.assertRaises(ValidationError):
            self.wo._work_order("TASK-1")

    def test_technician_cannot_assign_others(self):
        self.frappe.has_permission.return_value = True
        self.frappe.get_all.return_value = ["tech@example.com", "other@example.com"]
        with self.assertRaises(PermissionError):
            self.wo.create_work_order("Fix pump", assignees=["tech@example.com", "other@example.com"])

    def test_stale_update_rejected(self):
        self.manager()
        with self.assertRaises(ValidationError):
            self.wo.update_work_order("TASK-1", "2020-01-01", status="Completed")
        self.doc.save.assert_not_called()

    def test_technician_cannot_cancel_or_reprioritise(self):
        self.frappe.get_all.return_value = [Dict(reference_name="TASK-1", allocated_to="tech@example.com")]
        self.frappe.db.get_value.return_value = None
        with self.assertRaises(PermissionError):
            self.wo.update_work_order("TASK-1", self.doc.modified, status="Cancelled")
        with self.assertRaises(PermissionError):
            self.wo.update_work_order("TASK-1", self.doc.modified, priority="Urgent")
        self.doc.save.assert_not_called()

    def test_workflow_cannot_be_bypassed(self):
        self.manager()
        self.frappe.db.get_value.return_value = "Task Approval"
        with self.assertRaises(ValidationError):
            self.wo.update_work_order("TASK-1", self.doc.modified, status="Completed")

    def test_completion_closes_pm_log_and_request(self):
        task = MagicMock(custom_work_order=1, status="Completed", owner="boss@example.com",
            custom_asset_maintenance_log="LOG-1", custom_work_request="ISS-1", project=None)
        task.name = "TASK-1"
        task.get.side_effect = lambda key: getattr(task, key)
        task.has_value_changed.return_value = True
        request = MagicMock(status="Open", raised_by="tech@example.com", subject="Leak")
        request.name = "ISS-1"
        self.frappe.get_doc.return_value = request
        self.frappe.get_all.return_value = []
        with patch.object(self.pm, "complete_log") as complete:
            self.wo.on_task_update(task)
        complete.assert_called_once_with(task)
        self.assertEqual(request.status, "Resolved")
        request.save.assert_called_once()

    def test_certificate_required_before_completion(self):
        task = MagicMock(custom_asset_maintenance_log="LOG-1", status="Completed")
        task.name = "TASK-1"
        task.get.side_effect = lambda key: getattr(task, key)
        task.has_value_changed.return_value = True
        self.frappe.db.get_value.return_value = 1
        self.frappe.get_all.return_value = []
        with self.assertRaises(ValidationError):
            self.wo.validate_task(task)


class MaintenanceTests(OpsTestCase):
    def test_pm_generation_skips_raised_logs(self):
        logs = [Dict(name="LOG-1", asset_name="A1", task="T1", task_name="Grease", due_date="2026-10-12"),
            Dict(name="LOG-2", asset_name="A2", task="T2", task_name="Inspect", due_date="2026-10-12")]
        self.frappe.get_all.side_effect = [logs, ["LOG-1"]]
        self.frappe.db.get_value.return_value = {"assign_to": "tech@example.com", "description": "Check"}
        created = MagicMock()
        created.name = "TASK-9"
        with patch.object(self.wo, "create", return_value=created) as create:
            self.assertEqual(self.pm.generate_pm_work_orders(), ["TASK-9"])
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["pm_log"], "LOG-2")
        self.assertEqual(create.call_args.kwargs["category"], "Preventive")
        self.assertEqual(create.call_args.kwargs["assignees"], ["tech@example.com"])
        filters = self.frappe.get_all.call_args_list[0].kwargs["filters"]
        self.assertEqual(filters["due_date"], ["<=", "2026-10-14"])

    def test_failed_pm_rolls_back_and_continues(self):
        logs = [Dict(name="LOG-1", asset_name="A1", task="T1", task_name="Grease", due_date="2026-10-12")]
        self.frappe.get_all.side_effect = [logs, []]
        self.frappe.db.get_value.return_value = {}
        with patch.object(self.wo, "create", side_effect=ValidationError("bad")):
            self.assertEqual(self.pm.generate_pm_work_orders(), [])
        self.frappe.db.rollback.assert_called_once_with(save_point="techy_pm")
        self.frappe.log_error.assert_called_once()

    def test_complete_log_submits_completed(self):
        log = MagicMock(docstatus=0, has_certificate=0)
        self.frappe.get_doc.return_value = log
        work_order = MagicMock(custom_asset_maintenance_log="LOG-1")
        work_order.name = "TASK-1"
        self.pm.complete_log(work_order)
        self.assertEqual(log.maintenance_status, "Completed")
        self.assertEqual(log.completion_date, "2026-10-11")
        log.submit.assert_called_once()
        self.assertEqual(self.frappe.set_user.call_args_list[-1].args, ("tech@example.com",))
        self.assertEqual(self.frappe.local.session.sid, "sid-1")

    def test_complete_log_restores_user_on_failure(self):
        log = MagicMock(docstatus=0, has_certificate=0)
        log.submit.side_effect = ValidationError("boom")
        self.frappe.get_doc.return_value = log
        with self.assertRaises(ValidationError):
            self.pm.complete_log(MagicMock(custom_asset_maintenance_log="LOG-1"))
        self.assertEqual(self.frappe.set_user.call_args_list[-1].args, ("tech@example.com",))

    def test_run_now_requires_manager(self):
        with self.assertRaises(PermissionError):
            self.pm.run_pm_now()


class RequestTests(OpsTestCase):
    def test_states(self):
        self.assertEqual(self.req._state({"status": "Open"}), "Pending")
        self.assertEqual(self.req._state({"status": "Closed"}), "Declined")
        self.assertEqual(self.req._state({"status": "Open", "custom_work_order": "T"}), "Approved")
        self.assertEqual(self.req._state({"status": "Resolved", "custom_work_order": "T"}), "Done")

    def test_guest_requests_disabled_by_default(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.req.submit_guest_request("Leak", "a@b.co")
        self.assertEqual(self.req.request_context("A1"), {"allowed": False, "asset": None, "equipment": None})

    def test_staff_only_see_their_requests(self):
        self.frappe.get_all.return_value = []
        self.req.list_requests()
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"]["raised_by"], "tech@example.com")

    def test_approval_requires_manager(self):
        with self.assertRaises(PermissionError):
            self.req.approve_request("ISS-1")

    def test_handled_request_cannot_be_approved_twice(self):
        self.manager()
        self.frappe.get_doc.return_value = MagicMock(custom_maintenance_request=1, custom_work_order="TASK-1",
            status="Open")
        with patch.object(self.wo, "create") as create:
            with self.assertRaises(ValidationError):
                self.req.approve_request("ISS-1")
        create.assert_not_called()


class ChatTests(OpsTestCase):
    def channel(self, private=0, members=("tech@example.com",), direct=0):
        doc = MagicMock(is_private=private, is_direct=direct, archived=0, channel_name="general", description="",
            project=None, members=[SimpleNamespace(user=u) for u in members])
        doc.name = "general"
        doc.doctype = "Techy Channel"
        self.frappe.get_doc.return_value = doc
        return doc

    def test_private_channel_hidden_from_non_members(self):
        self.channel(private=1, members=("boss@example.com",))
        with self.assertRaises(PermissionError):
            self.chat.get_messages("general")

    def test_posting_requires_membership(self):
        self.channel(members=("boss@example.com",))
        with self.assertRaises(PermissionError):
            self.chat.post_message("general", "hello")

    def test_post_pushes_to_members_and_notifies_mentions(self):
        self.channel(members=("tech@example.com", "boss@example.com"))
        comment = MagicMock(content="hi", comment_email="tech@example.com", comment_by="Tech",
            creation="2026-10-11 09:00:00")
        comment.name = "C1"
        doc_for_comment = MagicMock()
        doc_for_comment.insert.return_value = comment
        channel_doc = self.frappe.get_doc.return_value
        self.frappe.get_doc.side_effect = lambda arg, *a, **k: doc_for_comment if isinstance(arg, dict) else channel_doc
        self.frappe.db.get_value.return_value = "ROW-1"
        message = self.chat.post_message("general", "ping @boss@example.com and @stranger@example.com")
        self.assertEqual(message["name"], "C1")
        users = [c.kwargs["user"] for c in self.frappe.publish_realtime.call_args_list]
        self.assertEqual(users, ["tech@example.com", "boss@example.com"])
        notified = self.notification.enqueue_create_notification.call_args.args[0]
        self.assertEqual(notified, ["boss@example.com"])

    def test_channel_name_validation(self):
        for bad in ("", "  ", "dm-sneaky", "!!!"):
            with self.assertRaises(ValidationError):
                self.chat.create_channel(bad)

    def test_direct_message_name_is_stable(self):
        self.frappe.get_all.return_value = ["boss@example.com"]
        self.frappe.db.exists.return_value = True
        first = self.chat.open_direct("boss@example.com")["name"]
        self.frappe.session.user = "boss@example.com"
        self.frappe.get_all.return_value = ["tech@example.com"]
        self.assertEqual(self.chat.open_direct("tech@example.com")["name"], first)

    def test_cannot_delete_others_messages(self):
        comment = MagicMock(reference_doctype="Techy Channel", reference_name="general", comment_type="Comment",
            comment_email="boss@example.com")
        channel = self.channel()
        self.frappe.get_doc.side_effect = lambda doctype, name=None, **k: comment if doctype == "Comment" else channel
        with self.assertRaises(PermissionError):
            self.chat.delete_message("C1")
        self.frappe.delete_doc.assert_not_called()

    def test_permission_hooks(self):
        doc = SimpleNamespace(is_private=1, members=[SimpleNamespace(user="boss@example.com")])
        self.assertFalse(self.chat.has_permission(doc, user="tech@example.com"))
        self.assertTrue(self.chat.has_permission(doc, user="boss@example.com"))
        self.assertIn("'tech@example.com'", self.chat.permission_query_conditions("tech@example.com"))
        self.frappe.get_roles.return_value = ["System Manager"]
        self.assertEqual(self.chat.permission_query_conditions("admin@example.com"), "")


class MentionTests(OpsTestCase):
    def test_mentions_parse_emails_and_skip_self(self):
        text = "hi @boss@example.com, @tech@example.com and mail@example.com"
        self.assertEqual(self.ops.mentions(text, {"boss@example.com", "tech@example.com"}), ["boss@example.com"])


if __name__ == "__main__":
    unittest.main()
