"""What we pay contractors, and when: pay lines (Techy Contractor Pay Line).

Each line is one thing we owe a contractor:

- **Fixed**: an agreed price for the job (quantity 1, or several of a thing at a fixed price).
- **Hourly**: hours times the rate. The hours come from their confirmed site visits (*Check-in*) or from the job
  timer (*Timer*), counted for the contractor's own people only, when the job is approved.
- **Per unit**: a rate per piece, metre, filter… from their rate card. Their crew report the quantity, the manager
  confirms it.
- **Milestone**: part of a project's contract sum (a percentage or an amount), approved when its proof job is done.
- **Reimbursement**: something they bought on site that we pay back (Techy Contractor Purchase).
- **Deduction**: materials we issued that were neither used nor returned, taken off their bill.

A line is *Draft* until the work is approved. A manager completing the job (the existing review) approves its lines,
and they become *Approved* (to be paid in the next payout run, see projectit.payouts). Sending the job back for rework
keeps them Draft; reopening a completed job turns lines that are not yet billed back to Draft. *On hold* keeps an
approved line out of payout runs. *Billed* lines are on a Purchase Invoice.

Only managers and the contractor's owner see amounts. Leads and crew see what they need to do the work: the
per-unit quantities to report, and the purchases and materials on their jobs.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from projectit import contractors, ops

LINE = "Techy Contractor Pay Line"
PURCHASE = "Techy Contractor Purchase"
JOB_TYPES = ("Fixed", "Hourly", "Per unit")
EARNING = ("Fixed", "Hourly", "Per unit", "Milestone", "Reimbursement")
LINE_FIELDS = ["name", "contractor", "contractor_name", "work_order", "project", "pay_type", "description", "status",
    "unit", "rate", "hours_from", "reported_qty", "qty", "percent", "contract_sum", "proof_work_order", "amount",
    "approved_by", "approved_on", "purchase_invoice", "purchase", "part_usage", "queried", "query_note", "notes",
    "modified"]
PURCHASE_FIELDS = ["name", "contractor", "user", "work_order", "project", "description", "qty", "amount", "bought_on",
    "status", "treatment", "chargeable", "approved_by", "rejection_reason", "pay_line", "offline", "creation"]


def signed(line):
    """The line's effect on the bill: deductions count against it."""
    return -flt(line.amount) if line.pay_type == "Deduction" else flt(line.amount)


# Access --------------------------------------------------------------------------------------------------------

def _job(work_order, for_update=False):
    doc = frappe.get_doc("Task", work_order, for_update=for_update)
    if not doc.get("custom_work_order") or doc.get("parent_task"):
        frappe.throw(_("{0} is not a work order.").format(work_order))
    return doc


def _viewer(doc):
    """('manager' | 'owner' | 'crew', membership) for someone who may see this job's pay page."""
    member = contractors.membership()
    if member:
        if doc.get("custom_contractor") != member.contractor or not contractors.sees_job(doc):
            frappe.throw(_("This job is not yours."), frappe.PermissionError)
        return ("owner" if contractors.sees_pay(member) else "crew"), member
    ops.require_manager()
    return "manager", None


def _redact(line, who):
    row = {f: line.get(f) for f in LINE_FIELDS}
    if who == "crew":
        for f in ("rate", "amount", "contract_sum", "percent", "approved_by", "purchase_invoice", "query_note"):
            row.pop(f, None)
    return row


# A job's pay ---------------------------------------------------------------------------------------------------

def _lines(work_order):
    return frappe.get_all(LINE, filters={"work_order": work_order, "status": ["!=", "Cancelled"]}, fields=LINE_FIELDS,
        order_by="creation asc", limit_page_length=0)


def hours(work_order, contractor, source):
    """Hours of the contractor's own people on a job: confirmed site visits, or the job timer."""
    if source == "Timer":
        from projectit import timer
        people = {m.user for m in contractors.members(contractor, enabled_only=False)}
        logged = timer.hours_by_person([work_order]).get(work_order) or {}
        return round(sum(h for user, h in logged.items() if user in people), 2)
    from projectit import site_visits
    return round(sum(site_visits.confirmed_hours(work_order, contractor).values()), 2)


