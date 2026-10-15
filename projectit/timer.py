"""Job timer: technicians start and stop a clock on a work order, MaintainX style.

Each stretch of work is a Techy Time Log (who, from, to, hours). A person runs one clock at a time, so
starting on another job stops the first one. Putting a job on hold, completing or cancelling it stops
every clock on it. Forgotten clocks are fixed by editing the entry, and missed time is added by hand.

The job's labour hours (what is invoiced) follow the logged total until someone types other hours, e.g.
a manager billing a minimum call-out; typed hours are then kept and the card offers the logged total.
The reports use the logged time per person.
"""
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, now_datetime, time_diff_in_seconds

from projectit import ops

DOCTYPE = "Techy Time Log"
FIELDS = ["name", "work_order", "user", "started_at", "ended_at", "hours", "source"]
MAX_MINUTES = 24 * 60  # one entry; longer means the clock was left running
CLOSED = ("Completed", "Cancelled")


def _hours(start, end):
    return round(max(0, time_diff_in_seconds(end, start)) / 3600, 2)


def _running(user=None, work_order=None):
    filters = {"ended_at": ["is", "not set"]}
    if user:
        filters["user"] = user
    if work_order:
        filters["work_order"] = work_order
    return frappe.get_all(DOCTYPE, filters=filters, fields=FIELDS, order_by="started_at asc")


def logged_total(work_order):
    """Hours in the job's finished entries."""
    return round(flt(frappe.db.sql(f"""SELECT SUM(hours) FROM `tab{DOCTYPE}` WHERE work_order = %s
        AND ended_at IS NOT NULL""", work_order)[0][0]), 2)


def hours_by_person(work_orders):
    """{work order: {user: hours}} for the finished entries on these jobs."""
    result = defaultdict(lambda: defaultdict(float))
    names = list(work_orders or [])
    if names:
        for row in frappe.get_all(DOCTYPE, filters={"work_order": ["in", names], "ended_at": ["is", "set"]},
                fields=["work_order", "user", "hours"], limit_page_length=0):
            result[row.work_order][row.user] += flt(row.hours)
    return result


def _sync(work_order, before):
    """Keep the job's labour hours on the logged total, unless someone typed other hours or it is invoiced."""
    hours, invoice = frappe.db.get_value("Task", work_order, ["custom_labour_hours", "custom_sales_invoice"])
    after = logged_total(work_order)
    if invoice or round(flt(hours), 2) not in (0, round(flt(before), 2)) or after == round(flt(hours), 2):
        return None
    # Billing field only, and without touching `modified` so open screens can still change the status.
    frappe.db.set_value("Task", work_order, "custom_labour_hours", after, update_modified=False)
    return after


def _close(entry, ended_at=None):
    ended_at = ended_at or now_datetime()
    frappe.db.set_value(DOCTYPE, entry.name, {"ended_at": ended_at, "hours": _hours(entry.started_at, ended_at)})


def _people(work_order):
    from projectit.work_orders import _assignees
    return set(_assignees([work_order])[work_order]) | {frappe.db.get_value("Task", work_order, "owner")}


def _job(name):
    from projectit.work_orders import _work_order
    doc = _work_order(name, write=True)
    if doc.get("custom_sales_invoice"):
        frappe.throw(_("This job is already invoiced ({0}).").format(doc.custom_sales_invoice))
    return doc


def _finished(work_order, changes):
    """After entries change: update the labour hours, tell open screens, return the job page."""
    from projectit import work_orders
    for job, before in changes.items():
        _sync(job, before)
        ops.push(_people(job) | {frappe.session.user}, "techy_work_order", {"name": job})
    return work_orders.get_work_order(work_order)


@frappe.whitelist(methods=["POST"])
def start(work_order):
    """Start my clock on this job (stopping it on any other job) and move the job to in progress."""
    doc = _job(work_order)
    if doc.status in CLOSED:
        frappe.throw(_("Reopen the job before starting the timer."))
    me = frappe.session.user
    changes = {}
    for entry in _running(user=me):
        if entry.work_order == doc.name:
            return _finished(doc.name, changes)
        changes[entry.work_order] = logged_total(entry.work_order)
        _close(entry)
    frappe.get_doc({"doctype": DOCTYPE, "work_order": doc.name, "user": me, "started_at": now_datetime(),
        "source": "Timer"}).insert(ignore_permissions=True)
    from projectit.work_orders import _workflow
    if doc.status in ("Open", "Overdue", "Pending Review") and not _workflow():
        doc.status = "Working"
        doc.save()
    return _finished(doc.name, changes)


