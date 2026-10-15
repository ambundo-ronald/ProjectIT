"""Parts on jobs: technicians list them, a manager or Stock Manager approves, ERPNext issues them.

Lines start as Draft while the technician builds the list, become Requested when sent for approval,
and Approved (or Rejected, with a reason) by a manager or Stock Manager. Approving raises one ERPNext
Material Request (Material Issue) per company for the approved lines, linked to the job; the stock team
fulfils it as usual and the Stock Entry marks the lines Issued. Each line's billing follows the machine's
cover: Internal for our own work, Warranty, Contract when the part is on the contract's included list,
otherwise Chargeable at the selling price. Managers can override a line.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, nowdate

from projectit import ops

BILLING = ("Chargeable", "Contract", "Warranty", "Internal", "No charge")
APPROVER_ROLES = {"Stock Manager", "Maintenance Manager", "Projects Manager", "System Manager"}
OPEN = ("Draft", "Requested")
FIELDS = ["name", "work_order", "equipment", "item_code", "item_name", "qty", "uom", "warehouse", "billing",
    "billing_set_by_manager", "rate", "amount", "valuation_rate", "status", "stock_entry", "material_request",
    "requested_on", "approved_by", "rejection_reason", "owner", "creation"]


def _setting(field):
    return frappe.get_cached_doc("Techy Ops Settings").get(field)


def can_approve(user=None):
    user = user or frappe.session.user
    return user != "Guest" and bool(set(frappe.get_roles(user)) & APPROVER_ROLES)


def approvers():
    users = frappe.get_all("Has Role", filters={"role": ["in", list(APPROVER_ROLES - {"System Manager"})],
        "parenttype": "User"}, pluck="parent")
    return frappe.get_all("User", filters={"name": ["in", users or [""]], "enabled": 1, "user_type": "System User"},
        pluck="name")


def available(item_code, warehouse):
    return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def selling_rate(item_code):
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    # The price list is the selling one; customer- or batch-specific prices are left to invoicing.
    rate = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": price_list,
        "customer": ["is", "not set"], "batch_no": ["is", "not set"]}, "price_list_rate") if price_list else None
    return flt(rate if rate is not None else frappe.db.get_value("Item", item_code, "standard_rate"))


def default_billing(task, item_code):
    """Who pays for this part on this job, from the machine's warranty and contract."""
    if not task.get("custom_equipment") or task.get("custom_work_category") == "Installation":
        return "Internal"  # our own equipment, or installation materials costed on the project
    from projectit.equipment import coverage
    eq = frappe.db.get_value("Techy Equipment", task.custom_equipment, ["status", "warranty_until", "contract_until",
        "service_contract"], as_dict=True)
    kind = coverage(eq)["kind"] if eq else None
    if kind == "Warranty":
        return "Warranty"
    if eq and eq.service_contract and eq.contract_until and getdate(eq.contract_until) >= getdate(nowdate()) \
            and frappe.db.exists("Techy Contract Item", {"parent": eq.service_contract,
                "parenttype": "Techy Service Contract", "item_code": item_code}):
        return "Contract"
    return "Chargeable"


def _amount(row):
    return flt(row.qty) * flt(row.rate) if row.billing == "Chargeable" else 0


def billable(task_name):
    """Approved or issued lines: what was actually supplied for the job."""
    return frappe.get_all("Techy Part Usage", filters={"work_order": task_name, "status": ["in", ["Approved", "Issued"]]},
        fields=FIELDS, order_by="creation asc")


def summary(task_name, can_edit=False):
    rows = frappe.get_all("Techy Part Usage", filters={"work_order": task_name}, fields=FIELDS, order_by="creation asc")
    for row in rows:
        row.in_stock = available(row.item_code, row.warehouse)
    supplied = [r for r in rows if r.status in ("Approved", "Issued")]
    return {"rows": rows, "chargeable_total": sum(flt(r.amount) for r in supplied),
        "cost_total": sum(flt(r.qty) * flt(r.valuation_rate) for r in supplied), "can_edit": bool(can_edit),
        "can_approve": can_approve(), "drafts": sum(1 for r in rows if r.status == "Draft"),
        "pending": sum(1 for r in rows if r.status == "Requested"),
        "default_warehouse": _setting("default_parts_warehouse"), "manager": ops.manager(),
        "currency": frappe.db.get_default("currency")}


def history(equipment):
    """Every part supplied for a machine, newest first."""
    return frappe.get_all("Techy Part Usage", filters={"equipment": equipment, "status": ["in", ["Approved", "Issued"]]},
        fields=["name", "work_order", "item_code", "item_name", "qty", "uom", "billing", "status", "creation"],
        order_by="creation desc", limit_page_length=100)