def materials(work_order):
    """Parts issued from our stock to the job: issued, used and returned, and what is missing."""
    rows = frappe.get_all("Techy Part Usage", filters={"work_order": work_order, "status": "Issued"},
        fields=["name", "item_code", "item_name", "qty", "uom", "qty_used", "qty_returned", "materials_reported",
            "valuation_rate"], order_by="creation asc", limit_page_length=0)
    deducted = {l.part_usage for l in frappe.get_all(LINE, filters={"work_order": work_order, "pay_type": "Deduction",
        "status": ["!=", "Cancelled"]}, fields=["part_usage"])}
    for r in rows:
        r.missing = max(0.0, round(flt(r.qty) - flt(r.qty_used) - flt(r.qty_returned), 3)) if r.materials_reported else 0
        r.deducted = r.name in deducted
    return rows


@frappe.whitelist()
def job_pay(work_order):
    """A contractor job's pay page: the agreed lines, hours so far, purchases and materials."""
    doc = _job(work_order)
    who, member = _viewer(doc)
    contractor = doc.get("custom_contractor")
    if not contractor:
        return {"contractor": None, "who": who}
    lines = _lines(doc.name)
    purchases = frappe.get_all(PURCHASE, filters={"work_order": doc.name}, fields=PURCHASE_FIELDS,
        order_by="creation desc", limit_page_length=0)
    if who == "crew" and not contractors.runs_jobs(member):
        purchases = [p for p in purchases if p.user == frappe.session.user]
    for p in purchases:
        p.full_name = frappe.utils.get_fullname(p.user)
        p.receipts = [f.file_url for f in ops.files(PURCHASE, p.name)]
        if who == "crew" and not contractors.runs_jobs(member):
            p.pop("rejection_reason", None)
    rates = []
    if who == "manager":
        rates = frappe.get_all("Techy Contractor Rate", filters={"parent": contractor, "parenttype": "Techy Contractor"},
            fields=["activity", "unit", "rate", "item_code"], order_by="idx asc")
    closed = doc.status in ("Completed", "Cancelled")
    return {"who": who, "contractor": contractors.job_contractor(doc.name), "status": doc.status,
        "lines": [_redact(l, who) for l in lines], "rates": rates,
        "hours": {"Check-in": hours(doc.name, contractor, "Check-in"), "Timer": hours(doc.name, contractor, "Timer")},
        "total": round(sum(signed(l) for l in lines), 2) if who != "crew" else None,
        "purchases": purchases, "materials": materials(doc.name), "can_edit": who == "manager",
        "can_report": who != "manager" and doc.get("custom_contractor_state") == "Accepted" and not closed,
        "currency": frappe.db.get_default("currency")}


def _clean_line(v, contractor):
    pay_type = v.get("pay_type")
    if pay_type not in JOB_TYPES:
        frappe.throw(_("Choose fixed, hourly or per unit."))
    description = ops.text(v.get("description"), "what the pay is for", 140)
    rate = flt(v.get("rate"))
    if rate <= 0:
        frappe.throw(_("Enter a rate above zero for {0}.").format(description))
    qty = flt(v.get("qty")) if v.get("qty") not in (None, "") else (1 if pay_type == "Fixed" else 0)
    if qty < 0:
        frappe.throw(_("Quantities cannot be negative."))
    hours_from = v.get("hours_from") or ("Check-in" if pay_type == "Hourly" else None)
    if pay_type == "Hourly" and hours_from not in ("Check-in", "Timer"):
        frappe.throw(_("Choose whether hours come from check-in or the job timer."))
    return {"pay_type": pay_type, "description": description, "rate": rate, "qty": qty,
        "unit": ops.text(v.get("unit"), "the unit", 40, required=False) or {"Hourly": "Hour", "Fixed": "Job"}.get(pay_type, ""),
        "hours_from": hours_from if pay_type == "Hourly" else None, "amount": round(rate * qty, 2) if pay_type != "Hourly" else 0,
        "notes": ops.text(v.get("notes"), "notes", 1000, required=False)}


