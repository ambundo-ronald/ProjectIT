"""Paying contractors: payout runs that turn approved pay lines into draft Purchase Invoices.

A payout run collects every approved line (not on hold, not yet billed) up to a date, for the contractors due by
their usual pay cycle. *Create bills* makes one draft Purchase Invoice per contractor, to their Supplier:

- each job, milestone and reimbursement is its own line, with its project and the project's cost centre, so the cost
  is booked to the right project;
- deductions (materials not returned) are taken off as the invoice's discount, and listed in its remarks;
- withholding tax applies when the Supplier has a Tax Withholding Category (set by Accounts in ERPNext).

Accounts reviews, submits and pays the invoice the usual way. A paid invoice shows its lines as *Paid* on the
contractor's statement (contractor_pay.shown_status). Cancelling or deleting the invoice frees its lines for the next
run, so nothing is paid twice.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate

from projectit import billing, contractor_pay, ops

LINE = contractor_pay.LINE
CYCLES = ("Per job", "Weekly", "Monthly")


def can_pay(user=None):
    """Managers and Accounts staff run payouts."""
    return billing.can_invoice()


def _require():
    ops.login()
    if not can_pay():
        frappe.throw(_("Only managers and accounts staff can run contractor payouts."), frappe.PermissionError)


def _setting(field):
    return frappe.get_cached_doc("Techy Ops Settings").get(field)


def _due(rows, up_to):
    return [r for r in rows if r.status == "Approved" and not r.purchase_invoice
        and getdate(r.approved_on or r.modified) <= up_to]


@frappe.whitelist()
def preview(up_to=None, cycle=None):
    """What would be billed: per contractor, the approved lines up to `up_to` (default today)."""
    _require()
    up_to = getdate(up_to or nowdate())
    filters = {"enabled": 1}
    if cycle in CYCLES:
        filters["pay_cycle"] = cycle
    contractors = frappe.get_all("Techy Contractor", filters=filters, fields=["name", "contractor_name", "supplier",
        "pay_cycle"], order_by="contractor_name asc", limit_page_length=0)
    by_name = {c.name: c for c in contractors}
    rows = frappe.get_all(LINE, filters={"contractor": ["in", list(by_name) or [""]], "status": "Approved",
        "purchase_invoice": ["is", "not set"]}, fields=contractor_pay.LINE_FIELDS, order_by="approved_on asc",
        limit_page_length=0)
    subjects = dict(frappe.get_all("Task", filters={"name": ["in", list({r.work_order for r in rows if r.work_order}) or [""]]},
        fields=["name", "subject"], as_list=True))
    groups = {}
    for r in _due(rows, up_to):
        r.subject = subjects.get(r.work_order)
        g = groups.setdefault(r.contractor, {**by_name[r.contractor], "lines": [], "earned": 0, "reimbursed": 0,
            "deducted": 0, "net": 0, "queried": 0})
        g["lines"].append(r)
        if r.pay_type == "Deduction":
            g["deducted"] += flt(r.amount)
        elif r.pay_type == "Reimbursement":
            g["reimbursed"] += flt(r.amount)
        else:
            g["earned"] += flt(r.amount)
        g["queried"] += 1 if r.queried else 0
    for g in groups.values():
        g["net"] = round(g["earned"] + g["reimbursed"] - g["deducted"], 2)
        g["problem"] = (_("No supplier") if not g["supplier"] else
            _("The deductions are more than the pay") if g["net"] < 0 else None)
    item = _setting("contractor_item")
    return {"up_to": up_to, "cycle": cycle, "contractors": list(groups.values()),
        "total": round(sum(g["net"] for g in groups.values()), 2), "item": item,
        "setup": None if item else _("Set the Contractor Work Item in Techy Ops Settings first."),
        "currency": frappe.db.get_default("currency"), "recent": recent()}


def recent(limit=20):
    names = frappe.get_all(LINE, filters={"purchase_invoice": ["is", "set"]}, pluck="purchase_invoice", distinct=True,
        order_by="modified desc", limit_page_length=200)
    return frappe.get_all("Purchase Invoice", filters={"name": ["in", list(dict.fromkeys(names)) or [""]]},
        fields=["name", "supplier", "supplier_name", "grand_total", "status", "docstatus", "posting_date",
            "outstanding_amount"], order_by="creation desc", limit_page_length=limit)


def _company():
    return (frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        or frappe.db.get_value("Company", {}, "name"))


def _bill(contractor, lines):
    con = frappe.get_doc("Techy Contractor", contractor)
    if not con.supplier:
        frappe.throw(_("{0} has no supplier.").format(con.contractor_name))
    work_item = _setting("contractor_item")
    if not work_item:
        frappe.throw(_("Set the Contractor Work Item in Techy Ops Settings first."))
    refund_item = _setting("contractor_reimbursement_item") or work_item
    subjects = dict(frappe.get_all("Task", filters={"name": ["in", [l.work_order for l in lines if l.work_order] or [""]]},
        fields=["name", "subject"], as_list=True))
    cost_centres = dict(frappe.get_all("Project", filters={"name": ["in", [l.project for l in lines if l.project] or [""]]},
        fields=["name", "cost_center"], as_list=True))
    items, deductions, notes = [], 0, []
    for l in lines:
        if l.pay_type == "Deduction":
            deductions += flt(l.amount)
            notes.append(_("Deducted {0}: {1}").format(frappe.utils.fmt_money(l.amount), l.description))
            continue
        job = f" – {subjects.get(l.work_order)} ({l.work_order})" if l.work_order else ""
        row = {"item_code": refund_item if l.pay_type == "Reimbursement" else work_item, "qty": 1, "rate": flt(l.amount),
            "description": f"{l.description}{job}"[:1000], "project": l.project or None}
        if l.project and cost_centres.get(l.project):
            row["cost_center"] = cost_centres[l.project]
        items.append(row)
    total = sum(i["rate"] for i in items)
    if not items or total - deductions <= 0:
        frappe.throw(_("{0}: there is nothing to pay after deductions.").format(con.contractor_name))
    supplier = frappe.db.get_value("Supplier", con.supplier, ["tax_withholding_category"], as_dict=True) or {}
    invoice = frappe.get_doc({"doctype": "Purchase Invoice", "supplier": con.supplier, "company": _company(),
        "posting_date": nowdate(), "set_posting_time": 0, "update_stock": 0, "items": items,
        "apply_tds": 1 if supplier.get("tax_withholding_category") else 0,
        "remarks": "\n".join([_("Techy contractor pay: {0}").format(", ".join(l.name for l in lines))] + notes)})
    if deductions:
        invoice.apply_discount_on = "Net Total"
        invoice.discount_amount = round(deductions, 2)
    invoice.set_missing_values()
    # Managers may lack Purchase Invoice roles; the draft is reviewed and submitted by Accounts in ERPNext.
    invoice.flags.ignore_permissions = True
    invoice.insert()
    for l in lines:
        frappe.db.set_value(LINE, l.name, {"status": "Billed", "purchase_invoice": invoice.name})
    jobs = {l.work_order for l in lines if l.work_order}
    for job in jobs:
        frappe.get_doc("Task", job).add_comment("Info", escape(_("{0} billed the contractor's pay on draft {1}.").format(
            frappe.utils.get_fullname(), invoice.name)))
    from projectit.contractor_pay import _owners
    ops.notify(_owners(contractor), _("Your bill {0} is being processed").format(invoice.name), "Techy Contractor", contractor)
    return {"contractor": contractor, "contractor_name": con.contractor_name, "invoice": invoice.name,
        "grand_total": invoice.grand_total}


@frappe.whitelist(methods=["POST"])
def create_bills(up_to=None, contractors=None):
    """One draft Purchase Invoice for each chosen contractor, with their approved lines up to `up_to`."""
    _require()
    up_to = getdate(up_to or nowdate())
    names = frappe.parse_json(contractors) if isinstance(contractors, str) else (contractors or [])
    names = list(dict.fromkeys(names))
    if not names or len(names) > 200:
        frappe.throw(_("Choose the contractors to bill."))
    made, failed = [], []
    for contractor in names:
        rows = frappe.get_all(LINE, filters={"contractor": contractor, "status": "Approved",
            "purchase_invoice": ["is", "not set"]}, fields=contractor_pay.LINE_FIELDS, order_by="approved_on asc",
            limit_page_length=0)
        lines = [frappe._dict(r) for r in _due(rows, up_to)]
        if not lines:
            continue
        try:
            # One savepoint per contractor: a problem with one bill never undoes the others.
            frappe.db.savepoint("techy_payout")
            made.append(_bill(contractor, lines))
        except frappe.ValidationError as error:
            frappe.db.rollback(save_point="techy_payout")
            failed.append({"contractor": contractor, "error": str(error)})
    return {"bills": made, "failed": failed, "preview": preview(up_to)}


def release_lines(doc, method=None):
    """Purchase Invoice cancelled or deleted: its lines are approved again, for the next payout run."""
    names = frappe.get_all(LINE, filters={"purchase_invoice": doc.name}, pluck="name")
    for name in names:
        frappe.db.set_value(LINE, name, {"status": "Approved", "purchase_invoice": None})


@frappe.whitelist()
def owed():
    """What we owe each contractor: approved but not yet billed, and billed but not yet paid."""
    _require()
    rows = frappe.get_all("Techy Contractor", fields=["name", "contractor_name", "pay_cycle"], order_by="contractor_name asc",
        limit_page_length=0)
    owed = contractor_pay.owed_by_contractor([r.name for r in rows])
    out = []
    for r in rows:
        o = owed.get(r.name) or {}
        if o.get("approved") or o.get("billed"):
            out.append({**r, **o, "total": round(flt(o.get("approved")) + flt(o.get("billed")), 2)})
    return {"rows": out, "approved": round(sum(r["approved"] for r in out), 2),
        "billed": round(sum(r["billed"] for r in out), 2), "currency": frappe.db.get_default("currency")}


# The contractor report -----------------------------------------------------------------------------------------

@frappe.whitelist()
def report(days=90):
    """Per contractor in the period: jobs done, on time, sent back for rework, average job cost, paid."""
    ops.require_manager()
    days = frappe.utils.cint(days) if frappe.utils.cint(days) in (30, 90, 180, 365) else 90
    end = getdate(nowdate())
    start = getdate(add_days(end, 1 - days))
    jobs = frappe.get_all("Task", filters={"custom_contractor": ["is", "set"], "custom_work_order": 1,
        "parent_task": ["is", "not set"], "status": "Completed",
        "custom_completed_at": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]},
        fields=["name", "custom_contractor", "exp_end_date", "custom_completed_at"], limit_page_length=0)
    names = [j.name for j in jobs]
    reworked = set(frappe.get_all("Comment", filters={"reference_doctype": "Task", "reference_name": ["in", names or [""]],
        "content": ["like", "Sent back%"]}, pluck="reference_name")) if names else set()
    costs = contractor_pay.job_costs(names)
    declined = dict(frappe.db.sql("""SELECT custom_contractor, COUNT(*) FROM `tabTask` WHERE custom_contractor_state = 'Declined'
        AND modified BETWEEN %s AND %s GROUP BY custom_contractor""", (f"{start} 00:00:00", f"{end} 23:59:59")))
    paid_rows = frappe.get_all(LINE, filters={"status": "Billed", "purchase_invoice": ["is", "set"]},
        fields=["contractor", "pay_type", "amount", "purchase_invoice", "status"], limit_page_length=0)
    invoices = contractor_pay._invoice_states(r.purchase_invoice for r in paid_rows)
    paid = {}
    for r in paid_rows:
        inv = invoices.get(r.purchase_invoice)
        if contractor_pay.shown_status(r, invoices) == "Paid" and inv and start <= getdate(inv.posting_date) <= end:
            paid[r.contractor] = paid.get(r.contractor, 0) + contractor_pay.signed(r)
    rows = {}
    for c in frappe.get_all("Techy Contractor", fields=["name", "contractor_name", "enabled"], limit_page_length=0):
        rows[c.name] = {"contractor": c.name, "contractor_name": c.contractor_name, "jobs": 0, "on_time": 0,
            "late": 0, "reworked": 0, "cost": 0.0, "declined": declined.get(c.name, 0), "paid": round(paid.get(c.name, 0), 2),
            "enabled": c.enabled}
    for j in jobs:
        r = rows.get(j.custom_contractor)
        if not r:
            continue
        r["jobs"] += 1
        if j.exp_end_date:
            if getdate(j.custom_completed_at) <= getdate(j.exp_end_date):
                r["on_time"] += 1
            else:
                r["late"] += 1
        r["reworked"] += 1 if j.name in reworked else 0
        r["cost"] += costs.get(j.name, 0)
    out = []
    for r in rows.values():
        if not (r["jobs"] or r["paid"] or r["declined"]):
            continue
        dated = r["on_time"] + r["late"]
        r["on_time_rate"] = round(100 * r["on_time"] / dated) if dated else None
        r["rework_rate"] = round(100 * r["reworked"] / r["jobs"]) if r["jobs"] else None
        r["average_cost"] = round(r["cost"] / r["jobs"], 2) if r["jobs"] else None
        r["cost"] = round(r["cost"], 2)
        out.append(r)
    out.sort(key=lambda r: (-r["jobs"], r["contractor_name"] or ""))
    return {"rows": out, "days": days, "start": start, "end": end, "owed": owed(), "currency": frappe.db.get_default("currency")}