# Building the list -------------------------------------------------------------------------------------------

@frappe.whitelist()
def search_parts(txt=None, warehouse=None, work_order=None):
    """Stock items to add to a job; parts the job's machine was built with come first."""
    ops.system_user()
    like = f"%{str(txt or '').strip()[:80]}%"
    base = {"disabled": 0, "is_stock_item": 1, "has_variants": 0}
    fields = ["name", "item_name", "stock_uom"]
    items = frappe.get_all("Item", filters=base, or_filters={"name": ["like", like], "item_name": ["like", like]},
        fields=fields, order_by="item_name asc", limit_page_length=40)
    fitted = set()
    if work_order:
        from projectit import work_orders
        from projectit.equipment import component_rows
        fitted = {r.item_code for r in component_rows(work_orders._work_order(work_order).get("custom_equipment"))}
        missing = fitted - {i.name for i in items}
        if missing:
            items += frappe.get_all("Item", filters={**base, "name": ["in", list(missing)]},
                or_filters={"name": ["like", like], "item_name": ["like", like]}, fields=fields)
    stock = {}
    if items:
        for b in frappe.get_all("Bin", filters={"item_code": ["in", [i.name for i in items]], "actual_qty": [">", 0]},
                fields=["item_code", "warehouse", "actual_qty"]):
            entry = stock.setdefault(b.item_code, {"total": 0, "here": 0})
            entry["total"] += flt(b.actual_qty)
            if b.warehouse == warehouse:
                entry["here"] = flt(b.actual_qty)
    for item in items:
        item.in_stock = stock.get(item.name, {}).get("total", 0)
        item.here = stock.get(item.name, {}).get("here", 0)
        item.fitted = item.name in fitted
    items.sort(key=lambda i: (-i.fitted, -(i.here > 0), -(i.in_stock > 0), i.item_name or ""))
    return items[:20]


@frappe.whitelist()
def part_warehouses(item_code):
    """Warehouses holding the item, plus the default parts warehouse."""
    ops.system_user()
    rows = frappe.get_all("Bin", filters={"item_code": item_code, "actual_qty": [">", 0]},
        fields=["warehouse", "actual_qty"], order_by="actual_qty desc")
    default = _setting("default_parts_warehouse")
    if default and not any(r.warehouse == default for r in rows):
        rows.insert(0, frappe._dict(warehouse=default, actual_qty=0))
    return {"warehouses": rows, "default": default}


def _job(work_order):
    from projectit import work_orders
    doc = work_orders._work_order(work_order, write=True)
    if doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("Reopen the job to change its parts."))
    return doc


def _result(doc):
    from projectit import procedures
    return procedures._result(doc)


def _line(doc, name):
    row = frappe.get_doc("Techy Part Usage", name)
    if row.work_order != doc.name:
        frappe.throw(_("This part is not on the job."))
    return row


@frappe.whitelist(methods=["POST"])
def add_part(work_order, item_code, qty, warehouse):
    """Add a line to the job's parts list (a draft until it is sent for approval)."""
    doc = _job(work_order)
    item = frappe.db.get_value("Item", item_code, ["name", "item_name", "stock_uom", "is_stock_item", "disabled"],
        as_dict=True)
    if not item or not item.is_stock_item or item.disabled:
        frappe.throw(_("Choose an active stock item."))
    qty = flt(qty)
    if qty <= 0 or qty > 10000:
        frappe.throw(_("Enter a quantity above zero."))
    if not frappe.db.get_value("Warehouse", {"name": warehouse, "is_group": 0, "disabled": 0}):
        frappe.throw(_("Choose a warehouse."))
    row = frappe.get_doc({"doctype": "Techy Part Usage", "work_order": doc.name, "equipment": doc.get("custom_equipment"),
        "item_code": item_code, "qty": qty, "uom": item.stock_uom, "warehouse": warehouse,
        "billing": default_billing(doc, item_code), "rate": selling_rate(item_code),
        "valuation_rate": flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate")),
        "status": "Draft"})
    row.amount = _amount(row)
    # Anyone who may work the job may list its parts; nothing moves until an approver signs off.
    row.insert(ignore_permissions=True)
    return _result(doc)


@frappe.whitelist(methods=["POST"])
def remove_part(work_order, name):
    doc = _job(work_order)
    row = _line(doc, name)
    if row.status not in ("Draft", "Requested", "Rejected"):
        frappe.throw(_("This part was approved. Cancel its Material Request in ERPNext to undo it."))
    frappe.delete_doc("Techy Part Usage", row.name, ignore_permissions=True)
    return _result(doc)