@frappe.whitelist(methods=["POST"])
def save_pay_lines(work_order, lines):
    """A manager sets what the contractor is paid for a job (its fixed, hourly and per-unit lines). Lines already
    approved or billed are kept; Draft ones are replaced by `lines` (pass a line's `name` to keep and change it)."""
    ops.require_manager()
    doc = _job(work_order, for_update=True)
    contractor = doc.get("custom_contractor")
    if not contractor:
        frappe.throw(_("Give the job to a contractor first."))
    if doc.status == "Cancelled":
        frappe.throw(_("This job was cancelled."))
    values = frappe.parse_json(lines) if isinstance(lines, str) else (lines or [])
    if len(values) > 50:
        frappe.throw(_("Use at most 50 pay lines on a job."))
    existing = {l.name: l for l in frappe.get_all(LINE, filters={"work_order": doc.name, "pay_type": ["in", JOB_TYPES],
        "status": ["!=", "Cancelled"]}, fields=["name", "status"])}
    kept = set()
    completed = doc.status == "Completed"
    for v in values:
        clean = _clean_line(v, contractor)
        name = v.get("name")
        if name and name in existing:
            if existing[name].status != "Draft":
                kept.add(name)
                continue  # approved or billed lines are not changed here
            line = frappe.get_doc(LINE, name)
            line.update(clean)
            line.save(ignore_permissions=True)
            kept.add(name)
        else:
            line = frappe.get_doc({"doctype": LINE, "contractor": contractor, "work_order": doc.name,
                "project": doc.project, "status": "Draft", **clean})
            line.insert(ignore_permissions=True)
            kept.add(line.name)
            if completed:
                _approve(line, doc)
    for name, row in existing.items():
        if name not in kept and row.status == "Draft":
            frappe.db.set_value(LINE, name, "status", "Cancelled")
    return job_pay(doc.name)


@frappe.whitelist(methods=["POST"])
def report_quantity(line, qty):
    """The contractor's crew report how many they did, for a per-unit line (the manager confirms it on approval)."""
    row = frappe.get_doc(LINE, line, for_update=True)
    doc = _job(row.work_order)
    who, member = _viewer(doc)
    if who == "manager":
        frappe.throw(_("Managers change the quantity on the job's pay lines."))
    if row.pay_type != "Per unit" or row.status != "Draft":
        frappe.throw(_("This line's quantity can no longer be changed."))
    contractors.check_can_work(doc)
    qty = flt(qty)
    if qty < 0 or qty > 100000:
        frappe.throw(_("Enter the quantity done."))
    row.reported_qty = qty
    row.save(ignore_permissions=True)
    doc.add_comment("Info", escape(_("{0} reported {1} {2} for {3}.").format(frappe.utils.get_fullname(), qty,
        row.unit or "", row.description)))
    return job_pay(doc.name)


# Approval (the job's review) -------------------------------------------------------------------------------------

def _approve(line, job):
    if line.pay_type == "Hourly":
        line.qty = hours(job.name, line.contractor, line.hours_from or "Check-in")
    elif line.pay_type == "Per unit" and not flt(line.qty):
        line.qty = flt(line.reported_qty)
    if line.pay_type in JOB_TYPES:
        line.amount = round(flt(line.rate) * flt(line.qty), 2)
    line.status = "Approved"
    line.approved_by = frappe.session.user
    line.approved_on = now_datetime()
    line.save(ignore_permissions=True)


