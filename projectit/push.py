"""Phone notifications (Web Push): alerts on the phone or computer even when Techy Ops is closed.

Turning notifications on in the app (the name menu) subscribes that browser with the site's own key. Whenever
someone gets a notification in Frappe (jobs assigned, mentions, reminders, response-time warnings, ratings...),
each of their subscribed browsers is sent an empty push signed with the key (VAPID). The app's service worker
then asks the site what is new and shows it, so no message text passes through the browser's push service.

The site's key pair is made the first time it is needed and kept in Techy Ops Settings (the private half as a
password field). Subscriptions the push service reports gone are removed. On iPhones, web push works only for
the app added to the home screen (iOS 16.4 or later).
"""
import base64
import json
import time
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from projectit import ops

DOCTYPE = "Techy Push Subscription"
SETTINGS = "Techy Ops Settings"
TTL = 24 * 3600
MAX_SHOWN = 3
FRESH_MINUTES = 30


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def keys():
    """(public key for browsers, private key) for the site, made once."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    public = frappe.db.get_single_value(SETTINGS, "vapid_public_key")
    private = None
    if public:
        from frappe.utils.password import get_decrypted_password
        private = get_decrypted_password(SETTINGS, SETTINGS, "vapid_private_key", raise_exception=False)
    if not (public and private):
        key = ec.generate_private_key(ec.SECP256R1())
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode()
        public = _b64(key.public_key().public_bytes(serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint))
        doc = frappe.get_single(SETTINGS)
        doc.vapid_public_key = public
        doc.vapid_private_key = private
        doc.flags.ignore_permissions = True
        doc.save()
    return public, private


def _contact():
    email = frappe.db.get_value("User", "Administrator", "email")
    return f"mailto:{email}" if email and "@" in email and not email.endswith("@example.com") else frappe.utils.get_url()


def vapid_headers(endpoint, public, private):
    """The Authorization header that proves the push comes from this site (RFC 8292)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    url = urlparse(endpoint)
    header = _b64(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({"aud": f"{url.scheme}://{url.netloc}", "exp": int(time.time()) + 12 * 3600,
        "sub": _contact()}, separators=(",", ":")).encode())
    key = serialization.load_pem_private_key(private.encode(), password=None)
    r, s = decode_dss_signature(key.sign(f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256())))
    signature = _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return {"Authorization": f"vapid t={header}.{claims}.{signature}, k={public}", "TTL": str(TTL), "Urgency": "high",
        "Content-Length": "0"}


# The app -------------------------------------------------------------------------------------------------------

@frappe.whitelist()
def public_key():
    _member()
    return {"key": keys()[0]}


@frappe.whitelist(methods=["POST"])
def subscribe(subscription, device=None):
    """Remember this browser for my notifications."""
    _member()
    sub = frappe.parse_json(subscription) if isinstance(subscription, str) else (subscription or {})
    endpoint = str(sub.get("endpoint") or "")
    if not endpoint.startswith("https://") or len(endpoint) > 1000:
        frappe.throw(_("This browser gave an invalid push address."))
    existing = frappe.db.get_value(DOCTYPE, {"endpoint": endpoint}, "name")
    values = {"user": frappe.session.user, "device": ops.text(device, "the device", 140, required=False) or None,
        "failures": 0}
    if existing:
        frappe.db.set_value(DOCTYPE, existing, values)
    else:
        frappe.get_doc({"doctype": DOCTYPE, "endpoint": endpoint, **values}).insert(ignore_permissions=True)
    return {"subscribed": True}


@frappe.whitelist(methods=["POST"])
def unsubscribe(endpoint):
    _member()
    for name in frappe.get_all(DOCTYPE, filters={"endpoint": str(endpoint or ""), "user": frappe.session.user}, pluck="name"):
        frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)
    return {"subscribed": False}


