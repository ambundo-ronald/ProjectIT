"""Contract tests for status, presence and message reminders."""
import importlib
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class PresenceTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.p = importlib.import_module("projectit.presence")
        self.seen = {}
        self.frappe.cache = MagicMock()
        self.frappe.cache.hget.side_effect = lambda key, user: self.seen.get(user)
        self.frappe.cache.hset.side_effect = lambda key, user, value: self.seen.__setitem__(user, value)

    def test_online_means_seen_recently_and_not_away(self):
        self.seen = {"a@x": time.time() - 30, "b@x": time.time() - 600, "c@x": time.time()}
        self.frappe.get_all.return_value = [Dict(user="c@x", emoji="🚐", status_text="On site", clear_at=None, away=1)]
        result = self.p.presence(["a@x", "b@x", "c@x", "d@x"])
        self.assertEqual({u: r["online"] for u, r in result.items()}, {"a@x": True, "b@x": False, "c@x": False,
            "d@x": False})
        self.assertEqual((result["c@x"]["away"], result["c@x"]["emoji"], result["c@x"]["text"]), (True, "🚐", "On site"))

    def test_expired_status_is_hidden(self):
        self.frappe.get_all.return_value = [Dict(user="a@x", emoji="🍽️", status_text="At lunch",
            clear_at="2026-10-11 08:00:00", away=0)]
        self.assertIsNone(self.p.presence(["a@x"])["a@x"]["text"])  # it is 09:00 in the test clock

    def test_heartbeat_marks_me_seen(self):
        self.frappe.get_all.return_value = []
        result = self.p.heartbeat('["boss@example.com"]')
        self.assertIn("tech@example.com", self.seen)
        self.assertTrue(result["tech@example.com"]["online"])
        self.assertIn("boss@example.com", result)

    def test_set_status(self):
        self.frappe.get_all.return_value = []
        self.frappe.db.exists.return_value = True
        self.p.set_status("🚐", "On site at Bahari", "1h")
        values = self.frappe.db.set_value.call_args.args[2]
        self.assertEqual((values["emoji"], values["status_text"], str(values["clear_at"])),
            ("🚐", "On site at Bahari", "2026-10-11 10:00:00"))
        self.p.set_status(away=1)
        self.assertEqual(self.frappe.db.set_value.call_args.args[2], {"away": 1})
        with self.assertRaises(ValidationError):
            self.p.set_status("🚐", "x", "forever")
        with self.assertRaises(ValidationError):
            self.p.set_status()


class ReminderTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.r = importlib.import_module("projectit.reminders")

    def test_when(self):
        thursday = datetime(2026, 10, 15, 16, 30)
        self.assertEqual(self.r.remind_at("1h", thursday), datetime(2026, 10, 15, 17, 30))
        self.assertEqual(self.r.remind_at("tomorrow", thursday), datetime(2026, 10, 16, 8, 0))
        self.assertEqual(self.r.remind_at("monday", thursday), datetime(2026, 10, 19, 8, 0))
        self.assertEqual(self.r.remind_at("monday", datetime(2026, 10, 19, 7, 0)), datetime(2026, 10, 26, 8, 0))

    def test_only_readable_channel_messages(self):
        self.frappe.db.get_value.return_value = Dict(name="C1", reference_doctype="Task", comment_type="Comment")
        with self.assertRaises(ValidationError):
            self.r.remind("C1", "1h")
        with self.assertRaises(ValidationError):
            self.r.remind("C1", "next year")

    def test_cancel_only_mine(self):
        self.frappe.db.get_value.return_value = "boss@example.com"
        with self.assertRaises(ValidationError):
            self.r.cancel("R1")
        self.frappe.delete_doc.assert_not_called()

    def test_due_reminders_notify_once(self):
        self.frappe.get_all.return_value = [Dict(name="R1", user="tina@x", channel="general", message="C1",
            note="Call the client")]
        self.frappe.utils.escape_html = lambda s: s
        made = MagicMock()
        self.frappe.get_doc.return_value = made
        self.r.send_due()
        self.frappe.db.set_value.assert_called_once_with("Techy Chat Reminder", "R1", "sent", 1, update_modified=False)
        log = self.frappe.get_doc.call_args.args[0]
        self.assertEqual((log["for_user"], log["subject"]), ("tina@x", "Reminder: Call the client"))
        self.assertEqual(self.frappe.publish_realtime.call_args.kwargs["user"], "tina@x")


if __name__ == "__main__":
    unittest.main()
