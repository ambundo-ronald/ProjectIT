"""Slash commands in chat: type a command at the start of a message instead of opening a screen.

    /job <what's wrong>    a repair job from the channel (its project, if any); add @someone to assign them
                           (managers), and !urgent or !high for the priority
    /jobs                  my open jobs
    /remind <when> <note>  remind me: 20m, 1h, 3h, tomorrow or monday (8 am)
    /status <emoji> <text> set my status; /status clear clears it
    /away and /back        show me as away, or back
    /help                  these commands

A command is not posted as a message. Its answer is shown only to the person who typed it, except /job, which
also tells the channel that the job was created.
"""
import re

import frappe
from frappe import _

from projectit import ops

COMMAND = re.compile(r"^/([a-zA-Z]+)(?:\s+(.*))?$", re.S)
PRIORITY = re.compile(r"(?:^|\s)!(urgent|high|medium|low)\b", re.I)
EMOJI = re.compile(r"^([^\w\s@#/!\"'(),.:;?-]{1,8})\s*(.*)$", re.S)
WHEN = {"20m": "20m", "20min": "20m", "1h": "1h", "3h": "3h", "tomorrow": "tomorrow", "monday": "monday", "mon": "monday"}
HELP = [
    ("/job <what's wrong>", "create a repair job here; add @someone to assign, !urgent or !high for priority"),
    ("/jobs", "list my open jobs"),
    ("/remind <20m | 1h | 3h | tomorrow | monday> <note>", "remind me later"),
    ("/status <emoji> <text>", "set my status (/status clear to clear it)"),
    ("/away, /back", "show me as away, or back"),
    ("/help", "these commands"),
]


def parse(content):
    """(command, rest) when the message is a slash command, else None."""
    m = COMMAND.match((content or "").strip())
    return (m.group(1).lower(), (m.group(2) or "").strip()) if m else None


def run(channel, content, thread=None):
    """Run a command typed in a channel; None when the message is not a command and should be posted."""
    found = parse(content)
    if not found:
        return None
    name, rest = found
    handler = HANDLERS.get(name)
    if not handler:
        frappe.throw(_("There is no /{0} command. Type /help to see them.").format(name))
    reply = handler(channel, rest, thread)
    return {"command": name, "reply": reply}


def _help(channel, rest, thread):
    return "\n".join([_("Commands:")] + [f"{usage}  {_(text)}" for usage, text in HELP])


def _job(channel, rest, thread):
    from projectit import work_orders
    from projectit.chat import post_system_message
    members = {row.user for row in channel.members}
    people = ops.mentions(rest, members)
    flag = PRIORITY.search(rest)
    priority = flag.group(1).capitalize() if flag else "Medium"
    subject = PRIORITY.sub(" ", ops.MENTION.sub(" ", rest))
    subject = " ".join(subject.split())
    if not subject:
        frappe.throw(_("Say what's wrong: /job Pump leaking at the clinic"))
    result = work_orders.create_work_order(subject[:140], category="Corrective", priority=priority,
        assignees=people or None, project=channel.project if channel.get("project") else None)
    name = result["name"]
    post_system_message(channel.name, _("{0} created [[work-order:{1}]] from chat.").format(frappe.utils.get_fullname(), name),
        thread)
    who = _(" for {0}").format(", ".join(frappe.utils.get_fullname(u) for u in people)) if people else ""
    return _("Created [[work-order:{0}]]{1}, priority {2}.").format(name, who, priority.lower())


def _jobs(channel, rest, thread):
    from projectit import work_orders
    names = work_orders._mine()
    rows = frappe.get_all("Task", filters={"name": ["in", names or [""]], "custom_work_order": 1,
        "status": ["not in", ["Completed", "Cancelled"]]}, fields=["name", "status", "exp_end_date"],
        order_by="modified desc", limit_page_length=50) if names else []
    # Soonest due first, undated last.
    rows = sorted(rows, key=lambda r: (r.exp_end_date is None, str(r.exp_end_date or "")))[:10]
    if not rows:
        return _("You have no open jobs.")
    lines = [_("Your open jobs:")]
    for r in rows:
        due = _(" · due {0}").format(frappe.utils.format_date(r.exp_end_date, "dd MMM")) if r.exp_end_date else ""
        lines.append(f"[[work-order:{r.name}]] · {_(r.status)}{due}")
    return "\n".join(lines)


def _remind(channel, rest, thread):
    from projectit import reminders
    parts = rest.split(None, 1)
    when = WHEN.get(parts[0].lower()) if parts else None
    note = parts[1].strip() if len(parts) > 1 else ""
    if not when or not note:
        frappe.throw(_("Say when and what: /remind 1h Call the clinic. When is 20m, 1h, 3h, tomorrow or monday."))
    row = reminders.add(channel.name, None, note, when)
    return _("I'll remind you {0}: {1}").format(frappe.utils.format_datetime(row["remind_at"], "EEE d MMM HH:mm"), note)


def _status(channel, rest, thread):
    from projectit import presence
    if rest.lower() in ("", "clear", "none", "off"):
        presence.set_status(emoji="", text="")
        return _("Status cleared.")
    m = EMOJI.match(rest)
    emoji, text = (m.group(1), m.group(2)) if m else ("", rest)
    presence.set_status(emoji=emoji, text=text.strip())
    return _("Status set: {0}").format(f"{emoji} {text}".strip())


def _away(channel, rest, thread):
    from projectit import presence
    presence.set_status(away=1)
    return _("You're shown as away. Type /back when you're back.")


def _back(channel, rest, thread):
    from projectit import presence
    presence.set_status(away=0)
    return _("Welcome back. You're shown as active.")


HANDLERS = {"help": _help, "job": _job, "jobs": _jobs, "remind": _remind, "status": _status, "away": _away,
    "back": _back}