def on_task_update(doc, method=None):
    """Task hook: completing a contractor's job approves its pay; reopening it or cancelling it undoes that."""
    if not doc.get("custom_contractor") or not doc.get("custom_work_order") or not doc.has_value_changed("status"):
        return
    before = doc.get_doc_before_save()
    was = before.status if before else None
    if doc.status == "Completed":
        approved = 0
        for name in frappe.get_all(LINE, filters={"work_order": doc.name, "status": "Draft",
                "pay_type": ["!=", "Milestone"]}, pluck="name"):
            _approve(frappe.get_doc(LINE, name), doc)
            approved += 1
        if approved:
            doc.add_comment("Info", escape(_("{0} approved the contractor's pay for this job.").format(
                frappe.utils.get_fullname())))
    elif was == "Completed":
        for name in frappe.get_all(LINE, filters={"work_order": doc.name, "status": ["in", ["Approved", "On hold"]],
                "pay_type": ["!=", "Milestone"]}, pluck="name"):
            frappe.db.set_value(LINE, name, {"status": "Draft", "approved_by": None, "approved_on": None})
    if doc.status == "Cancelled":
        cancel_draft(doc.name)


def cancel_draft(work_order):
    """Agreed pay that was never earned (the job was cancelled, or taken back from the contractor)."""
    for name in frappe.get_all(LINE, filters={"work_order": work_order, "status": "Draft"}, pluck="name"):
        frappe.db.set_value(LINE, name, "status", "Cancelled")


def check_hours_open(work_order, contractor):
    """A visit's hours cannot change once an hourly line counting them is approved or billed."""
    if work_order and frappe.db.exists(LINE, {"work_order": work_order, "contractor": contractor, "pay_type": "Hourly",
            "hours_from": "Check-in", "status": ["in", ["Approved", "On hold", "Billed"]]}):
        frappe.throw(_("The hours on this job are already approved for pay. Reopen the job to change them."))


@frappe.whitelist(methods=["POST"])
def hold_line(line, hold=1, note=None):
    """Keep an approved line out of payout runs (or let it back in)."""
    ops.require_manager()
    row = frappe.get_doc(LINE, line, for_update=True)
    if cint(hold):
        if row.status != "Approved":
            frappe.throw(_("Only approved lines can be held."))
        row.status = "On hold"
    else:
        if row.status != "On hold":
            frappe.throw(_("This line is not on hold."))
        row.status = "Approved"
    note = ops.text(note, "the note", 1000, required=False)
    if note:
        row.notes = "\n".join(filter(None, [row.notes, note]))
    row.save(ignore_permissions=True)
    return {f: row.get(f) for f in LINE_FIELDS}


# Milestones ----------------------------------------------------------------------------------------------------

@frappe.whitelist()
def milestones(project):
    ops.require_manager()
    rows = frappe.get_all(LINE, filters={"project": project, "pay_type": "Milestone", "status": ["!=", "Cancelled"]},
        fields=LINE_FIELDS, order_by="creation asc", limit_page_length=0)
    proofs = dict(frappe.get_all("Task", filters={"name": ["in", [r.proof_work_order for r in rows if r.proof_work_order] or [""]]},
        fields=["name", "status"], as_list=True))
    for r in rows:
        r.proof_status = proofs.get(r.proof_work_order)
    jobs = frappe.get_all("Task", filters={"project": project, "custom_work_order": 1, "parent_task": ["is", "not set"],
        "status": ["!=", "Cancelled"]}, fields=["name", "subject", "status"], order_by="creation asc", limit_page_length=200)
    return {"milestones": rows, "jobs": jobs, "contractors": contractors.options(),
        "currency": frappe.db.get_default("currency")}


