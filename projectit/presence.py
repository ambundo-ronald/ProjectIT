"""Slack-style status and presence for Techy apps.

Status: each person may set an emoji and a short text ("🚐 On site at Bahari") that clears itself after a
chosen time, and may mark themselves away. It is a Techy User Status record, one per person.
Presence: every open Techy app calls heartbeat() about once a minute while it is on screen; the time is kept
in Redis. Someone is online when seen in the last two and a half minutes and not marked away.
"""
import time

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from projectit import ops

DOCTYPE = "Techy User Status"
KEY = "techy_presence"
ONLINE_SECONDS = 150
CLEAR_AFTER = {"30m": 30, "1h": 60, "4h": 240}  # minutes; also "today" and "never"
MAX_WATCHED = 200


def _statuses(users):
    """{user: {emoji, text, away}} for statuses that have not expired."""
    users = list(dict.fromkeys(u for u in users or [] if u))
    if not users:
        return {}
    now = now_datetime()
    result = {}
    for row in frappe.get_all(DOCTYPE, filters={"user": ["in", users]},
            fields=["user", "emoji", "status_text", "clear_at", "away"], limit_page_length=0):
        live = not row.clear_at or get_datetime(row.clear_at) > now
        result[row.user] = {"emoji": row.emoji if live else None, "text": row.status_text if live else None,
            "away": bool(row.away), "clear_at": row.clear_at if live else None}
    return result


def presence(users):
    """{user: {online, away, emoji, text}} for these people."""
    users = list(dict.fromkeys(u for u in users or [] if u))[:MAX_WATCHED]
    statuses = _statuses(users)
    now = time.time()
    result = {}
    for user in users:
        seen = frappe.cache.hget(KEY, user)
        status = statuses.get(user, {})
        away = status.get("away", False)
        result[user] = {"online": bool(seen) and now - float(seen) < ONLINE_SECONDS and not away, "away": away,
            "emoji": status.get("emoji"), "text": status.get("text"), "clear_at": status.get("clear_at")}
    return result


@frappe.whitelist(methods=["POST"])
def heartbeat(users=None):
    """I am here; and how are these people doing (the members on my screen)."""
    ops.system_user()
    frappe.cache.hset(KEY, frappe.session.user, time.time())
    users = frappe.parse_json(users) if isinstance(users, str) else (users or [])
    if not isinstance(users, list):
        users = []
    return presence([str(u) for u in users[:MAX_WATCHED]] + [frappe.session.user])


def _clear_at(value):
    if value in (None, "", "never"):
        return None
    if value == "today":
        return get_datetime(now_datetime().strftime("%Y-%m-%d 23:59:59"))
    if value not in CLEAR_AFTER:
        frappe.throw(_("Choose when the status clears."))
    return add_to_date(now_datetime(), minutes=CLEAR_AFTER[value])


@frappe.whitelist(methods=["POST"])
def set_status(emoji=None, text=None, clear_after=None, away=None):
    """Set or clear my status (empty emoji and text clear it). With only `away`, just that changes."""
    ops.system_user()
    me = frappe.session.user
    if emoji is None and text is None:
        if away is None:
            frappe.throw(_("Nothing to change."))
        values = {"away": cint(away)}
    else:
        emoji = str(emoji or "").strip()
        text = ops.text(text, "a status", 100, required=False)
        if len(emoji) > 8:
            frappe.throw(_("Choose a single emoji."))
        values = {"emoji": emoji or None, "status_text": text or None,
            "clear_at": _clear_at(clear_after) if (emoji or text) else None}
        if away is not None:
            values["away"] = cint(away)
    if frappe.db.exists(DOCTYPE, me):
        frappe.db.set_value(DOCTYPE, me, values)
    else:
        frappe.get_doc({"doctype": DOCTYPE, "user": me, **values}).insert(ignore_permissions=True)
    return presence([me])[me]