@frappe.whitelist(methods=["POST"])
def stop(work_order, entry=None):
    """Stop my clock on this job; managers may stop someone else's (`entry`)."""
    doc = _job(work_order)
    running = _running(work_order=doc.name)
    if entry:
        running = [r for r in running if r.name == entry]
        if running and running[0].user != frappe.session.user and not ops.manager():
            frappe.throw(_("Only managers can stop someone else's timer."), frappe.PermissionError)
    else:
        running = [r for r in running if r.user == frappe.session.user]
    if not running:
        frappe.throw(_("The timer is not running."))
    before = logged_total(doc.name)
    for row in running:
        _close(row)
    return _finished(doc.name, {doc.name: before})


def stop_all(doc):
    """The job went on hold, was completed or cancelled: stop every clock on it (Task on_update)."""
    running = _running(work_order=doc.name)
    if not running:
        return
    before = logged_total(doc.name)
    for row in running:
        _close(row)
    hours = _sync(doc.name, before)
    if hours is not None:
        doc.custom_labour_hours = hours


def _minutes(value):
    minutes = cint(value)
    if minutes < 1 or minutes > MAX_MINUTES:
        frappe.throw(_("Enter between 1 minute and 24 hours."))
    return minutes


@frappe.whitelist(methods=["POST"])
def add_time(work_order, minutes, user=None):
    """Record time worked without the clock (forgot to start it). Managers may record it for others."""
    doc = _job(work_order)
    minutes = _minutes(minutes)
    user = user or frappe.session.user
    if user != frappe.session.user:
        if not ops.manager():
            frappe.throw(_("Only managers can record time for someone else."), frappe.PermissionError)
        if not ops.active_users([user]):
            frappe.throw(_("Choose an active team member."))
    before = logged_total(doc.name)
    ended_at = now_datetime()
    frappe.get_doc({"doctype": DOCTYPE, "work_order": doc.name, "user": user, "source": "Manual",
        "started_at": add_to_date(ended_at, minutes=-minutes), "ended_at": ended_at,
        "hours": round(minutes / 60, 2)}).insert(ignore_permissions=True)
    return _finished(doc.name, {doc.name: before})


def _entry(name):
    row = frappe.db.get_value(DOCTYPE, name, FIELDS, as_dict=True)
    if not row:
        frappe.throw(_("Time entry not found."))
    doc = _job(row.work_order)
    if row.user != frappe.session.user and not ops.manager():
        frappe.throw(_("You can only change your own time."), frappe.PermissionError)
    return row, doc


@frappe.whitelist(methods=["POST"])
def update_entry(name, minutes):
    """Correct how long a finished entry lasted (a clock left running overnight, say)."""
    row, doc = _entry(name)
    if not row.ended_at:
        frappe.throw(_("Stop the timer before changing this entry."))
    minutes = _minutes(minutes)
    before = logged_total(doc.name)
    frappe.db.set_value(DOCTYPE, row.name, {"ended_at": add_to_date(row.started_at, minutes=minutes),
        "hours": round(minutes / 60, 2)})
    return _finished(doc.name, {doc.name: before})


@frappe.whitelist(methods=["POST"])
def delete_entry(name):
    row, doc = _entry(name)
    before = logged_total(doc.name)
    frappe.delete_doc(DOCTYPE, row.name, ignore_permissions=True)
    return _finished(doc.name, {doc.name: before})


def summary(doc, can_write):
    """The timer card on the job page."""
    me, manager, now = frappe.session.user, ops.manager(), now_datetime()
    rows = frappe.get_all(DOCTYPE, filters={"work_order": doc.name}, fields=FIELDS, order_by="started_at desc",
        limit_page_length=200)
    names = {p["user"]: p for p in ops.people(list({r.user for r in rows}))}
    invoiced = bool(doc.get("custom_sales_invoice"))
    for row in rows:
        row.full_name = names.get(row.user, {}).get("full_name") or row.user
        row.image = names.get(row.user, {}).get("image")
        # Seconds so far, so the browser can count on without trusting its own clock or timezone.
        row.elapsed = int(time_diff_in_seconds(now, row.started_at)) if not row.ended_at else None
        row.can_edit = not invoiced and (row.user == me or manager)
    total = round(sum(flt(r.hours) for r in rows if r.ended_at), 2)
    return {"entries": rows, "total": total, "running": [r for r in rows if not r.ended_at],
        "mine": next((r for r in rows if not r.ended_at and r.user == me), None),
        "can_start": bool(can_write) and doc.status not in CLOSED and not invoiced,
        "can_add": bool(can_write) and not invoiced, "manager": manager,
        "labour_hours": flt(doc.get("custom_labour_hours"))}


def mine():
    """My running clock, for the banner in the app shell."""
    if frappe.session.user == "Guest":
        return None
    for row in _running(user=frappe.session.user):
        return {"work_order": row.work_order, "subject": frappe.db.get_value("Task", row.work_order, "subject"),
            "elapsed": int(time_diff_in_seconds(now_datetime(), row.started_at))}
    return None