@frappe.whitelist(methods=["POST"])
def save_milestone(project, contractor, description, percent=None, contract_sum=None, amount=None,
        proof_work_order=None, name=None):
    """A part of a project's contract sum, paid when its proof job is done (or when a manager approves it)."""
    ops.require_manager()
    if not frappe.db.exists("Project", project):
        frappe.throw(_("Choose the project."))
    if not frappe.db.exists("Techy Contractor", {"name": contractor, "enabled": 1}):
        frappe.throw(_("Choose an active contractor."))
    description = ops.text(description, "the milestone", 140)
    percent, contract_sum, amount = flt(percent), flt(contract_sum), flt(amount)
    if percent:
        if not 0 < percent <= 100 or contract_sum <= 0:
            frappe.throw(_("Enter a percentage up to 100 and the contract sum."))
        amount = round(contract_sum * percent / 100, 2)
    if amount <= 0:
        frappe.throw(_("Enter the milestone's amount, or a percentage of the contract sum."))
    if proof_work_order and frappe.db.get_value("Task", proof_work_order, "project") != project:
        frappe.throw(_("Choose a job of this project."))
    values = {"contractor": contractor, "project": project, "pay_type": "Milestone", "description": description,
        "percent": percent or None, "contract_sum": contract_sum or None, "amount": amount, "qty": 1, "rate": amount,
        "unit": "Milestone", "proof_work_order": proof_work_order or None}
    if name:
        row = frappe.get_doc(LINE, name, for_update=True)
        if row.pay_type != "Milestone" or row.status != "Draft":
            frappe.throw(_("Only milestones not yet approved can be changed."))
        row.update(values)
        row.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": LINE, "status": "Draft", **values}).insert(ignore_permissions=True)
    return milestones(project)


@frappe.whitelist(methods=["POST"])
def approve_milestone(name):
    ops.require_manager()
    row = frappe.get_doc(LINE, name, for_update=True)
    if row.pay_type != "Milestone" or row.status != "Draft":
        frappe.throw(_("This milestone is not waiting for approval."))
    if row.proof_work_order and frappe.db.get_value("Task", row.proof_work_order, "status") != "Completed":
        frappe.throw(_("Complete its job ({0}) first.").format(row.proof_work_order))
    row.update({"status": "Approved", "approved_by": frappe.session.user, "approved_on": now_datetime()})
    row.save(ignore_permissions=True)
    ops.notify(_owners(row.contractor), _("Milestone approved: {0}").format(row.description), LINE, row.name)
    return milestones(row.project)


@frappe.whitelist(methods=["POST"])
def remove_milestone(name):
    ops.require_manager()
    row = frappe.get_doc(LINE, name)
    if row.pay_type != "Milestone" or row.status != "Draft":
        frappe.throw(_("Only milestones not yet approved can be removed."))
    frappe.db.set_value(LINE, name, "status", "Cancelled")
    return milestones(row.project)


def _owners(contractor):
    return [m.user for m in contractors.members(contractor) if m.member_role == "Owner"]


# Bought on site ------------------------------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def log_purchase(work_order, description, amount, photo, qty=1, at=None):
    """Something the crew bought on site for the job, with a photo of the receipt."""
    doc = _job(work_order)
    who, member = _viewer(doc)
    if who == "manager":
        frappe.throw(_("Purchases are logged by the contractor."))
    contractors.check_can_work(doc)
    if doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("This job is closed."))
    amount, qty = flt(amount), flt(qty) or 1
    if amount <= 0 or amount > 10000000:
        frappe.throw(_("Enter what you paid."))
    bought_on = nowdate()
    offline = False
    if at:
        from projectit.attendance import _when
        when, offline = _when(at)
        bought_on = getdate(when)
    row = frappe.get_doc({"doctype": PURCHASE, "contractor": member.contractor, "user": frappe.session.user,
        "work_order": doc.name, "project": doc.project, "description": ops.text(description, "what you bought", 140),
        "qty": qty, "amount": amount, "bought_on": bought_on, "status": "Submitted",
        "treatment": doc.get("custom_contractor_purchases") or member.purchases or "Reimbursed", "offline": 1 if offline else 0})
    row.insert(ignore_permissions=True)
    ops.save_photo(PURCHASE, row.name, photo, "receipt", ignore_permissions=True)
    from projectit.meters import _managers
    ops.notify(_managers(), _("Bought on site for {0}: {1}").format(doc.subject, row.description), "Task", doc.name)
    return job_pay(doc.name)