@frappe.whitelist(methods=["POST"])
def request_approval(work_order):
    """Send the job's draft lines to the approvers."""
    doc = _job(work_order)
    drafts = frappe.get_all("Techy Part Usage", filters={"work_order": doc.name, "status": "Draft"},
        fields=["name", "item_name", "qty"])
    if not drafts:
        frappe.throw(_("Add parts to the list first."))
    for row in drafts:
        frappe.db.set_value("Techy Part Usage", row.name, {"status": "Requested", "requested_on": now_datetime()})
    lines = ", ".join(f"{frappe.format(r.qty)} × {r.item_name}" for r in drafts)
    doc.add_comment("Info", escape(_("{0} requested parts: {1}").format(frappe.utils.get_fullname(), lines)))
    ops.notify(approvers(), _("Parts to approve for {0}: {1}").format(doc.subject, lines)[:250], "Task", doc.name,
        "Assignment")
    ops.push(approvers(), "techy_work_order", {"name": doc.name})
    return _result(doc)


# Approval ----------------------------------------------------------------------------------------------------

def _approver_job(work_order):
    ops.system_user()
    if not can_approve():
        frappe.throw(_("Only managers and Stock Managers can approve parts."), frappe.PermissionError)
    # Approvers act on any job's parts list; the Task is read directly because Stock Managers usually
    # have no Task access.
    doc = frappe.get_doc("Task", work_order)
    if not doc.custom_work_order:
        frappe.throw(_("{0} is not a work order.").format(work_order))
    return doc


@frappe.whitelist(methods=["POST"])
def approve_parts(work_order, lines=None):
    """Approve requested lines (all when none are given) and raise the Material Request."""
    doc = _approver_job(work_order)
    lines = frappe.parse_json(lines) if isinstance(lines, str) else lines
    filters = {"work_order": doc.name, "status": "Requested"}
    if lines:
        filters["name"] = ["in", list(lines)]
    rows = frappe.get_all("Techy Part Usage", filters=filters, fields=["name", "item_code", "qty", "uom", "warehouse",
        "owner"], order_by="creation asc")
    if not rows:
        frappe.throw(_("There are no parts waiting for approval."))
    by_company = {}
    for row in rows:
        by_company.setdefault(frappe.db.get_value("Warehouse", row.warehouse, "company"), []).append(row)
    account = _setting("parts_expense_account")
    made = []
    for company, group in by_company.items():
        schedule = max(getdate(nowdate()), getdate(doc.exp_end_date)) if doc.exp_end_date else getdate(nowdate())
        mr = frappe.get_doc({"doctype": "Material Request", "material_request_type": "Material Issue", "company": company,
            "schedule_date": schedule, "custom_work_order": doc.name,
            "items": [{"item_code": r.item_code, "qty": r.qty, "uom": r.uom, "warehouse": r.warehouse,
                "schedule_date": schedule, "project": doc.project, **({"expense_account": account} if account else {})}
                for r in group]})
        # Approval is the authority here; approvers may lack Material Request roles (e.g. Maintenance Managers).
        mr.flags.ignore_permissions = True
        mr.insert()
        mr.submit()
        for r, item in zip(group, mr.items):
            frappe.db.set_value("Techy Part Usage", r.name, {"status": "Approved", "material_request": mr.name,
                "material_request_item": item.name, "approved_by": frappe.session.user})
        made.append(mr.name)
    doc.add_comment("Info", escape(_("{0} approved {1} part line(s): {2}.").format(frappe.utils.get_fullname(), len(rows),
        ", ".join(made))))
    owners = {r.owner for r in rows}
    ops.notify(owners, _("Parts approved for {0} ({1})").format(doc.subject, ", ".join(made)), "Task", doc.name)
    ops.push(owners | set(_people(doc)), "techy_work_order", {"name": doc.name})
    return {"material_requests": made, "job": _view(doc)}


@frappe.whitelist(methods=["POST"])
def reject_parts(work_order, lines, reason):
    doc = _approver_job(work_order)
    reason = ops.text(reason, "a reason", 500)
    lines = frappe.parse_json(lines) if isinstance(lines, str) else lines
    rows = frappe.get_all("Techy Part Usage", filters={"work_order": doc.name, "status": "Requested",
        "name": ["in", list(lines or []) or [""]]}, fields=["name", "item_name", "owner"])
    if not rows:
        frappe.throw(_("There are no parts waiting for approval."))
    for row in rows:
        frappe.db.set_value("Techy Part Usage", row.name, {"status": "Rejected", "rejection_reason": reason,
            "approved_by": frappe.session.user})
    doc.add_comment("Info", escape(_("{0} rejected {1}: {2}").format(frappe.utils.get_fullname(),
        ", ".join(r.item_name for r in rows), reason)))
    ops.notify({r.owner for r in rows}, _("Parts rejected for {0}: {1}").format(doc.subject, reason)[:250], "Task",
        doc.name)
    ops.push({r.owner for r in rows} | set(_people(doc)), "techy_work_order", {"name": doc.name})
    return {"job": _view(doc)}