def _member():
    """Staff, or a customer's person using the plant app."""
    ops.login()
    from projectit import customer_accounts
    if not customer_accounts.account():
        ops.system_user()


# Customers' notifications open the plant app.
PLANT_ROUTES = {"Task": "/techy-app/plant/service", "Issue": "/techy-app/plant/service",
    "Techy Plant Log": "/techy-app/plant/log", "Techy Equipment": "/techy-app/plant"}


def _route(row, customer=False):
    """Where tapping a notification opens."""
    name = row.document_name or ""
    if customer:
        return PLANT_ROUTES.get(row.document_type, "/techy-app/plant")
    return {"Task": f"/techy-app/ops/work-orders/{name}", "Techy Channel": f"/techy-app/ops/chat/{name}",
        "Issue": "/techy-app/ops/requests", "Techy Investigation": f"/techy-app/ops/investigations/{name}",
        "Techy Equipment": f"/techy-app/ops/equipment/{name}", "Techy Service Contract": f"/techy-app/ops/contracts/{name}",
        "Techy Meter": "/techy-app/ops/equipment"}.get(row.document_type, "/techy-app/home")


@frappe.whitelist()
def pending():
    """For the service worker when a push arrives: my newest unread notifications. The worker tags each with its
    name, so one already on screen is replaced quietly rather than shown twice."""
    _member()
    since = frappe.utils.add_to_date(now_datetime(), minutes=-FRESH_MINUTES)
    rows = frappe.get_all("Notification Log", filters={"for_user": frappe.session.user, "read": 0, "creation": [">", since]},
        fields=["name", "subject", "document_type", "document_name"], order_by="creation desc", limit_page_length=MAX_SHOWN)
    from projectit import customer_accounts
    customer = bool(customer_accounts.account())
    title = (frappe.db.get_single_value("Global Defaults", "default_company") or _("Your plant")) if customer else _("Techy Ops")
    return [{"tag": r.name, "title": title, "body": ops.plain(r.subject)[:200], "url": _route(r, customer)} for r in rows]


@frappe.whitelist(methods=["POST"])
def test():
    """Send myself a test notification."""
    _member()
    if not frappe.db.exists(DOCTYPE, {"user": frappe.session.user}):
        frappe.throw(_("Turn on notifications on this device first."))
    frappe.get_doc({"doctype": "Notification Log", "for_user": frappe.session.user, "type": "Alert",
        "subject": _("Test notification: phone notifications are working."), "from_user": frappe.session.user}).insert(
        ignore_permissions=True)
    return {"sent": True}


# Sending -------------------------------------------------------------------------------------------------------

def on_notification(doc, method=None):
    """Notification Log after_insert: wake the person's subscribed browsers once the notification is saved."""
    if doc.for_user and frappe.db.exists(DOCTYPE, {"user": doc.for_user}):
        frappe.enqueue("projectit.push.send", user=doc.for_user, enqueue_after_commit=True, queue="short")


def send(user):
    """Push to each of the user's browsers; drop the ones the push service no longer knows."""
    import requests
    public, private = keys()
    for row in frappe.get_all(DOCTYPE, filters={"user": user}, fields=["name", "endpoint", "failures"]):
        try:
            response = requests.post(row.endpoint, headers=vapid_headers(row.endpoint, public, private), timeout=10)
        except Exception:
            frappe.db.set_value(DOCTYPE, row.name, "failures", cint(row.failures) + 1, update_modified=False)
            continue
        if response.status_code in (404, 410) or (response.status_code >= 400 and cint(row.failures) >= 5):
            frappe.delete_doc(DOCTYPE, row.name, ignore_permissions=True)
        elif response.status_code >= 400:
            frappe.db.set_value(DOCTYPE, row.name, "failures", cint(row.failures) + 1, update_modified=False)
        else:
            frappe.db.set_value(DOCTYPE, row.name, {"failures": 0, "last_sent": now_datetime()}, update_modified=False)
