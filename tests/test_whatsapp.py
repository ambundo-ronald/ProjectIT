"""Contract tests for WhatsApp (Cloud API): numbers, the message Meta expects, sending, delivery updates and STOP."""
import hashlib
import hmac
import importlib
import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase


class WhatsAppTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.wa = importlib.import_module("projectit.whatsapp")
        self.s = Dict(enabled=1, phone_id="123", token="tok", app_secret="secret", verify_token="vt", update_template="plant_update",
            invite_template="plant_invite", language="en", country="254", api="https://graph.example/v21.0")
        self.wa.settings = lambda: self.s

    def test_numbers(self):
        n = self.wa.normalize
        self.assertEqual(n("0712 345 678"), "254712345678")
        self.assertEqual(n("+254 712-345-678"), "254712345678")
        self.assertEqual(n("00255712345678"), "255712345678")
        self.assertIsNone(n("12345"))
        self.assertIsNone(n(""))

    def test_template_values_have_no_new_lines(self):
        self.assertEqual(self.wa._text("Visit planned\n\n on  Monday\t10:00"), "Visit planned on Monday 10:00")
        self.assertEqual(self.wa._text(""), "-")

    def test_payload_is_a_template_message(self):
        p = self.wa.payload("254712345678", "plant_update", "en", ["Amina", "Our technician is on the way."])
        self.assertEqual(p["type"], "template")
        self.assertEqual(p["template"]["name"], "plant_update")
        self.assertEqual(p["template"]["language"], {"code": "en"})
        self.assertEqual([x["text"] for x in p["template"]["components"][0]["parameters"]], ["Amina", "Our technician is on the way."])

    def test_nothing_is_sent_until_set_up(self):
        self.s.enabled = 0
        self.assertIsNone(self.wa.queue("0712345678", "plant_update", ["a", "b"]))
        self.frappe.enqueue.assert_not_called()

    def sending(self, status_code, body):
        doc = MagicMock(status="Queued", to_number="254712345678", template="plant_update", params='["Amina", "Hello"]')
        self.frappe.get_doc = MagicMock(return_value=doc)
        requests = ModuleType("requests")
        response = SimpleNamespace(status_code=status_code, content=b"x", json=lambda: body)
        requests.post = MagicMock(return_value=response)
        with patch.dict(sys.modules, {"requests": requests}):
            self.wa.send("M1")
        return doc, requests.post

    def test_send_records_the_message_id(self):
        doc, post = self.sending(200, {"messages": [{"id": "wamid.1"}]})
        self.assertEqual(post.call_args.args[0], "https://graph.example/v21.0/123/messages")
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer tok"})
        values = doc.db_set.call_args.args[0]
        self.assertEqual((values["status"], values["message_id"]), ("Sent", "wamid.1"))

    def test_send_records_meta_errors(self):
        doc, _post = self.sending(400, {"error": {"message": "Template name does not exist in the translation"}})
        values = doc.db_set.call_args.args[0]
        self.assertEqual(values["status"], "Failed")
        self.assertIn("Template name does not exist", values["error"])

    def test_delivery_updates_and_stop(self):
        self.frappe.db.get_value = MagicMock(return_value="M1")
        self.frappe.get_all = MagicMock(return_value=["amina@c.test"])
        self.wa.handle({"entry": [{"changes": [{"value": {
            "statuses": [{"id": "wamid.1", "status": "read"}],
            "messages": [{"from": "254712345678", "text": {"body": "STOP"}}]}}]}]})
        self.frappe.db.set_value.assert_any_call("Techy WhatsApp Message", "M1", {"status": "Read"})
        self.frappe.db.set_value.assert_any_call("Techy Customer User", "amina@c.test", "whatsapp_on", 0)

    def webhook_post(self, body, signature):
        self.frappe.local.request = SimpleNamespace(method="POST", get_data=lambda: body,
            headers={"X-Hub-Signature-256": signature})
        with patch.object(self.wa, "handle") as handle:
            result = self.wa.webhook()
        return result, handle

    def test_webhook_checks_metas_signature(self):
        body = json.dumps({"entry": []}).encode()
        good = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        result, handle = self.webhook_post(body, good)
        self.assertEqual(result, "ok")
        handle.assert_called_once()
        with self.assertRaises(PermissionError):
            self.webhook_post(body, "sha256=forged")

    def test_webhook_verification(self):
        self.frappe.local.request = SimpleNamespace(method="GET")
        self.frappe.local.response = {}
        self.frappe.local.form_dict = {"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "1158201444"}
        self.wa.webhook()
        self.assertEqual(self.frappe.local.response["filecontent"], "1158201444")
        self.frappe.local.form_dict = {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"}
        with self.assertRaises(PermissionError):
            self.wa.webhook()


if __name__ == "__main__":
    unittest.main()
