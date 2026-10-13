"""Labour and invoicing for jobs on customer equipment.

Each job has labour charged by the hour or as a flat fee. Its default billing follows the cover:
Included when the machine is under warranty, or when its service contract covers labour (scheduled
visits) or call-outs (other jobs); Chargeable otherwise; jobs on our own equipment are not billed.
A manager turns completed jobs into a draft Sales Invoice: one job, or several jobs for the same
customer together. The invoice carries labour plus the chargeable approved parts and stays a draft
for accounts to review. A job is invoiced once; cancelling or deleting the invoice frees it again.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from projectit import ops, parts

INVOICE_ROLES = {"Accounts User", "Accounts Manager"}
LABOUR = ("Chargeable", "Included", "No charge")


def can_invoice():
    return ops.manager() or bool(set(frappe.get_roles()) & INVOICE_ROLES)


def _setting(field):
    return frappe.get_cached_doc("Techy Ops Settings").get(field)


def default_labour(task):
    """Chargeable, Included or No charge for a job's labour, from the machine's cover."""
    if not task.get("custom_equipment"):
        return "No charge"
    from projectit.equipment import coverage
    eq = frappe.db.get_value("Techy Equipment", task.custom_equipment, ["status", "warranty_until", "contract_until",
        "service_contract"], as_dict=True)
    kind = coverage(eq)["kind"] if eq else None
    if kind == "Warranty":
        return "Included"
    if kind == "Contract" and eq.service_contract:
        terms = frappe.db.get_value("Techy Service Contract", eq.service_contract, ["labour_included",
            "callouts_included", "status"], as_dict=True)
        if terms and terms.status != "Cancelled":
            visit = task.get("custom_service_contract") == eq.service_contract
            if (visit and terms.labour_included) or (not visit and terms.callouts_included):
                return "Included"
    return "Chargeable"


def labour(task):
    """The job's labour as it would be invoiced."""
    billing = task.get("custom_labour_billing") or default_labour(task)
    mode = task.get("custom_labour_mode") or "Hourly"
    hourly_item, flat_item = _setting("labour_hour_item"), _setting("flat_fee_item")
    rate = flt(task.get("custom_labour_rate")) or (parts.selling_rate(hourly_item) if hourly_item else 0)
    fee = flt(task.get("custom_flat_fee")) or (parts.selling_rate(flat_item) if flat_item else 0)
    hours = flt(task.get("custom_labour_hours"))
    amount = 0
    if billing == "Chargeable":
        amount = hours * rate if mode == "Hourly" else fee
    return {"billing": billing, "default_billing": default_labour(task), "mode": mode, "hours": hours, "rate": rate,
        "flat_fee": fee, "amount": amount, "hourly_item": hourly_item, "flat_item": flat_item}


def summary(task, can_write):
    closed = task.status in ("Completed", "Cancelled")
    data = labour(task)
    part_total = sum(flt(r.amount) for r in parts.billable(task.name))
    invoice = None
    if task.get("custom_sales_invoice"):
        invoice = frappe.db.get_value("Sales Invoice", task.custom_sales_invoice, ["name", "docstatus", "status",
            "grand_total", "currency"], as_dict=True)
    data.update(parts_total=part_total, total=data["amount"] + part_total, invoice=invoice,
        customer=task.get("custom_customer"), can_edit_hours=bool(can_write) and not invoice,
        can_edit=can_invoice() and not invoice, can_invoice=can_invoice() and task.status == "Completed"
            and bool(task.get("custom_customer")) and not invoice and (data["amount"] + part_total) > 0,
        currency=frappe.db.get_default("currency"), closed=closed)
    return data


