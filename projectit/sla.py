"""Response times promised in service contracts: on site within so many hours, and fixed within so many.

A contract may promise a response time and a fix time for breakdowns. A repair (Corrective) job on a machine
under an active contract with a promise gets its deadlines when it is created: respond by, and fix by, counted
from when the customer's request came in (or from when the job was opened). The response is met when work
starts on the job (it is first set to Working); the fix is met when the job is completed by its deadline.

Every 10 minutes the scheduler warns the job's technicians and the managers an hour before a response is due,
and again once it is missed. Reports show the promises kept per contract.
"""
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, format_datetime, get_datetime, getdate, now_datetime

from projectit import ops

WARN_BEFORE = timedelta(hours=1)
CONTRACT_FIELDS = ["name", "title", "customer_name", "status", "start_date", "end_date", "response_hours", "fix_hours"]


def contract_for(doc):
    """The active contract with a promise covering this job, if any."""
    from projectit import contracts
    name = doc.get("custom_service_contract")
    if not name and doc.get("custom_equipment"):
        name = frappe.db.get_value("Techy Equipment", doc.custom_equipment, "service_contract")
    if not name:
        return None
    row = frappe.db.get_value("Techy Service Contract", name, CONTRACT_FIELDS, as_dict=True)
    if not row or contracts.state(row) != "Active" or not (flt(row.response_hours) or flt(row.fix_hours)):
        return None
    return row


def stamp(doc):
    """Task validate: give a new repair on a covered machine its deadlines (once)."""
    if not doc.get("custom_work_order") or doc.get("custom_work_category") != "Corrective" \
            or doc.get("custom_respond_by") or doc.get("custom_fix_by") or doc.get("custom_sla_contract"):
        return
    if doc.get("status") in ("Completed", "Cancelled") and not doc.is_new():
        return
    contract = contract_for(doc)
    if not contract:
        return
    start = None
    if doc.get("custom_work_request"):
        start = frappe.db.get_value("Issue", doc.custom_work_request, "creation")
    start = get_datetime(start or doc.get("creation") or now_datetime())
    doc.custom_sla_contract = contract.name
    if flt(contract.response_hours):
        doc.custom_respond_by = start + timedelta(hours=flt(contract.response_hours))
    if flt(contract.fix_hours):
        doc.custom_fix_by = start + timedelta(hours=flt(contract.fix_hours))


def _promise(deadline, done_at, now):
    """One promise: due, met or missed, with the hours to go or by how much it was missed."""
    if not deadline:
        return None
    deadline = get_datetime(deadline)
    if done_at:
        done_at = get_datetime(done_at)
        late = (done_at - deadline).total_seconds() / 3600
        return {"by": deadline, "state": "Met" if late <= 0 else "Missed", "hours": round(max(late, 0), 1)}
    left = (deadline - now).total_seconds() / 3600
    return {"by": deadline, "state": "Due" if left >= 0 else "Missed", "hours": round(abs(left), 1),
        "soon": 0 <= left <= WARN_BEFORE.total_seconds() / 3600}


def state(job, now=None):
    """{'respond': promise, 'fix': promise} for a job; a cancelled job keeps no promises."""
    if not (job.get("custom_respond_by") or job.get("custom_fix_by")) or job.get("status") == "Cancelled":
        return None
    now = now or now_datetime()
    done = job.get("custom_completed_at") if job.get("status") == "Completed" else None
    return {"respond": _promise(job.get("custom_respond_by"), job.get("custom_started_at"), now),
        "fix": _promise(job.get("custom_fix_by"), done, now)}


def summary(doc):
    """The job page's promise: deadlines and the contract they come from."""
    current = state(doc)
    if not current:
        return None
    title = frappe.db.get_value("Techy Service Contract", doc.custom_sla_contract, "title") if doc.get("custom_sla_contract") else None
    return {**current, "contract": doc.get("custom_sla_contract"), "contract_title": title}


# Warnings ------------------------------------------------------------------------------------------------------

def _people(name):
    from projectit.meters import _managers
    from projectit.work_orders import _assignees
    return list(dict.fromkeys(list(_assignees([name])[name]) + _managers()))


def check_due():
    """Scheduler (every 10 minutes): warn before a response is due, and when it is missed."""
    now = now_datetime()
    rows = frappe.get_all("Task", filters={"custom_work_order": 1, "status": ["not in", ["Completed", "Cancelled"]],
        "custom_respond_by": ["is", "set"], "custom_started_at": ["is", "not set"], "custom_sla_warned": ["<", 2]},
        fields=["name", "subject", "custom_respond_by", "custom_sla_warned"], limit_page_length=500)
    for row in rows:
        due = get_datetime(row.custom_respond_by)
        level = 2 if now >= due else 1 if due - now <= WARN_BEFORE else 0
        if level <= cint(row.custom_sla_warned):
            continue
        when = format_datetime(due, "HH:mm") if getdate(due) == getdate(now) else format_datetime(due, "dd MMM HH:mm")
        subject = _("Response time missed (due {0}): {1}") if level == 2 else _("Respond by {0}: {1}")
        ops.notify(_people(row.name), subject.format(when, row.subject), "Task", row.name)
        frappe.db.set_value("Task", row.name, "custom_sla_warned", level, update_modified=False)


# Reports -------------------------------------------------------------------------------------------------------

def report(jobs, start, end, now=None):
    """Promises on jobs opened in the period: kept, missed and still due, per contract and in total."""
    now = now or now_datetime()

    def blank():
        return {"jobs": 0, "respond_met": 0, "respond_missed": 0, "respond_due": 0, "fix_met": 0, "fix_missed": 0, "fix_due": 0}

    rows = {}
    total = blank()
    missed = []
    for job in jobs:
        if not job.get("custom_sla_contract") or not (getdate(start) <= getdate(job.creation) <= getdate(end)):
            continue
        current = state(job, now)
        if not current:
            continue
        row = rows.setdefault(job.custom_sla_contract, blank())
        for target in (row, total):
            target["jobs"] += 1
            for kind in ("respond", "fix"):
                if current[kind]:
                    target[f"{kind}_{current[kind]['state'].lower()}"] += 1
        late = [k for k in ("respond", "fix") if current[k] and current[k]["state"] == "Missed"]
        if late:
            missed.append({"name": job.name, "subject": job.subject, "contract": job.custom_sla_contract,
                "missed": late, "late_hours": max(current[k]["hours"] for k in late)})
    names = {r.name: r for r in frappe.get_all("Techy Service Contract", filters={"name": ["in", list(rows)]},
        fields=CONTRACT_FIELDS)} if rows else {}

    def kept(r, kind):
        judged = r[f"{kind}_met"] + r[f"{kind}_missed"]
        return round(100 * r[f"{kind}_met"] / judged) if judged else None

    contracts = []
    for name, r in rows.items():
        c = names.get(name) or frappe._dict(title=name, customer_name="")
        contracts.append({"name": name, "title": c.title, "customer_name": c.customer_name,
            "response_hours": flt(c.get("response_hours")) or None, "fix_hours": flt(c.get("fix_hours")) or None, **r,
            "respond_kept": kept(r, "respond"), "fix_kept": kept(r, "fix")})
    contracts.sort(key=lambda c: (-(c["respond_missed"] + c["fix_missed"]), c["customer_name"] or ""))
    return {**total, "respond_kept": kept(total, "respond"), "fix_kept": kept(total, "fix"), "contracts": contracts,
        "missed": sorted(missed, key=lambda m: -m["late_hours"])[:10]}
