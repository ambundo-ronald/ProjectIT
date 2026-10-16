"""Contract tests for phone notifications: the signed (VAPID) push request, where taps open, and dropping dead
subscriptions."""
import base64
import importlib
import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
except ImportError:  # pragma: no cover
    ec = None


def unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@unittest.skipIf(ec is None, "cryptography is not installed")
class PushTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.push = importlib.import_module("projectit.push")
        self.frappe.utils.get_url = lambda: "https://ops.example.com"
        key = ec.generate_private_key(ec.SECP256R1())
        self.private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode()
        self.public = base64.urlsafe_b64encode(key.public_key().public_bytes(serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint)).rstrip(b"=").decode()

    def test_vapid_header_is_a_valid_signed_token(self):
        self.frappe.db.get_value.return_value = "admin@techy.co.ke"
        headers = self.push.vapid_headers("https://fcm.googleapis.com/fcm/send/abc123", self.public, self.private)
        token, k = headers["Authorization"][len("vapid t="):].split(", k=")
        self.assertEqual(k, self.public)
        head, claims, signature = token.split(".")
        self.assertEqual(json.loads(unb64(head)), {"typ": "JWT", "alg": "ES256"})
        body = json.loads(unb64(claims))
        self.assertEqual((body["aud"], body["sub"]), ("https://fcm.googleapis.com", "mailto:admin@techy.co.ke"))
        raw = unb64(signature)
        self.assertEqual(len(raw), 64)
        public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64(self.public))
        public.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
            f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))  # raises if the signature is wrong
        self.assertEqual((headers["TTL"], headers["Content-Length"]), ("86400", "0"))

    def test_taps_open_the_right_screen(self):
        route = self.push._route
        self.assertEqual(route(Dict(document_type="Task", document_name="TASK-1")), "/techy-app/ops/work-orders/TASK-1")
        self.assertEqual(route(Dict(document_type="Techy Channel", document_name="CH-1")), "/techy-app/ops/chat/CH-1")
        self.assertEqual(route(Dict(document_type=None, document_name=None)), "/techy-app/home")

    def test_subscribe_needs_a_secure_push_address(self):
        with self.assertRaises(Exception):
            self.push.subscribe(json.dumps({"endpoint": "http://evil.example.com/x"}))

    def test_send_drops_gone_subscriptions(self):
        self.frappe.get_all = MagicMock(return_value=[Dict(name="S1", endpoint="https://push.example.com/a", failures=0),
            Dict(name="S2", endpoint="https://push.example.com/b", failures=0)])
        requests = ModuleType("requests")
        requests.post = MagicMock(side_effect=[SimpleNamespace(status_code=201), SimpleNamespace(status_code=410)])
        with patch.dict(sys.modules, {"requests": requests}), patch.object(self.push, "keys", return_value=(self.public, self.private)):
            self.push.send("tina@x.com")
        self.frappe.delete_doc.assert_called_once_with("Techy Push Subscription", "S2", ignore_permissions=True)
        self.assertEqual(self.frappe.db.set_value.call_args.args[:2], ("Techy Push Subscription", "S1"))

    def test_only_subscribed_people_are_pushed(self):
        self.frappe.db.exists.return_value = None
        self.push.on_notification(Dict(for_user="tom@x.com"))
        self.frappe.enqueue.assert_not_called()
        self.frappe.db.exists.return_value = "S1"
        self.push.on_notification(Dict(for_user="tina@x.com"))
        self.assertEqual(self.frappe.enqueue.call_args.kwargs["user"], "tina@x.com")


if __name__ == "__main__":
    unittest.main()
