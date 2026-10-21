"""WhatsApp for the customer app, through Meta's WhatsApp Cloud API (the WhatsApp Business Platform).

Customers who turn WhatsApp on (plant app, Account; or staff with their agreement when inviting them) get:
- their invitation link (the invitation template);
- every plant app notification they already get on the phone: visits, technician on the way, reports, cleaning,
  request replies, log reminders (the update template, with the notification's text).

WhatsApp only lets a business start a conversation with a template Meta has approved, so everything goes out as one
of those two templates (docs/whatsapp.md has their text). Messages are sent in the background and kept as Techy
WhatsApp Message, with the delivery status Meta reports back to the webhook. Replying STOP turns WhatsApp off for
that number. Nothing is sent until the settings are filled in and Send WhatsApp Messages is ticked.
"""
import hashlib
import hmac
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from projectit import ops

SETTINGS = "Techy Ops Settings"
MESSAGE = "Techy WhatsApp Message"
ACCOUNT = "Techy Customer User"
STOP_WORDS = {"stop", "unsubscribe", "stop all", "acha"}
STATUSES = {"sent": "Sent", "delivered": "Delivered", "read": "Read", "failed": "Failed"}


def settings():
    from frappe.utils.password import get_decrypted_password
    doc = frappe.get_cached_doc(SETTINGS)
    return frappe._dict(enabled=cint(doc.get("whatsapp_enabled")), phone_id=(doc.get("whatsapp_phone_number_id") or "").strip(),
        token=get_decrypted_password(SETTINGS, SETTINGS, "whatsapp_token", raise_exception=False) or "",
        app_secret=get_decrypted_password(SETTINGS, SETTINGS, "whatsapp_app_secret", raise_exception=False) or "",
        verify_token=doc.get("whatsapp_verify_token") or "",
        # not "update": that is a dict method, and frappe._dict would return it instead of the value
        update_template=doc.get("whatsapp_template_update") or "plant_update",
        invite_template=doc.get("whatsapp_template_invite") or "plant_invite", language=doc.get("whatsapp_language") or "en",
        country=re.sub(r"\D", "", doc.get("whatsapp_country_code") or "254"),
        api=(doc.get("whatsapp_api_base") or "https://graph.facebook.com/v21.0").rstrip("/"))


def available():
    """WhatsApp is set up: customers can be offered it."""
    s = settings()
    return bool(s.enabled and s.phone_id and s.token)


def normalize(number, country=None):
    """A number as WhatsApp wants it (country code and digits, no +), or None when it cannot be one."""
    digits = re.sub(r"\D", "", str(number or ""))
    if not digits:
        return None
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = (country or settings().country) + digits[1:]
    return digits if 8 <= len(digits) <= 15 else None


def _text(value, limit=900):
    """A template value: WhatsApp refuses new lines, tabs and long runs of spaces in them."""
    text = re.sub(r"\s+", " ", ops.plain(str(value or ""))).strip()
    return text[:limit] or "-"


def queue(number, template, values, user=None, reference=None):
    """Keep the message and send it in the background. Returns the record's name (None when WhatsApp is off)."""
    if not available():
        return None
    to = normalize(number)
    if not to:
        return None
    values = [_text(v) for v in values]
    doc = frappe.get_doc({"doctype": MESSAGE, "to_number": to, "user": user, "template": template, "status": "Queued",
        "params": json.dumps(values), "body": " · ".join(values), "reference_doctype": (reference or (None, None))[0],
        "reference_name": (reference or (None, None))[1]}).insert(ignore_permissions=True)
    frappe.enqueue("projectit.whatsapp.send", queue="short", enqueue_after_commit=True, name=doc.name)
    return doc.name


def payload(to, template, language, values):
    return {"messaging_product": "whatsapp", "to": to, "type": "template", "template": {"name": template,
        "language": {"code": language}, "components": [{"type": "body", "parameters": [{"type": "text", "text": v}
            for v in values]}]}}


def send(name):
    """Background job: send one message through the Cloud API and record what happened."""
    import requests
    doc = frappe.get_doc(MESSAGE, name)
    if doc.status != "Queued":
        return
    s = settings()
    try:
        response = requests.post(f"{s.api}/{s.phone_id}/messages", json=payload(doc.to_number, doc.template, s.language,
            json.loads(doc.params or "[]")), headers={"Authorization": f"Bearer {s.token}"}, timeout=15)
        data = response.json() if response.content else {}
    except Exception as e:
        doc.db_set({"status": "Failed", "error": str(e)[:500]})
        return
    if response.status_code >= 400 or not data.get("messages"):
        error = (data.get("error") or {}).get("message") or f"HTTP {response.status_code}"
        doc.db_set({"status": "Failed", "error": error[:500]})
        return
    doc.db_set({"status": "Sent", "message_id": data["messages"][0].get("id"), "sent_on": now_datetime(), "error": None})


