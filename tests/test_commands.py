"""Contract tests for chat slash commands: what counts as a command, and what each one does."""
import importlib
import unittest
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase


class CommandTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.commands = importlib.import_module("projectit.commands")
        self.channel = Dict(name="CH-1", project="PROJ-1", members=[Dict(user="tina@example.com"), Dict(user="tech@example.com")])

    def test_what_counts_as_a_command(self):
        parse = self.commands.parse
        self.assertEqual(parse("/job Pump leaking"), ("job", "Pump leaking"))
        self.assertEqual(parse("  /HELP "), ("help", ""))
        self.assertIsNone(parse("Pump /job leaking"))
        self.assertIsNone(parse("/files/x.png"))
        self.assertIsNone(self.commands.run(self.channel, "Just a message"))

    def test_unknown_command(self):
        with self.assertRaises(Exception) as caught:
            self.commands.run(self.channel, "/jbo pump")
        self.assertIn("/help", str(caught.exception))

    def test_job_with_assignee_and_priority(self):
        wo = importlib.import_module("projectit.work_orders")
        chat = importlib.import_module("projectit.chat")
        self.frappe.get_all = MagicMock(return_value=["tina@example.com"])
        with patch.object(wo, "create_work_order", return_value={"name": "TASK-9"}) as create, \
                patch.object(chat, "post_system_message") as posted:
            r = self.commands.run(self.channel, "/job Pump leaking   at clinic @tina@example.com !urgent")
        args, kwargs = create.call_args
        self.assertEqual(args[0], "Pump leaking at clinic")
        self.assertEqual((kwargs["priority"], kwargs["assignees"], kwargs["project"], kwargs["category"]),
            ("Urgent", ["tina@example.com"], "PROJ-1", "Corrective"))
        self.assertIn("[[work-order:TASK-9]]", posted.call_args.args[1])
        self.assertIn("[[work-order:TASK-9]]", r["reply"])
        self.assertEqual(r["command"], "job")

    def test_job_needs_a_description(self):
        with self.assertRaises(Exception):
            self.commands.run(self.channel, "/job !high")

    def test_remind(self):
        reminders = importlib.import_module("projectit.reminders")
        with patch.object(reminders, "add", return_value={"name": "R1", "remind_at": "2026-10-11 10:00:00"}) as add:
            self.commands.run(self.channel, "/remind 1h Call the clinic")
        self.assertEqual(add.call_args.args, ("CH-1", None, "Call the clinic", "1h"))
        for bad in ("/remind", "/remind 1h", "/remind later Call"):
            with self.assertRaises(Exception):
                self.commands.run(self.channel, bad)

    def test_status_away_back(self):
        presence = importlib.import_module("projectit.presence")
        with patch.object(presence, "set_status") as status:
            self.commands.run(self.channel, "/status 🚗 On the road")
            self.assertEqual(status.call_args.kwargs, {"emoji": "🚗", "text": "On the road"})
            self.commands.run(self.channel, "/status In a meeting")
            self.assertEqual(status.call_args.kwargs, {"emoji": "", "text": "In a meeting"})
            self.commands.run(self.channel, "/status clear")
            self.assertEqual(status.call_args.kwargs, {"emoji": "", "text": ""})
            self.commands.run(self.channel, "/away")
            self.assertEqual(status.call_args.kwargs, {"away": 1})
            self.commands.run(self.channel, "/back")
            self.assertEqual(status.call_args.kwargs, {"away": 0})


if __name__ == "__main__":
    unittest.main()
