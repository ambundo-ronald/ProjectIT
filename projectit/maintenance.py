"""Assets, locations and preventive maintenance on native ERPNext Asset / Asset Maintenance.

ERPNext's Asset Maintenance keeps one Planned Asset Maintenance Log per maintenance task.
A daily job turns logs that fall due into work orders; completing the work order submits
the log, which makes ERPNext roll the task's next due date forward and plan the next log.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import add_days, cint, nowdate

from projectit import meters, ops, work_orders

ASSET_FIELDS = ["name", "asset_name", "item_code", "asset_category", "location", "status", "image", "custodian"]


@frappe.whitelist()
def list_assets(search=None, location=None, start=0, page_length=None):
    ops.require_asset_access()
    filters = {"docstatus": ["<", 2]}
    if location:
        filters["location"] = location
    or_filters = None
    if search:
        search = f"%{str(search).strip()[:80]}%"
        or_filters = {"name": ["like", search], "asset_name": ["like", search], "item_code": ["like", search]}
    start, size = max(0, cint(start)), ops.page_size(page_length, 50)
    rows, total = ops.paged("Asset", filters, or_filters, "asset_name asc", start, size, ASSET_FIELDS)
    counts = {}
    if rows:  # Counts only, for Assets the user may already list.
        counts = dict(frappe.db.sql("""SELECT custom_asset, COUNT(*) FROM `tabTask`
            WHERE custom_work_order = 1 AND custom_asset IN %(assets)s AND status NOT IN ('Completed', 'Cancelled')
            GROUP BY custom_asset""", {"assets": tuple(r.name for r in rows)}))
    for row in rows:
        row.open_work_orders = counts.get(row.name, 0)
    return {"assets": rows, "total": total, "start": start, "page_length": size, "has_more": start + len(rows) < total}


@frappe.whitelist()
def get_asset(name):
    ops.require_asset_access()
    doc = frappe.get_doc("Asset", name)
    if doc.docstatus == 2:
        frappe.throw(_("Asset {0} is cancelled.").format(name))
    history = frappe.get_all("Task", filters={"custom_work_order": 1, "custom_asset": doc.name},
        fields=["name", "subject", "status", "priority", "exp_end_date", "custom_work_category", "modified"],
        order_by="modified desc", limit_page_length=50)
    requests = frappe.get_all("Issue", filters={"custom_maintenance_request": 1, "custom_asset": doc.name},
        fields=["name", "subject", "status", "opening_date", "custom_work_order"], order_by="creation desc",
        limit_page_length=20)
    return {"asset": {field: doc.get(field) for field in ASSET_FIELDS}, "plans": _plans({"asset_name": doc.name}),
        "work_orders": history, "requests": requests, "files": ops.files("Asset", doc.name),
        "meters": meters.for_machine(asset=doc.name, include_inactive=ops.manager()),
        "can_create": bool(frappe.has_permission("Task", "create")), "manager": ops.manager()}


@frappe.whitelist()
def list_locations():
    ops.system_user()
    return frappe.get_all("Location", fields=["name", "location_name", "parent_location", "is_group"],
        order_by="lft asc", limit_page_length=1000)


def _plans(filters):
    names = frappe.get_all("Asset Maintenance", filters=filters, pluck="name", limit_page_length=0)
    if not names:
        return []
    return frappe.get_all("Asset Maintenance Task", filters={"parent": ["in", names],
        "parenttype": "Asset Maintenance", "maintenance_status": ["!=", "Cancelled"]},
        fields=["name", "parent", "maintenance_task", "maintenance_type", "periodicity", "next_due_date",
            "last_completion_date", "assign_to", "maintenance_status"], order_by="next_due_date asc",
        limit_page_length=0)


@frappe.whitelist()
def pm_schedule(days=30):
    """Upcoming and overdue preventive maintenance, with any work order already raised for it."""
    ops.require_asset_access()
    until = add_days(nowdate(), min(max(cint(days), 1), 366))
    logs = frappe.get_all("Asset Maintenance Log", filters={"docstatus": 0, "maintenance_status": ["in",
        ["Planned", "Overdue"]], "due_date": ["<=", until]}, fields=["name", "asset_name", "task", "task_name",
        "maintenance_type", "periodicity", "due_date", "maintenance_status", "assign_to_name"],
        order_by="due_date asc", limit_page_length=500)
    linked = dict(frappe.get_all("Task", filters={"custom_asset_maintenance_log": ["in", [l.name for l in logs] or [""]]},
        fields=["custom_asset_maintenance_log", "name"], as_list=True))
    labels = ops.asset_names(log.asset_name for log in logs)
    procedure = dict(frappe.get_all("Asset Maintenance Task", filters={"name": ["in", [l.task for l in logs] or [""]]},
        fields=["name", "custom_procedure"], as_list=True))
    titles = dict(frappe.get_all("Techy Procedure", filters={"name": ["in", [p for p in procedure.values() if p] or [""]]},
        fields=["name", "title"], as_list=True))
    for log in logs:
        log.work_order = linked.get(log.name)
        log.asset_label = labels.get(log.asset_name)
        log.procedure = procedure.get(log.task)
        log.procedure_title = titles.get(log.procedure)
    return {"logs": logs, "lead_days": ops.settings().pm_lead_days, "manager": ops.manager()}


def _active_procedure(name):
    return name if name and not frappe.db.get_value("Techy Procedure", name, "disabled") else None


@frappe.whitelist(methods=["POST"])
def set_task_procedure(task, procedure=None):
    """Choose the procedure that work orders from this Asset Maintenance task will carry."""
    ops.require_asset_access()
    ops.require_manager()
    parent = frappe.db.get_value("Asset Maintenance Task", task, "parent")
    if not parent:
        frappe.throw(_("Maintenance task {0} was not found.").format(task))
    if procedure and not _active_procedure(procedure):
        frappe.throw(_("Choose an active procedure."))
    # Managers are authorised above; the plan itself (Asset Maintenance) is not otherwise changed.
    frappe.db.set_value("Asset Maintenance Task", task, "custom_procedure", procedure or None)
    return {"task": task, "procedure": procedure or None}


@frappe.whitelist(methods=["POST"])
def run_pm_now():
    ops.require_manager()
    return {"created": generate_pm_work_orders()}


def generate_pm_work_orders():
    """Daily scheduler job: one work order per due, not-yet-raised Asset Maintenance Log."""
    until = add_days(nowdate(), ops.settings().pm_lead_days)
    logs = frappe.get_all("Asset Maintenance Log", filters={"docstatus": 0, "maintenance_status": ["in",
        ["Planned", "Overdue"]], "due_date": ["<=", until]}, fields=["name", "asset_name", "task", "task_name",
        "description", "due_date"], order_by="due_date asc", limit_page_length=500)
    raised = set(frappe.get_all("Task", filters={"custom_asset_maintenance_log": ["in", [l.name for l in logs] or [""]]},
        pluck="custom_asset_maintenance_log"))
    created = []
    for log in logs:
        if log.name in raised:
            continue
        task = frappe.db.get_value("Asset Maintenance Task", log.task, ["assign_to", "description",
            "custom_procedure"], as_dict=True) or {}
        frappe.db.savepoint("techy_pm")
        try:
            label = frappe.db.get_value("Asset", log.asset_name, "asset_name") or log.asset_name
            doc = work_orders.create(_("PM: {0} – {1}").format(log.task_name or log.task, label)[:140],
                description=frappe.utils.strip_html(task.get("description") or log.description or "")[:4000],
                category="Preventive", asset=log.asset_name, assignees=[task["assign_to"]] if task.get("assign_to") else [],
                due_date=log.due_date, pm_log=log.name, procedure=_active_procedure(task.get("custom_procedure")))
            created.append(doc.name)
        except Exception:
            frappe.db.rollback(save_point="techy_pm")
            frappe.log_error(title=f"Techy Ops: PM work order for {log.name} failed")
    return created


def complete_log(work_order):
    """Submit the work order's Asset Maintenance Log as Completed so ERPNext schedules the next one."""
    log = frappe.get_doc("Asset Maintenance Log", work_order.custom_asset_maintenance_log)
    if log.docstatus != 0:
        return
    user = frappe.session.user
    log.maintenance_status = "Completed"
    log.completion_date = nowdate()
    log.actions_performed = escape(_("Completed by {0} through work order {1}.").format(
        frappe.utils.get_fullname(user), work_order.name))
    if log.has_certificate and not log.certificate_attachement:
        log.certificate_attachement = ops.files("Task", work_order.name)[0].file_url
    # The technician completed the permitted work order; the log is its system-owned record. ERPNext's
    # on_submit also re-saves the Asset Maintenance without permission flags, so submit as Administrator.
    # set_user() also replaces the request's sid, session data and form_dict, so restore those too.
    sid, data, form = frappe.local.session.sid, frappe.local.session.data, frappe.local.form_dict
    frappe.set_user("Administrator")
    try:
        log.submit()
    finally:
        frappe.set_user(user)
        frappe.local.session.sid, frappe.local.session.data, frappe.local.form_dict = sid, data, form
