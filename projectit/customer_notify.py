"""Notifications for customers (the plant app) and about their logs.

To the customer's people who can see the machine (their phones, through Notification Log and Web Push):
- a visit is scheduled or moved, our technician has started work, the visit is done (report ready, rate it);
- the membranes need cleaning and we have raised a cleaning job;
- a daily reminder when the machine's log is due (operators, or the admins when it has no operator).
Replies to their requests already go to whoever raised them (work_requests).

To our managers: a machine whose customer has not logged for a few days.

Each person can switch visit news and log reminders off in the plant app (Account).
"""
import frappe
from frappe import _
from frappe.utils import cint, format_date, get_datetime, getdate, now_datetime, nowdate

from projectit import customer_accounts, ops

DOCTYPE = "Techy Customer User"
VISITS, REMINDERS = "notify_visits", "notify_reminders"
DEFAULT_REMINDER = "10:00"
DEFAULT_MISSING_DAYS = 3


def audience(equipment, kind=None, operators_first=False):
    """Enabled customer accounts that can see the machine (and want this kind of notification)."""
    customer = frappe.db.get_value("Techy Equipment", equipment, "customer")
    if not customer:
        return []
    rows = frappe.get_all(DOCTYPE, filters={"customer": customer, "enabled": 1},
        fields=["name", "user", "access", VISITS, REMINDERS])
    machines = {r.parent for r in frappe.get_all("Techy Customer Machine", filters={"parenttype": DOCTYPE,
        "parent": ["in", [r.name for r in rows] or [""]], "equipment": equipment}, fields=["parent"])}
    sees = [r for r in rows if r.access == "Customer admin" or r.name in machines]
    if operators_first:
        ops_only = [r for r in sees if r.access == "Operator"]
        sees = ops_only or sees
    return [r.user for r in sees if not kind or cint(r.get(kind) if r.get(kind) is not None else 1)]


def _tell(users, subject, doctype, name):
    """A notification from us (not from whoever happened to make the change)."""
    from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
    users = [u for u in dict.fromkeys(users) if u]
    if users:
        enqueue_create_notification(users, {"type": "Alert", "document_type": doctype, "document_name": name,
            "subject": frappe.utils.escape_html(subject), "from_user": "Administrator"})


def _machine(equipment):
    return frappe.db.get_value("Techy Equipment", equipment, "equipment_name") or equipment


VISIT_WORDS = {"Preventive": _("Service visit"), "Corrective": _("Repair visit"), "Inspection": _("Inspection"),
    "Installation": _("Installation")}


def on_task_update(doc, method=None):
    """Task on_update: visit news for the customer's people."""
    if not doc.get("custom_work_order") or not doc.get("custom_equipment") or doc.get("parent_task") or doc.get("is_template"):
        return
    try:
        before = doc.get_doc_before_save() if callable(getattr(doc, "get_doc_before_save", None)) else None
        machine = _machine(doc.custom_equipment)
        kind = VISIT_WORDS.get(doc.get("custom_work_category"), _("Visit"))
        users = audience(doc.custom_equipment, VISITS)
        if not users:
            return
        status_changed = not before or before.status != doc.status
        if status_changed and doc.status == "Working" and (not before or before.status in ("Open", "Overdue")):
            _tell(users, _("Our technician has started work on {0}.").format(machine), "Task", doc.name)
        elif status_changed and doc.status == "Completed":
            _tell(users, _("{0} done on {1}. The service report is ready: tell us how we did.").format(kind, machine),
                "Task", doc.name)
        elif doc.status in ("Open", "Overdue") and doc.get("exp_start_date") and (not before or
                str(before.get("exp_start_date") or "") != str(doc.exp_start_date)):
            when = format_date(doc.exp_start_date, "d MMM yyyy")
            text = _("{0} for {1} planned on {2}.") if not (before and before.get("exp_start_date")) else \
                _("{0} for {1} moved to {2}.")
            _tell(users, text.format(kind, machine, when), "Task", doc.name)
    except Exception:
        frappe.log_error(title=f"Techy Plant: visit notification for {doc.name} failed")