# What goes out ---------------------------------------------------------------------------------------------------------

def _account(user):
    return frappe.db.get_value(ACCOUNT, {"user": user, "enabled": 1, "whatsapp_on": 1}, ["name", "full_name",
        "whatsapp_number"], as_dict=True)


def on_notification(doc, method=None):
    """Notification Log after_insert: the customer's notification on WhatsApp too, when they turned it on."""
    if not doc.for_user or not available():
        return
    acc = _account(doc.for_user)
    if not acc or not acc.whatsapp_number:
        return
    try:
        first = (acc.full_name or "").split(" ")[0] or _("there")
        queue(acc.whatsapp_number, settings().update_template, [first, doc.subject], doc.for_user, (doc.document_type, doc.document_name))
    except Exception:
        frappe.log_error(title="Techy Plant: WhatsApp notification failed")


def invite(user, full_name, link, customer_name):
    """The invitation link on WhatsApp (the person agreed to WhatsApp). True when it was queued."""
    acc = _account(user)
    if not acc or not acc.whatsapp_number:
        return False
    company = frappe.db.get_single_value("Global Defaults", "default_company") or ""
    return bool(queue(acc.whatsapp_number, settings().invite_template, [(full_name or "").split(" ")[0] or _("there"), company,
        customer_name or "", link], user, (ACCOUNT, acc.name)))


def set_number(account_name, number, on, agreed=True):
    """Turn WhatsApp on (with a number they agreed to) or off for an account."""
    values = {"whatsapp_on": 1 if on else 0}
    if on:
        to = normalize(number)
        if not to:
            frappe.throw(_("Enter a WhatsApp number with its country code, e.g. +254 712 345 678."))
        values["whatsapp_number"] = "+" + to
        if agreed:
            values["whatsapp_opt_in_on"] = now_datetime()
    frappe.db.set_value(ACCOUNT, account_name, values)


# Meta tells us what happened ---------------------------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def webhook():
    """Meta's webhook: GET to check it is ours, POST with delivery updates and replies."""
    s = settings()
    request = frappe.local.request
    if request.method == "GET":
        args = frappe.local.form_dict
        if args.get("hub.mode") != "subscribe" or not s.verify_token or not hmac.compare_digest(
                str(args.get("hub.verify_token") or ""), s.verify_token):
            frappe.throw(_("Not permitted."), frappe.PermissionError)
        frappe.local.response.update({"type": "download", "filename": "challenge.txt", "content_type": "text/plain",
            "display_content_as": "inline", "filecontent": str(args.get("hub.challenge") or "")})
        return
    body = request.get_data() or b""
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(s.app_secret.encode(), body, hashlib.sha256).hexdigest() if s.app_secret else None
    if not expected or not hmac.compare_digest(signature, expected):
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    handle(json.loads(body or b"{}"))
    return "ok"


def handle(data):
    """Delivery statuses update the messages; STOP turns WhatsApp off for that number."""
    for entry in data.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for st in value.get("statuses") or []:
                name = frappe.db.get_value(MESSAGE, {"message_id": st.get("id")}, "name")
                status = STATUSES.get(st.get("status"))
                if name and status:
                    error = "; ".join(e.get("title") or e.get("message") or "" for e in st.get("errors") or []) or None
                    frappe.db.set_value(MESSAGE, name, {"status": status, **({"error": error[:500]} if error else {})})
            for msg in value.get("messages") or []:
                text = ((msg.get("text") or {}).get("body") or (msg.get("button") or {}).get("text") or "").strip().lower()
                if text in STOP_WORDS:
                    number = normalize(msg.get("from"))
                    for acc in frappe.get_all(ACCOUNT, filters={"whatsapp_number": ["like", f"%{number}"]}, pluck="name"):
                        frappe.db.set_value(ACCOUNT, acc, "whatsapp_on", 0)


# Staff ------------------------------------------------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def test(number):
    """Managers: send the update template to a number, to check the set-up."""
    ops.system_user()
    ops.require_manager()
    if not available():
        frappe.throw(_("Fill in the WhatsApp settings and tick Send WhatsApp Messages first."))
    name = queue(number, settings().update_template, [_("there"), _("This is a test message from the plant app.")], frappe.session.user)
    if not name:
        frappe.throw(_("Enter a WhatsApp number with its country code."))
    return {"message": name}


def ensure_verify_token():
    """after_migrate: the token Meta's webhook set-up asks for, made once."""
    if frappe.db.exists("DocType", SETTINGS) and not frappe.db.get_single_value(SETTINGS, "whatsapp_verify_token"):
        frappe.db.set_single_value(SETTINGS, "whatsapp_verify_token", frappe.generate_hash(length=24))
