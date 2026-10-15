"""Contract tests for chat reactions, pins, search and typing."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class ChatExtrasTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.doc = MagicMock(is_private=0, is_direct=0, archived=0, channel_name="general",
            members=[SimpleNamespace(user="tech@example.com"), SimpleNamespace(user="boss@example.com")])
        self.doc.name, self.doc.doctype = "general", "Techy Channel"
        self.frappe.get_doc.side_effect = lambda arg, *a, **k: MagicMock() if isinstance(arg, dict) else self.doc
        self.row = Dict(name="C1", reference_doctype="Techy Channel", reference_name="general",
            comment_type="Comment", content="Pump is fixed", comment_email="boss@example.com")

    def test_only_offered_reactions(self):
        with self.assertRaises(ValidationError):
            self.chat.react("C1", "🍕")

    def test_reaction_toggles_and_is_pushed(self):
        self.frappe.db.get_value.side_effect = [self.row, None]
        self.frappe.get_all.return_value = []
        self.chat.react("C1", "👍")
        inserted = self.frappe.get_doc.call_args_list[-1].args[0]
        self.assertEqual((inserted["emoji"], inserted["user"], inserted["message"]), ("👍", "tech@example.com", "C1"))
        events = {c.args[0] for c in self.frappe.publish_realtime.call_args_list}
        self.assertEqual(events, {"techy_chat_update"})
        self.frappe.db.get_value.side_effect = [self.row, "R1"]
        self.chat.react("C1", "👍")
        self.frappe.delete_doc.assert_called_once_with("Techy Chat Reaction", "R1", ignore_permissions=True)

    def test_members_only(self):
        self.doc.members = [SimpleNamespace(user="boss@example.com")]
        self.frappe.db.get_value.side_effect = [self.row]
        with self.assertRaises(PermissionError):
            self.chat.pin("C1")

    def test_system_messages_cannot_be_pinned(self):
        self.frappe.db.get_value.side_effect = [Dict(self.row, comment_type="Info")]
        with self.assertRaises(ValidationError):
            self.chat.pin("C1")

    def test_pin_limit(self):
        self.frappe.db.get_value.side_effect = [self.row, None]
        self.frappe.db.count.return_value = 50
        with self.assertRaises(ValidationError):
            self.chat.pin("C1")

    def test_reactions_grouped_by_emoji(self):
        self.frappe.get_all.side_effect = [
            [Dict(message="C1", emoji="👍", user="a@x"), Dict(message="C1", emoji="✅", user="b@x"),
                Dict(message="C1", emoji="👍", user="b@x")],
            ["C1"]]
        reactions, pinned = self.chat._marks(["C1"])
        self.assertEqual(reactions["C1"], [{"emoji": "👍", "users": ["a@x", "b@x"]}, {"emoji": "✅", "users": ["b@x"]}])
        self.assertEqual(pinned, {"C1"})

    def test_search_needs_words_and_escapes_wildcards(self):
        with self.assertRaises(ValidationError):
            self.chat.search(" a ")
        self.frappe.get_all.side_effect = [["general"], ["general"], []]
        self.chat.search("50%_off")
        like = self.frappe.get_all.call_args.kwargs["filters"]["content"]
        self.assertEqual(like, ["like", "%50\\%\\_off%"])

    def test_search_skips_photo_tokens(self):
        rows = [Dict(name="C1", content="[[photo:abc123def0]]", reference_name="general", comment_type="Comment"),
            Dict(name="C2", content="new photo of the pump", reference_name="general", comment_type="Comment",
                comment_email="tech@example.com", comment_by="Tech", creation="x", modified="x", subject=None)]
        self.frappe.get_all.side_effect = [["general"], ["general"], rows, [], [], []]
        found = self.chat.search("photo")
        self.assertEqual([r["message"]["name"] for r in found], ["C2"])

    def test_typing_goes_to_the_others(self):
        self.chat.typing("general")
        users = [c.kwargs["user"] for c in self.frappe.publish_realtime.call_args_list]
        self.assertEqual(users, ["boss@example.com"])


if __name__ == "__main__":
    unittest.main()
