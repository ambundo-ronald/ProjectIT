"""Dispatch calendar: managers plan who does which job on which day.

A job's planned day is the Task's Expected Start Date (exp_start_date) and its technicians are its ERPNext
assignments (ToDo), so the plan shows in Desk too. The board lists the technicians down the side and the days
across; jobs not planned yet wait in a list to be dragged onto a day.
"""
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from projectit import ops

FIELDS = ["name", "subject", "status", "priority", "exp_start_date", "exp_end_date", "custom_work_category",
    "custom_equipment", "custom_customer", "custom_asset", "custom_location"]
CLOSED = ("Completed", "Cancelled")
SPANS = (1, 7, 14)
TECH_ROLES = ("Maintenance User", "Maintenance Manager")
BASE = {"custom_work_order": 1, "is_template": 0, "parent_task": ["is", "not set"]}


def _monday(day):
    return day - timedelta(days=day.weekday())


def technicians(extra=()):
    """Staff who do maintenance work, plus anyone else already assigned jobs on the board."""
    users = set(frappe.get_all("Has Role", filters={"role": ["in", list(TECH_ROLES)], "parenttype": "User"},
        pluck="parent")) | set(extra)
    users = frappe.get_all("User", filters=[["name", "in", list(users) or [""]], ["name", "not in", ["Administrator", "Guest"]],
        ["enabled", "=", 1], ["user_type", "=", "System User"]], pluck="name")
    return sorted(ops.people(users), key=lambda p: (p.get("full_name") or p["user"]).lower())


def _rows(filters, limit=0, order_by="exp_start_date asc, priority desc"):
    from projectit import equipment
    from projectit.work_orders import _assignees
    rows = frappe.get_all("Task", filters={**BASE, **filters}, fields=FIELDS, order_by=order_by,
        limit_page_length=limit)
    assigned = _assignees([r.name for r in rows])
    machines = equipment.labels(r.custom_equipment for r in rows)
    assets = ops.asset_names(r.custom_asset for r in rows)
    for row in rows:
        # ERPNext v16 stores the expected dates with a time; the board works in days.
        row.exp_start_date = getdate(row.exp_start_date) if row.exp_start_date else None
        row.exp_end_date = getdate(row.exp_end_date) if row.exp_end_date else None
        row.assignees = assigned[row.name]
        machine = machines.get(row.custom_equipment) or {}
        row.machine = machine.get("equipment_name") or assets.get(row.custom_asset)
        row.where = machine.get("customer_name") or row.custom_location
    return rows


@frappe.whitelist()
def board(start=None, days=7):
    """The plan for `days` days from `start` (a week starts on Monday), and the jobs still to plan."""
    ops.require_manager()
    days = cint(days) if cint(days) in SPANS else 7
    start = getdate(start) if start else getdate(nowdate())
    if days > 1:
        start = _monday(start)
    end = start + timedelta(days=days - 1)
    planned = _rows({"exp_start_date": ["between", [start, end]], "status": ["!=", "Cancelled"]})
    # Not planned yet, or planned for an earlier day and still not done.
    backlog = _rows({"status": ["not in", CLOSED], "exp_start_date": ["is", "not set"]}, limit=200,
        order_by="creation desc")
    backlog.sort(key=lambda r: (r.exp_end_date is None, getdate(r.exp_end_date) if r.exp_end_date else start))  # soonest due first
    # Frappe compares an empty date as the earliest date, so keep only jobs that really were planned.
    late = [r for r in _rows({"status": ["not in", CLOSED], "exp_start_date": ["<", start]}, limit=300)
        if r.exp_start_date][:100]
    people = technicians({u for r in planned for u in r.assignees})
    return {"start": start, "end": end, "today": getdate(nowdate()), "days": [start + timedelta(days=i) for i in range(days)],
        "people": people, "jobs": planned, "backlog": backlog, "late": late}


@frappe.whitelist(methods=["POST"])
def schedule(name, date=None, user=None, from_user=None, move_due=0):
    """Plan a job for a day (no date: back to the list) and, optionally, move it from one technician to another.

    If the day is after the job's due date the plan is not changed and {"needs_due_move": due} is returned, so the
    manager can confirm moving the due date as well (move_due=1).
    """
    from frappe.desk.form.assign_to import add, remove
    from projectit.work_orders import _assignees
    ops.require_manager()
    doc = frappe.get_doc("Task", name)
    if not doc.custom_work_order or doc.parent_task:
        frappe.throw(_("{0} is not a work order.").format(name))
    if doc.status in CLOSED:
        frappe.throw(_("{0} is already {1}.").format(name, _(doc.status).lower()))
    day = getdate(date) if date else None
    if day and doc.exp_end_date and getdate(doc.exp_end_date) < day:
        if not cint(move_due):
            return {"needs_due_move": doc.exp_end_date}
        doc.exp_end_date = day
    current = set(_assignees([doc.name])[doc.name])
    if user:
        user = ops.active_users([user])[0]  # rejects unknown or disabled users
    changed = (getdate(doc.exp_start_date) if doc.exp_start_date else None) != day
    doc.exp_start_date = day
    if changed or cint(move_due):
        doc.save()
    if from_user and from_user != user and from_user in current:
        remove("Task", doc.name, from_user)
    if user and user not in current:
        add({"doctype": "Task", "name": doc.name, "assign_to": [user], "description": doc.subject})
    told = [u for u in ({user} if user else set(_assignees([doc.name])[doc.name])) if u]
    if day and (changed or (user and user not in current)):
        ops.notify(told, _("Planned for {0}: {1}").format(frappe.utils.format_date(day), doc.subject), "Task",
            doc.name, "Assignment")
    ops.push(set(told) | current | {from_user}, "techy_work_order", {"name": doc.name})
    return {"name": doc.name, "exp_start_date": day, "assignees": _assignees([doc.name])[doc.name]}