def _people(doc):
    from projectit import work_orders
    return work_orders._assignees([doc.name])[doc.name] + [doc.owner]


def _view(doc):
    """The job page data when the approver can open the job (Stock Managers may not)."""
    from projectit import work_orders
    try:
        return work_orders.get_work_order(doc.name)
    except frappe.PermissionError:
        frappe.clear_messages()
        return None


@frappe.whitelist(methods=["POST"])
def set_billing(work_order, name, billing):
    """Managers decide the billing for a line, until the job is invoiced."""
    from projectit import work_orders
    ops.require_manager()
    doc = work_orders._work_order(work_order)
    if billing not in BILLING:
        frappe.throw(_("Invalid billing."))
    if doc.get("custom_sales_invoice"):
        frappe.throw(_("This job is already invoiced ({0}).").format(doc.custom_sales_invoice))
    row = _line(doc, name)
    row.billing = billing
    row.billing_set_by_manager = 1
    row.amount = _amount(row)
    row.save(ignore_permissions=True)
    return _result(doc)


@frappe.whitelist()
def approval_queue():
    """Requested lines across all jobs, grouped by job, for approvers."""
    ops.system_user()
    if not can_approve():
        frappe.throw(_("Only managers and Stock Managers can approve parts."), frappe.PermissionError)
    rows = frappe.get_all("Techy Part Usage", filters={"status": "Requested"}, fields=FIELDS, order_by="requested_on asc",
        limit_page_length=500)
    jobs = {}
    for row in rows:
        row.in_stock = available(row.item_code, row.warehouse)
        jobs.setdefault(row.work_order, []).append(row)
    info = {t.name: t for t in frappe.get_all("Task", filters={"name": ["in", list(jobs) or [""]]},
        fields=["name", "subject", "custom_customer", "custom_equipment", "exp_end_date", "status"])}
    from projectit.equipment import labels
    machines = labels(t.custom_equipment for t in info.values())
    result = []
    for name, lines in jobs.items():
        task = info.get(name) or frappe._dict(name=name)
        result.append({"work_order": name, "subject": task.subject, "status": task.status, "due": task.exp_end_date,
            "equipment": machines.get(task.custom_equipment), "requested_by": frappe.utils.get_fullname(lines[0].owner),
            "requested_on": lines[0].requested_on, "lines": lines,
            "chargeable_total": sum(flt(l.amount) for l in lines)})
    return {"jobs": result, "currency": frappe.db.get_default("currency")}


def pending_count():
    return frappe.db.count("Techy Part Usage", {"status": "Requested"}) if can_approve() else 0


# Job completion and ERPNext stock --------------------------------------------------------------------------

def check_open(task_name):
    """Before completing: the parts list must have been decided (validate_task)."""
    drafts = frappe.db.count("Techy Part Usage", {"work_order": task_name, "status": "Draft"})
    if drafts:
        frappe.throw(_("{0} part(s) on this job were never sent for approval. Request approval or remove them first.")
            .format(drafts))
    waiting = frappe.db.count("Techy Part Usage", {"work_order": task_name, "status": "Requested"})
    if waiting:
        frappe.throw(_("{0} part(s) on this job are waiting for approval.").format(waiting))


def on_stock_entry_submit(doc, method=None):
    """A Stock Entry made from the Material Request marks the job's lines Issued."""
    for item in doc.items:
        if item.get("material_request_item"):
            frappe.db.set_value("Techy Part Usage", {"material_request_item": item.material_request_item,
                "status": "Approved"}, {"status": "Issued", "stock_entry": doc.name})


def on_stock_entry_cancel(doc, method=None):
    for item in doc.items:
        if item.get("material_request_item"):
            frappe.db.set_value("Techy Part Usage", {"material_request_item": item.material_request_item,
                "stock_entry": doc.name}, {"status": "Approved", "stock_entry": None})


def on_material_request_cancel(doc, method=None):
    """A cancelled Material Request sends its lines back for a new decision."""
    if not doc.get("custom_work_order"):
        return
    frappe.db.set_value("Techy Part Usage", {"material_request": doc.name, "status": "Approved"},
        {"status": "Requested", "material_request": None, "material_request_item": None, "approved_by": None})
