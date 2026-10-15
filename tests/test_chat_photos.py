"""Contract tests for photos in chat and turning a chat message into a work order."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class ChatPhotoTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.doc = MagicMock(is_private=0, is_direct=0, archived=0, channel_name="general",
            members=[SimpleNamespace(user="tech@example.com"), SimpleNamespace(user="boss@example.com")])
        self.doc.name, self.doc.doctype = "general", "Techy Channel"
        self.inserted = []

        def get_doc(arg, *args, **kwargs):
            if not isinstance(arg, dict):
                return self.doc
            self.inserted.append(arg)
            made = MagicMock(**{k: v for k, v in arg.items() if k != "name"})
            made.name, made.creation = "C1", "2026-10-11 09:00:00"
            made.insert.return_value = made
            return made
        self.frappe.get_doc.side_effect = get_doc
        self.frappe.db.get_value.return_value = "ROW-1"
        saved = iter(["f1a2b3c4d5", "e6f7a8b9c0"])
        self.ops.save_photo = MagicMock(side_effect=lambda *a, **k: SimpleNamespace(name=next(saved),
            file_url="/private/files/chat-x.jpg"))
        self.chat.ops = self.ops

    def test_photos_only_message(self):
        message = self.chat.post_message("general", "", photos=["AAAA", "BBBB"])
        self.assertEqual(self.inserted[-1]["content"], "[[photo:f1a2b3c4d5]]\n[[photo:e6f7a8b9c0]]")
        self.assertEqual(message["content"], "")
        self.assertEqual([p["name"] for p in message["photos"]], ["f1a2b3c4d5", "e6f7a8b9c0"])
        self.assertTrue(all(c.kwargs.get("ignore_permissions") for c in self.ops.save_photo.call_args_list))

    def test_text_with_a_photo_and_no_typed_tokens(self):
        message = self.chat.post_message("general", "Leak at the pump [[photo:stolenfile1]]", photos='["AAAA"]')
        self.assertEqual(self.inserted[-1]["content"], "Leak at the pump\n[[photo:f1a2b3c4d5]]")
        self.assertEqual(message["content"], "Leak at the pump")

    def test_limits(self):
        with self.assertRaises(ValidationError):
            self.chat.post_message("general", "", photos=[])
        with self.assertRaises(ValidationError):
            self.chat.post_message("general", "", photos=["A"] * 7)

    def test_readers_only_get_photos_of_this_channel(self):
        self.frappe.get_all.return_value = [["f1a2b3c4d5", "/private/files/a.jpg"]]
        row = Dict(name="C2", content="Look\n[[photo:f1a2b3c4d5]]\n[[photo:otherchan99]]", comment_type="Comment",
            comment_email="tech@example.com", comment_by="Tech", creation="x", modified="x", subject=None,
            reference_name="general")
        message = self.chat._message(row, marks=self.chat.NO_MARKS)
        self.assertEqual(message["photos"], [{"name": "f1a2b3c4d5", "url": "/private/files/a.jpg"}])
        filters = self.frappe.get_all.call_args.kwargs["filters"]
        self.assertEqual((filters["attached_to_doctype"], filters["attached_to_name"]), ("Techy Channel", "general"))

    def test_editing_keeps_the_photos(self):
        comment = MagicMock(reference_doctype="Techy Channel", reference_name="general", comment_type="Comment",
            comment_email="tech@example.com", content="Old\n[[photo:f1a2b3c4d5]]")
        self.frappe.get_doc.side_effect = lambda doctype, name=None, **k: comment if doctype == "Comment" else self.doc
        self.chat.edit_message("C1", "New text")
        self.assertEqual(comment.content, "New text\n[[photo:f1a2b3c4d5]]")

    def test_only_channel_messages_become_jobs(self):
        self.frappe.db.get_value.return_value = Dict(name="C9", reference_doctype="Task", comment_type="Comment")
        with self.assertRaises(ValidationError):
            self.chat.message_source("C9")
        self.frappe.db.get_value.return_value = Dict(name="C9", reference_doctype="Techy Channel",
            reference_name="general", comment_type="Comment")
        self.doc.is_private = 1
        self.doc.members = [SimpleNamespace(user="boss@example.com")]
        with self.assertRaises(PermissionError):
            self.chat.message_source("C9")  # a private channel the reader is not in


if __name__ == "__main__":
    unittest.main()