def _reimburse(purchase, job):
    line = frappe.get_doc({"doctype": LINE, "contractor": purchase.contractor, "work_order": purchase.work_order,
        "project": purchase.project, "pay_type": "Reimbursement", "description": _("Bought on site: {0}").format(
            purchase.description)[:140], "qty": 1, "rate": purchase.amount, "amount": purchase.amount, "unit": "",
        "purchase": purchase.name, "status": "Draft"})
    line.insert(ignore_permissions=True)
    if job.status == "Completed":
        _approve(line, job)
    return line.name


@frappe.whitelist(methods=["POST"])
def review_purchase(name, approve, treatment=None, chargeable=0, reason=None):
    """A manager accepts or rejects a purchase, decides whether we pay it back and whether the customer pays for it."""
    ops.require_manager()
    row = frappe.get_doc(PURCHASE, name, for_update=True)
    job = _job(row.work_order)
    if row.status != "Submitted":
        frappe.throw(_("This purchase was already reviewed."))
    if cint(approve):
        treatment = treatment or row.treatment
        if treatment not in ("Reimbursed", "Included in price"):
            frappe.throw(_("Choose whether we pay it back."))
        row.update({"status": "Approved", "treatment": treatment, "chargeable": 1 if cint(chargeable) else 0,
            "approved_by": frappe.session.user})
        if treatment == "Reimbursed":
            row.pay_line = _reimburse(row, job)
    else:
        row.update({"status": "Rejected", "approved_by": frappe.session.user,
            "rejection_reason": ops.text(reason, "the reason", 1000)})
        ops.notify([row.user], _("Not accepted: {0}").format(row.description), "Task", job.name)
    row.save(ignore_permissions=True)
    return job_pay(job.name)


def chargeable_purchases(work_order):
    """Approved purchases the customer pays for (added to the job's invoice, see billing)."""
    return frappe.get_all(PURCHASE, filters={"work_order": work_order, "status": "Approved", "chargeable": 1},
        fields=["name", "description", "qty", "amount"], order_by="creation asc")


# Materials we issued -------------------------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def report_materials(work_order, rows):
    """At the end of the job the crew say how much of each issued part they used and returned."""
    doc = _job(work_order)
    who, member = _viewer(doc)
    if who == "manager":
        frappe.throw(_("The contractor reports what was used."))
    contractors.check_can_work(doc)
    values = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
    issued = {r.name: r for r in materials(doc.name)}
    for v in values:
        part = issued.get(v.get("name"))
        if not part:
            frappe.throw(_("This part was not issued to the job."))
        if part.deducted:
            continue
        used, returned = flt(v.get("used")), flt(v.get("returned"))
        if used < 0 or returned < 0 or used + returned > flt(part.qty) + 1e-9:
            frappe.throw(_("{0}: used and returned together cannot be more than the {1} issued.").format(
                part.item_name or part.item_code, flt(part.qty)))
        frappe.db.set_value("Techy Part Usage", part.name, {"qty_used": used, "qty_returned": returned,
            "materials_reported": 1})
    doc.add_comment("Info", escape(_("{0} reported the materials used and returned.").format(frappe.utils.get_fullname())))
    return job_pay(doc.name)


@frappe.whitelist(methods=["POST"])
def deduct_missing(work_order, part):
    """Take materials that were neither used nor returned off the contractor's bill, at our stock cost."""
    ops.require_manager()
    doc = _job(work_order)
    row = next((m for m in materials(doc.name) if m.name == part), None)
    if not row:
        frappe.throw(_("This part was not issued to the job."))
    if row.deducted:
        frappe.throw(_("This part was already deducted."))
    if row.missing <= 0:
        frappe.throw(_("Nothing is missing for this part."))
    amount = round(row.missing * flt(row.valuation_rate), 2)
    if amount <= 0:
        frappe.throw(_("This part has no stock cost to deduct."))
    line = frappe.get_doc({"doctype": LINE, "contractor": doc.custom_contractor, "work_order": doc.name,
        "project": doc.project, "pay_type": "Deduction", "description": _("Not returned: {0} × {1}").format(
            row.missing, row.item_name or row.item_code)[:140], "qty": row.missing, "rate": row.valuation_rate,
        "amount": amount, "unit": row.uom, "part_usage": row.name, "status": "Draft"})
    line.insert(ignore_permissions=True)
    if doc.status == "Completed":
        _approve(line, doc)
    ops.notify(_owners(doc.custom_contractor), _("Deduction on {0}: {1}").format(doc.subject, line.description),
        "Task", doc.name)
    return job_pay(doc.name)