@frappe.whitelist(methods=["POST"])
def set_labour(work_order, hours=None, billing=None, mode=None, rate=None, flat_fee=None):
    """Technicians record hours; managers (and accounts) decide billing, mode and rates."""
    from projectit import work_orders
    doc = work_orders._work_order(work_order)
    if doc.get("custom_sales_invoice"):
        frappe.throw(_("This job is already invoiced ({0}).").format(doc.custom_sales_invoice))
    values = {}
    if hours is not None:
        if not frappe.has_permission("Task", "write", doc=doc) and not can_invoice():
            frappe.throw(_("You cannot record hours on this job."), frappe.PermissionError)
        hours = flt(hours)
        if hours < 0 or hours > 500:
            frappe.throw(_("Enter the hours worked (0 to 500)."))
        values["custom_labour_hours"] = hours
    if any(v is not None for v in (billing, mode, rate, flat_fee)):
        if not can_invoice():
            frappe.throw(_("Only managers can change how labour is billed."), frappe.PermissionError)
        if billing is not None:
            if billing and billing not in LABOUR:
                frappe.throw(_("Invalid labour billing."))
            values["custom_labour_billing"] = billing or None
        if mode is not None:
            if mode not in ("Hourly", "Flat fee"):
                frappe.throw(_("Choose hourly or flat fee."))
            values["custom_labour_mode"] = mode
        for field, value in (("custom_labour_rate", rate), ("custom_flat_fee", flat_fee)):
            if value is not None:
                if flt(value) < 0:
                    frappe.throw(_("Amounts cannot be negative."))
                values[field] = flt(value)
    if values:
        # Billing fields only; saving the Task would re-run status and dependency validation.
        frappe.db.set_value("Task", doc.name, values)
    return work_orders.get_work_order(doc.name)


# Invoicing ---------------------------------------------------------------------------------------------------

def _require_invoicer():
    ops.system_user()
    if not can_invoice():
        frappe.throw(_("Only managers and accounts staff can create invoices."), frappe.PermissionError)


def _job_total(task):
    data = labour(task)
    part_total = sum(flt(r.amount) for r in parts.billable(task.name))
    return data, part_total


@frappe.whitelist()
def billing_queue():
    """Completed, uninvoiced customer jobs with something to charge, grouped by customer."""
    _require_invoicer()
    jobs = frappe.get_all("Task", filters={"custom_work_order": 1, "status": "Completed",
        "custom_customer": ["is", "set"], "custom_sales_invoice": ["is", "not set"], "parent_task": ["is", "not set"]},
        fields=["name", "subject", "custom_customer", "custom_equipment", "custom_service_contract", "custom_work_category",
            "custom_labour_billing", "custom_labour_mode", "custom_labour_hours", "custom_labour_rate", "custom_flat_fee",
            "project", "modified", "status"], order_by="modified desc", limit_page_length=300)
    from projectit.equipment import labels
    machines = labels(j.custom_equipment for j in jobs)
    customers = {}
    for job in jobs:
        data, part_total = _job_total(job)
        total = data["amount"] + part_total
        if total <= 0:
            continue
        group = customers.setdefault(job.custom_customer, {"customer": job.custom_customer,
            "customer_name": frappe.db.get_value("Customer", job.custom_customer, "customer_name"), "jobs": [], "total": 0})
        group["jobs"].append({"name": job.name, "subject": job.subject, "completed": job.modified,
            "equipment": machines.get(job.custom_equipment), "labour": data["amount"], "labour_mode": data["mode"],
            "hours": data["hours"], "parts": part_total, "total": total,
            "missing_hours": data["billing"] == "Chargeable" and data["mode"] == "Hourly" and not data["hours"]})
        group["total"] += total
    recent = frappe.get_all("Sales Invoice", filters={"name": ["in", frappe.get_all("Task",
        filters={"custom_sales_invoice": ["is", "set"]}, pluck="custom_sales_invoice", limit_page_length=200) or [""]]},
        fields=["name", "customer_name", "grand_total", "status", "docstatus", "posting_date"], order_by="creation desc",
        limit_page_length=20)
    return {"customers": sorted(customers.values(), key=lambda c: c["customer_name"] or ""), "recent": recent,
        "currency": frappe.db.get_default("currency")}