def on_the_way(doc, first_name, minutes=None):
    """The technician has set off to the customer's machine."""
    users = audience(doc.custom_equipment, VISITS)
    if users:
        when = _(" They should arrive in about {0} minutes.").format(minutes) if minutes else ""
        _tell(users, _("{0}, our technician, is on the way to {1}.{2}").format(first_name, _machine(doc.custom_equipment), when),
            "Task", doc.name)


def cleaning_raised(equipment, task):
    """We raised a membrane cleaning job: tell the customer why."""
    users = audience(equipment, VISITS)
    if users:
        _tell(users, _("The membranes of {0} need cleaning. We will plan a visit to clean them.").format(_machine(equipment)),
            "Task", task)


# Scheduled -------------------------------------------------------------------------------------------------------

def _setting(field, default):
    return frappe.db.get_single_value("Techy Ops Settings", field) or default


def _watched_machines():
    """Machines someone at the customer can log, with a log schedule."""
    customers = frappe.get_all(DOCTYPE, filters={"enabled": 1}, pluck="customer", distinct=True)
    if not customers:
        return []
    return frappe.get_all("Techy Equipment", filters={"customer": ["in", customers], "status": "Active",
        "log_schedule": ["!=", "Not expected"]}, pluck="name")


def remind_logs():
    """Every 15 minutes: after the reminder time, remind operators once a day while the machine's log is due."""
    from projectit.plant import log_status
    at = str(_setting("log_reminder_time", DEFAULT_REMINDER))[:5]
    now = now_datetime()
    if now.strftime("%H:%M") < at:
        return
    today = nowdate()
    due_for = {}  # person: machines whose log is due, so someone with many machines gets one reminder
    for eq in _watched_machines():
        key = f"techy_log_reminder:{eq}:{today}"
        if frappe.cache().get_value(key):
            continue
        if not log_status(eq)["due"]:
            continue
        frappe.cache().set_value(key, 1, expires_in_sec=36 * 3600)
        for user in audience(eq, REMINDERS, operators_first=True):
            due_for.setdefault(user, []).append(eq)
    for user, machines in due_for.items():
        names = [_machine(eq) for eq in machines]
        what = names[0] if len(names) == 1 else _("{0} machines: {1}").format(len(names), _listed(names))
        _tell([user], _("Time to log {0}: read the gauges and fill in today's log.").format(what), "Techy Equipment", machines[0])


def _listed(names, shown=3):
    if len(names) <= shown:
        return ", ".join(names)
    return _("{0} and {1} more").format(", ".join(names[:shown]), len(names) - shown)


def missing_logs():
    """Daily: tell managers about machines whose customer has not logged for a few days (once per gap, in one
    notification however many machines)."""
    from projectit.meters import _managers
    from projectit.plant import LOG
    days = cint(_setting("log_missing_days", DEFAULT_MISSING_DAYS)) or DEFAULT_MISSING_DAYS
    since = frappe.utils.add_days(getdate(nowdate()), -days)
    missing = []
    for eq in _watched_machines():
        if not audience(eq):
            continue
        last = frappe.db.get_value(LOG, {"equipment": eq}, "log_on", order_by="log_on desc")
        if last and getdate(last) >= since:
            continue
        key = f"techy_log_missing:{eq}:{last or 'never'}"
        if frappe.cache().get_value(key):
            continue
        frappe.cache().set_value(key, 1, expires_in_sec=60 * 86400)
        missing.append((eq, last))
    if not missing:
        return
    if len(missing) == 1:
        eq, last = missing[0]
        name = _machine(eq)
        text = _("No customer log for {0} for {1} days.").format(name, (getdate(nowdate()) - getdate(last)).days) if last \
            else _("The customer has never logged {0}.").format(name)
    else:
        text = _("{0} machines have had no customer log for {1} days or more: {2}.").format(len(missing), days,
            _listed([_machine(eq) for eq, _last in missing]))
    ops.notify(_managers(), text + " " + _("Remind them, or change the plant app log schedule."), "Techy Equipment", missing[0][0])


# The person's choices ------------------------------------------------------------------------------------------------

def preferences(acc):
    row = frappe.db.get_value(DOCTYPE, acc.name, [VISITS, REMINDERS], as_dict=True) or {}
    return {"visits": cint(row.get(VISITS) if row.get(VISITS) is not None else 1),
        "reminders": cint(row.get(REMINDERS) if row.get(REMINDERS) is not None else 1)}