# Statements ----------------------------------------------------------------------------------------------------

def _invoice_states(names):
    names = [n for n in names if n]
    return {r.name: r for r in frappe.get_all("Purchase Invoice", filters={"name": ["in", names or [""]]},
        fields=["name", "docstatus", "status", "outstanding_amount", "grand_total", "posting_date"])}


def shown_status(line, invoices):
    """Draft, Approved, On hold, Billed or Paid (a billed line whose Purchase Invoice is paid)."""
    if line.status == "Billed":
        inv = invoices.get(line.purchase_invoice)
        if inv and inv.docstatus == 1 and flt(inv.outstanding_amount) <= 0:
            return "Paid"
    return line.status


@frappe.whitelist()
def statement(contractor=None, start=None, end=None):
    """A contractor's pay: lines with their state, and totals. The owner sees their own; managers any."""
    member = contractors.membership()
    if member:
        contractors.require_member(("Owner",))
        contractor = member.contractor
    else:
        ops.require_manager()
        if not contractor:
            frappe.throw(_("Choose a contractor."))
    end = getdate(end or nowdate())
    start = getdate(start or frappe.utils.add_days(end, -89))
    rows = frappe.get_all(LINE, filters={"contractor": contractor, "status": ["!=", "Cancelled"]},
        fields=LINE_FIELDS + ["creation"], order_by="creation desc", limit_page_length=0)
    invoices = _invoice_states(r.purchase_invoice for r in rows)
    shown = []
    totals = {"Draft": 0, "Approved": 0, "On hold": 0, "Billed": 0, "Paid": 0}
    for r in rows:
        r.shown = shown_status(r, invoices)
        totals[r.shown] = round(totals[r.shown] + signed(r), 2)
        when = getdate(r.approved_on or r.creation)
        # Everything not yet paid is shown whatever its date; paid lines only in the period.
        if r.shown != "Paid" or start <= when <= end:
            shown.append(r)
    subjects = dict(frappe.get_all("Task", filters={"name": ["in", list({r.work_order for r in shown if r.work_order}) or [""]]},
        fields=["name", "subject"], as_list=True))
    projects = dict(frappe.get_all("Project", filters={"name": ["in", list({r.project for r in shown if r.project}) or [""]]},
        fields=["name", "project_name"], as_list=True))
    for r in shown:
        r.subject, r.project_name = subjects.get(r.work_order), projects.get(r.project)
        inv = invoices.get(r.purchase_invoice)
        r.invoice_date = inv.posting_date if inv else None
    paid_in_period = round(sum(signed(r) for r in shown if r.shown == "Paid"), 2)
    con = frappe.db.get_value("Techy Contractor", contractor, ["name", "contractor_name", "pay_cycle", "supplier"], as_dict=True)
    return {"contractor": con, "lines": shown, "totals": totals, "paid_in_period": paid_in_period, "start": start,
        "end": end, "currency": frappe.db.get_default("currency"), "manager": not member}


@frappe.whitelist(methods=["POST"])
def query_line(line, note):
    """The owner questions a line: the job's managers are told."""
    member = contractors.require_member(("Owner",))
    row = frappe.get_doc(LINE, line, for_update=True)
    if row.contractor != member.contractor:
        frappe.throw(_("This is not your line."), frappe.PermissionError)
    note = ops.text(note, "your question", 1000)
    row.queried, row.query_note = 1, "\n".join(filter(None, [row.query_note, f"{frappe.utils.get_fullname()}: {note}"]))
    row.save(ignore_permissions=True)
    from projectit.meters import _managers
    target = ("Task", row.work_order) if row.work_order else (LINE, row.name)
    ops.notify(_managers(), _("{0} queried pay: {1}").format(member.contractor_name, row.description), *target)
    if row.work_order:
        frappe.get_doc("Task", row.work_order).add_comment("Comment", escape(_("Pay query on “{0}”: {1}").format(
            row.description, note)))
    return {f: row.get(f) for f in LINE_FIELDS}


