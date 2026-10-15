"""Reminders on chat messages ("remind me about this in an hour").

A reminder is a Techy Chat Reminder for one person. A job runs every minute and, for each reminder that is due,
adds a notification (the bell in Desk and Techy) and pops it up in any open Techy app.
"""
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from projectit import ops

DOCTYPE = "Techy Chat Reminder"
MAX_PENDING = 50
MORNING = 8  # o'clock for "tomorrow" and "next Monday"
OPTIONS = ("20m", "1h", "3h", "tomorrow", "monday")


def remind_at(when, now=None):
    now = get_datetime(now or now_datetime())
    if when == "20m":
        return add_to_date(now, minutes=20)
    if when == "1h":
        return add_to_date(now, hours=1)
    if when == "3h":
        return add_to_date(now, hours=3)
    morning = now.replace(hour=MORNING, minute=0, second=0, microsecond=0)
    if when == "tomorrow":
        return morning + timedelta(days=1)
    if when == "monday":
        return morning + timedelta(days=(7 - now.weekday()) or 7)
    frappe.throw(_("Choose when to be reminded."))


def _note(content):
    from projectit import chat, links
    text = links.readable(ops.plain(chat._split(content)[0])).strip()
    return (text[:137] + "…") if len(text) > 140 else (text or _("A photo"))


@frappe.whitelist(methods=["POST"])
def remind(message, when):
    """Remind me about a message I can read."""
    from projectit import chat
    ops.system_user()
    if when not in OPTIONS:
        frappe.throw(_("Choose when to be reminded."))
    row = frappe.db.get_value("Comment", message, ["name", "reference_doctype", "reference_name", "comment_type",
        "content"], as_dict=True)
    if not row or row.reference_doctype != "Techy Channel" or row.comment_type != "Comment":
        frappe.throw(_("Message not found."))
    chat._channel(row.reference_name, member=False)
    me = frappe.session.user
    if frappe.db.count(DOCTYPE, {"user": me, "sent": 0}) >= MAX_PENDING:
        frappe.throw(_("You have {0} reminders waiting. Cancel some first.").format(MAX_PENDING))
    doc = frappe.get_doc({"doctype": DOCTYPE, "user": me, "channel": row.reference_name, "message": row.name,
        "remind_at": remind_at(when), "note": _note(row.content)}).insert(ignore_permissions=True)
    return {"name": doc.name, "remind_at": doc.remind_at}


@frappe.whitelist()
def my_reminders():
    """My reminders still to come, soonest first."""
    from projectit import chat
    ops.system_user()
    rows = frappe.get_all(DOCTYPE, filters={"user": frappe.session.user, "sent": 0},
        fields=["name", "remind_at", "channel", "message", "note"], order_by="remind_at asc", limit_page_length=MAX_PENDING)
    titles = {}
    for name in {r.channel for r in rows}:
        doc = frappe.get_doc("Techy Channel", name)
        titles[name] = {"title": chat._title(doc), "is_direct": doc.is_direct}
    return [{**r, **titles.get(r.channel, {})} for r in rows]


@frappe.whitelist(methods=["POST"])
def cancel(name):
    ops.system_user()
    if frappe.db.get_value(DOCTYPE, name, "user") != frappe.session.user:
        frappe.throw(_("Reminder not found."))
    frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)
    return {"name": name}


def send_due():
    """Scheduler (every minute): notify everyone whose reminder time has come."""
    for row in frappe.get_all(DOCTYPE, filters={"sent": 0, "remind_at": ["<=", now_datetime()]},
            fields=["name", "user", "channel", "message", "note"], order_by="remind_at asc", limit_page_length=200):
        frappe.db.set_value(DOCTYPE, row.name, "sent", 1, update_modified=False)
        frappe.get_doc({"doctype": "Notification Log", "for_user": row.user, "type": "Alert",
            "document_type": "Techy Channel", "document_name": row.channel, "from_user": row.user,
            "subject": frappe.utils.escape_html(_("Reminder: {0}").format(row.note))}).insert(ignore_permissions=True)
        frappe.publish_realtime("techy_reminder", {"name": row.name, "channel": row.channel, "message": row.message,
            "note": row.note}, user=row.user, after_commit=True)
    frappe.db.commit()