@frappe.whitelist(methods=["POST"])
def create_invoice(jobs):
    """One draft Sales Invoice for one or more completed jobs of the same customer."""
    _require_invoicer()
    names = frappe.parse_json(jobs) if isinstance(jobs, str) else (jobs or [])
    names = list(dict.fromkeys(names))
    if not names or len(names) > 100:
        frappe.throw(_("Choose the jobs to invoice."))
    # Oldest job first, so the invoice reads in the order the work was done.
    tasks = sorted((frappe.get_doc("Task", n, for_update=True) for n in names), key=lambda t: str(t.modified))
    customers = {t.get("custom_customer") for t in tasks}
    if len(customers) != 1 or None in customers:
        frappe.throw(_("Invoice jobs for one customer at a time."))
    hourly_item, flat_item = _setting("labour_hour_item"), _setting("flat_fee_item")
    items, projects = [], set()
    for task in tasks:
        if not task.custom_work_order or task.status != "Completed":
            frappe.throw(_("{0} is not a completed job.").format(task.name))
        if task.get("custom_sales_invoice"):
            frappe.throw(_("{0} is already invoiced ({1}).").format(task.name, task.custom_sales_invoice))
        data, part_total = _job_total(task)
        if data["amount"] + part_total <= 0:
            frappe.throw(_("{0} has nothing to charge.").format(task.name))
        label = f"{task.subject} ({task.name})"
        if data["amount"] > 0:
            item = hourly_item if data["mode"] == "Hourly" else flat_item
            if not item:
                frappe.throw(_("Set the labour items in Techy Ops Settings first."))
            hourly = data["mode"] == "Hourly"
            if hourly and flt(data["hours"]) % 1:
                uom = frappe.db.get_value("Item", item, "stock_uom")
                if frappe.db.get_value("UOM", uom, "must_be_whole_number"):
                    frappe.throw(_("{0} is measured in {1}, which only allows whole numbers. Set the labour item's unit "
                        "to Hour so part hours can be invoiced.").format(item, uom))
            items.append({"item_code": item, "qty": data["hours"] if hourly else 1,
                "rate": data["rate"] if hourly else data["flat_fee"],
                "description": _("Labour – {0}").format(label)})
        for row in parts.billable(task.name):
            if row.billing == "Chargeable" and flt(row.amount) > 0:
                items.append({"item_code": row.item_code, "qty": row.qty, "rate": row.rate,
                    "description": f"{row.item_name} – {label}"})
        if task.project:
            projects.add(task.project)
    customer = customers.pop()
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults",
        "default_company") or frappe.db.get_value("Company", {}, "name")
    invoice = frappe.get_doc({"doctype": "Sales Invoice", "customer": customer, "company": company,
        "posting_date": nowdate(), "due_date": nowdate(), "set_posting_time": 0, "update_stock": 0,
        "project": projects.pop() if len(projects) == 1 else None,
        "remarks": _("Techy Ops jobs: {0}").format(", ".join(t.name for t in tasks)), "items": items})
    invoice.set_missing_values()
    # Managers may lack Sales Invoice roles; the draft is reviewed and submitted by accounts in ERPNext.
    invoice.flags.ignore_permissions = True
    invoice.insert()
    for task in tasks:
        frappe.db.set_value("Task", task.name, "custom_sales_invoice", invoice.name)
        task.add_comment("Info", escape(_("{0} created draft invoice {1}.").format(frappe.utils.get_fullname(),
            invoice.name)))
    return {"invoice": invoice.name, "grand_total": invoice.grand_total, "currency": invoice.currency}


def release_jobs(doc, method=None):
    """Sales Invoice cancelled or deleted: its jobs can be invoiced again."""
    for task in frappe.get_all("Task", filters={"custom_sales_invoice": doc.name}, pluck="name"):
        frappe.db.set_value("Task", task, "custom_sales_invoice", None)
        frappe.get_doc("Task", task).add_comment("Info", escape(_("Invoice {0} was cancelled; the job can be invoiced again.")
            .format(doc.name)))