@frappe.whitelist(methods=["POST"])
def answer_query(line, note):
    ops.require_manager()
    row = frappe.get_doc(LINE, line, for_update=True)
    note = ops.text(note, "your answer", 1000)
    row.queried = 0
    row.query_note = "\n".join(filter(None, [row.query_note, f"{frappe.utils.get_fullname()}: {note}"]))
    row.save(ignore_permissions=True)
    ops.notify(_owners(row.contractor), _("Answer about {0}").format(row.description), LINE, row.name)
    return {f: row.get(f) for f in LINE_FIELDS}


@frappe.whitelist()
def queries():
    """Open pay queries, for managers."""
    ops.require_manager()
    return frappe.get_all(LINE, filters={"queried": 1, "status": ["!=", "Cancelled"]}, fields=LINE_FIELDS,
        order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def download_statement(contractor=None, start=None, end=None):
    """The statement as a PDF."""
    data = statement(contractor, start, end)
    from frappe.utils.pdf import get_pdf
    company = frappe.db.get_single_value("Global Defaults", "default_company") or ""
    html = frappe.render_template("projectit/templates/contractor_statement.html", {"data": data, "company": company,
        "printed": frappe.utils.format_datetime(now_datetime(), "dd MMM yyyy HH:mm"),
        "fmt": lambda v: frappe.utils.fmt_money(v, currency=data["currency"])})
    frappe.local.response.filename = f"Statement {data['contractor'].contractor_name} {data['end']}.pdf"
    frappe.local.response.filecontent = get_pdf(html, {"page-size": "A4", "encoding": "UTF-8"})
    frappe.local.response.type = "pdf"


# For other modules ---------------------------------------------------------------------------------------------

def job_totals(work_orders):
    """{job: agreed and earned pay so far} (managers' and owners' lists)."""
    names = [n for n in work_orders if n]
    out = {}
    for r in frappe.get_all(LINE, filters={"work_order": ["in", names or [""]], "status": ["!=", "Cancelled"]},
            fields=["work_order", "pay_type", "amount", "status"], limit_page_length=0):
        out[r.work_order] = round(out.get(r.work_order, 0) + signed(r), 2)
    return out


def job_costs(work_orders):
    """{job: what the contractor is paid for it} for jobs with approved or billed pay: what project and machine costs
    count instead of the staff labour cost rate (see reports)."""
    names = [n for n in work_orders if n]
    out = {}
    for r in frappe.get_all(LINE, filters={"work_order": ["in", names or [""]], "status": ["in", ["Approved", "On hold", "Billed"]],
            "pay_type": ["!=", "Milestone"]}, fields=["work_order", "pay_type", "amount"], limit_page_length=0):
        out[r.work_order] = round(out.get(r.work_order, 0) + signed(r), 2)
    return out


def owed_by_contractor(contractor_names):
    """{contractor: {"approved": not yet billed, "billed": billed and not yet paid}}."""
    names = [n for n in contractor_names if n]
    out = {n: {"approved": 0, "billed": 0} for n in names}
    rows = frappe.get_all(LINE, filters={"contractor": ["in", names or [""]], "status": ["in", ["Approved", "Billed"]]},
        fields=["contractor", "pay_type", "amount", "status", "purchase_invoice"], limit_page_length=0)
    invoices = _invoice_states(r.purchase_invoice for r in rows)
    for r in rows:
        if shown_status(r, invoices) == "Paid":
            continue
        key = "approved" if r.status == "Approved" else "billed"
        out[r.contractor][key] = round(out[r.contractor][key] + signed(r), 2)
    return out
