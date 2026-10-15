"""Manager reports: how the maintenance work is going, and whether service contracts pay.

Everything is worked out from the jobs themselves for a chosen period (7, 30, 90 or 365 days):
jobs opened and completed, how long repairs take, preventive maintenance done on time, who did the
work, which machines keep breaking, requests received, and for each service contract the money in
(subscription invoices plus extra work billed) against the money out (parts at cost plus labour hours
at the internal cost per hour from Techy Ops Settings).

Labour hours are the time logged with the job timer, per person; jobs without timer entries fall back to
their recorded labour hours, shared between the assignees.

Jobs completed before start and finish times were recorded fall back to their last-modified time.
"""
from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, get_datetime, getdate, now_datetime, nowdate

from projectit import billing, contracts, ops, timer

PERIODS = (7, 30, 90, 365)
JOB_FIELDS = ["name", "subject", "status", "creation", "modified", "exp_end_date", "custom_work_category",
    "custom_equipment", "custom_asset", "custom_customer", "custom_service_contract", "custom_started_at",
    "custom_completed_at", "custom_labour_hours", "custom_labour_billing", "custom_labour_mode", "custom_labour_rate",
    "custom_flat_fee", "custom_sales_invoice", "custom_problem_code", "custom_cause_code", "custom_machine_down",
    "custom_down_from", "custom_down_to"]
OPEN = ("Completed", "Cancelled")


def hours_between(start, end):
    if not start or not end:
        return None
    return max(0.0, (get_datetime(end) - get_datetime(start)).total_seconds() / 3600)


def completed_at(job):
    return job.get("custom_completed_at") or job.get("modified")


def average(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def buckets(start, end, days):
    """Chart columns covering the period: days for a week, weeks up to a quarter, months for a year."""
    start, end = getdate(start), getdate(end)
    result = []
    while start <= end:
        if days <= 7:
            stop, label = start, start.strftime("%a")
        elif days <= 90:
            stop, label = min(getdate(add_days(start, 6)), end), start.strftime("%d %b")
        else:
            # Calendar months; the first and last may be part months.
            stop = min(getdate(add_days(add_months(start.replace(day=1), 1), -1)), end)
            label = start.strftime("%b %y") if not result else start.strftime("%b")
        result.append({"start": start, "end": stop, "label": label, "created": 0, "completed": 0})
        start = getdate(add_days(stop, 1))
    return result


def pm_state(job, today):
    """On time, Late, Missed or Upcoming for a preventive job against its due date."""
    due = getdate(job.exp_end_date)
    if job.status == "Completed":
        return "On time" if getdate(completed_at(job)) <= due else "Late"
    if job.status == "Cancelled":
        return None
    return "Missed" if due < today else "Upcoming"


def _in(value, start, end):
    return value is not None and getdate(start) <= getdate(value) <= getdate(end)


def _jobs(start):
    """Work orders still open, or created or completed since the start (top-level jobs only)."""
    base = {"custom_work_order": 1, "is_template": 0, "parent_task": ["is", "not set"]}
    names = set(frappe.get_all("Task", filters={**base, "status": ["not in", OPEN]}, pluck="name", limit_page_length=0))
    names |= set(frappe.get_all("Task", filters={**base, "creation": [">=", start]}, pluck="name", limit_page_length=0))
    names |= set(frappe.get_all("Task", filters={**base, "modified": [">=", start]}, pluck="name", limit_page_length=0))
    names |= set(frappe.get_all("Task", filters={**base, "exp_end_date": [">=", start]}, pluck="name", limit_page_length=0))
    # Machines that were down during the period, however old the job.
    names |= set(frappe.get_all("Task", filters={**base, "custom_machine_down": 1}, or_filters=[
        ["custom_down_to", ">=", start], ["custom_down_to", "is", "not set"]], pluck="name", limit_page_length=0))
    if not names:
        return []
    return frappe.get_all("Task", filters={"name": ["in", list(names)]}, fields=JOB_FIELDS, limit_page_length=0)


def _assignees(names):
    result = defaultdict(list)
    for chunk in range(0, len(names), 500):
        for row in frappe.get_all("ToDo", filters={"reference_type": "Task", "reference_name": ["in", names[chunk:chunk + 500]],
                "status": ["!=", "Cancelled"]}, fields=["reference_name", "allocated_to"]):
            if row.allocated_to not in result[row.reference_name]:
                result[row.reference_name].append(row.allocated_to)
    return result


def work_summary(jobs, start, end, today):
    created = [j for j in jobs if _in(j.creation, start, end)]
    done = [j for j in jobs if j.status == "Completed" and _in(completed_at(j), start, end)]
    repairs = [j for j in done if j.custom_work_category == "Corrective"]
    open_now = [j for j in jobs if j.status not in OPEN]
    return {
        "created": len(created), "completed": len(done), "open": len(open_now),
        "overdue": sum(1 for j in open_now if j.exp_end_date and getdate(j.exp_end_date) < today),
        "repair_hours": average(hours_between(j.creation, completed_at(j)) for j in repairs),
        "response_hours": average(hours_between(j.creation, j.custom_started_at) for j in created if j.custom_started_at),
    }


def pm_summary(jobs, start, end, today):
    counts = defaultdict(int)
    late = []
    for job in jobs:
        if job.custom_work_category != "Preventive" or not job.exp_end_date or not _in(job.exp_end_date, start, end):
            continue
        state = pm_state(job, today)
        if state:
            counts[state] += 1
            if state in ("Late", "Missed"):
                late.append({"name": job.name, "subject": job.subject, "due": job.exp_end_date, "state": state})
    judged = counts["On time"] + counts["Late"] + counts["Missed"]
    return {"on_time": counts["On time"], "late": counts["Late"], "missed": counts["Missed"],
        "upcoming": counts["Upcoming"], "compliance": round(100 * counts["On time"] / judged) if judged else None,
        "late_jobs": sorted(late, key=lambda r: str(r["due"]))[:10]}


def by_category(jobs, start, end):
    rows = defaultdict(lambda: {"created": 0, "completed": 0, "hours": []})
    for job in jobs:
        row = rows[job.custom_work_category or "Other"]
        if _in(job.creation, start, end):
            row["created"] += 1
        if job.status == "Completed" and _in(completed_at(job), start, end):
            row["completed"] += 1
            row["hours"].append(hours_between(job.creation, completed_at(job)))
    return sorted(({"category": k, "created": v["created"], "completed": v["completed"],
        "avg_hours": average(v["hours"])} for k, v in rows.items() if v["created"] or v["completed"]),
        key=lambda r: -(r["created"] + r["completed"]))


def by_technician(jobs, assigned, start, end, today, logged=None):
    logged = logged or {}
    rows = defaultdict(lambda: {"completed": 0, "open": 0, "overdue": 0, "labour_hours": 0.0, "hours": []})
    for job in jobs:
        done = job.status == "Completed" and _in(completed_at(job), start, end)
        if done and logged.get(job.name):
            for user, hours in logged[job.name].items():
                rows[user]["labour_hours"] += flt(hours)
        for user in assigned.get(job.name, []):
            row = rows[user]
            if done:
                row["completed"] += 1
                if not logged.get(job.name):
                    row["labour_hours"] += flt(job.custom_labour_hours) / len(assigned[job.name])
                row["hours"].append(hours_between(job.creation, completed_at(job)))
            elif job.status not in OPEN:
                row["open"] += 1
                if job.exp_end_date and getdate(job.exp_end_date) < today:
                    row["overdue"] += 1
    result = []
    for person in ops.people(list(rows)):
        row = rows[person["user"]]
        result.append({**person, "completed": row["completed"], "open": row["open"], "overdue": row["overdue"],
            "labour_hours": round(row["labour_hours"], 1), "avg_hours": average(row["hours"])})
    return sorted(result, key=lambda r: (-r["completed"], -r["open"], r["full_name"] or ""))


def repeat_failures(jobs, start, end):
    """Machines (customer equipment or our own assets) with the most repairs opened in the period."""
    counts = defaultdict(lambda: {"jobs": 0, "hours": []})
    for job in jobs:
        if job.custom_work_category != "Corrective" or not _in(job.creation, start, end):
            continue
        key = ("equipment", job.custom_equipment) if job.custom_equipment else ("asset", job.custom_asset) if job.custom_asset else None
        if key:
            counts[key]["jobs"] += 1
            if job.status == "Completed":
                counts[key]["hours"].append(hours_between(job.creation, completed_at(job)))
    top = sorted(counts.items(), key=lambda kv: -kv[1]["jobs"])[:8]
    from projectit.equipment import labels
    machines = labels(k[1] for k, _v in top if k[0] == "equipment")
    assets = ops.asset_names(k[1] for k, _v in top if k[0] == "asset")
    result = []
    for (kind, name), row in top:
        label = machines.get(name) or {}
        result.append({"kind": kind, "name": name, "repairs": row["jobs"], "avg_hours": average(row["hours"]),
            "label": label.get("equipment_name") if kind == "equipment" else assets.get(name) or name,
            "where": _where(label) if kind == "equipment" else _("Our equipment")})
    return result


def failure_counts(jobs, start, end):
    """The problem and cause codes on jobs completed in the period, most common first."""
    done = [j for j in jobs if j.status == "Completed" and _in(completed_at(j), start, end)]
    used = {j.get(f) for j in done for f in ("custom_problem_code", "custom_cause_code") if j.get(f)}
    titles = dict(frappe.get_all("Techy Failure Code", filters={"name": ["in", list(used)]}, fields=["name", "title"],
        as_list=True)) if used else {}
    result = {}
    for key, field in (("problems", "custom_problem_code"), ("causes", "custom_cause_code")):
        counts = Counter(j.get(field) for j in done if j.get(field))
        result[key] = [{"code": code, "title": titles.get(code, code), "jobs": n} for code, n in counts.most_common(8)]
    repairs = [j for j in done if j.custom_work_category == "Corrective"]
    result.update(repairs=len(repairs), coded=sum(1 for j in repairs if j.get("custom_problem_code")))
    return result


def downtime(jobs, start, end):
    """Hours each machine was down within the period, its stoppages, time to repair and availability."""
    period_start = get_datetime(getdate(start))
    period_end = min(get_datetime(f"{getdate(end)} 23:59:59"), now_datetime())
    period_hours = max((period_end - period_start).total_seconds() / 3600, 1)
    rows = defaultdict(lambda: {"hours": 0.0, "stops": 0, "repairs": [], "down_now": False})
    for job in jobs:
        if not job.get("custom_machine_down") or not job.get("custom_down_from"):
            continue
        key = ("equipment", job.custom_equipment) if job.custom_equipment else ("asset", job.custom_asset) if job.custom_asset else None
        down_from = get_datetime(job.custom_down_from)
        back = get_datetime(job.custom_down_to) if job.get("custom_down_to") else now_datetime()
        overlap = (min(back, period_end) - max(down_from, period_start)).total_seconds() / 3600
        if not key or overlap <= 0:
            continue
        row = rows[key]
        row["hours"] += overlap
        row["stops"] += 1
        if job.get("custom_down_to"):
            row["repairs"].append((back - down_from).total_seconds() / 3600)
        else:
            row["down_now"] = True
    top = sorted(rows.items(), key=lambda kv: -kv[1]["hours"])
    from projectit.equipment import labels
    machines = labels(k[1] for k, _v in top if k[0] == "equipment")
    assets = ops.asset_names(k[1] for k, _v in top if k[0] == "asset")
    result = []
    for (kind, name), row in top[:10]:
        label = machines.get(name) or {}
        result.append({"kind": kind, "name": name, "hours": round(row["hours"], 1), "stops": row["stops"],
            "mttr": average(row["repairs"]), "down_now": row["down_now"],
            "availability": round(max(0.0, 100 * (1 - row["hours"] / period_hours)), 1),
            "label": label.get("equipment_name") if kind == "equipment" else assets.get(name) or name,
            "where": _where(label) if kind == "equipment" else _("Our equipment")})
    repairs = [h for row in rows.values() for h in row["repairs"]]
    return {"machines": result, "hours": round(sum(r["hours"] for r in rows.values()), 1),
        "stops": sum(r["stops"] for r in rows.values()), "mttr": average(repairs),
        "down_now": sum(1 for r in rows.values() if r["down_now"])}


def _where(label):
    customer, site = label.get("customer_name"), label.get("site")
    if site and customer and customer in site:
        return site
    return ", ".join(x for x in (customer, site) if x)


def request_summary(start, end):
    rows = frappe.get_all("Issue", filters={"custom_maintenance_request": 1, "creation": [">=", start]},
        fields=["status", "custom_work_order", "creation"], limit_page_length=0)
    rows = [r for r in rows if _in(r.creation, start, end)]
    closed = ("Resolved", "Closed")
    return {"received": len(rows), "approved": sum(1 for r in rows if r.custom_work_order),
        "declined": sum(1 for r in rows if not r.custom_work_order and r.status in closed),
        "pending": sum(1 for r in rows if not r.custom_work_order and r.status not in closed)}


def contract_profit(start, end, jobs, logged=None):
    """Money in and out for each service contract that ran during the period."""
    logged = logged or {}
    cost_rate = flt(frappe.get_cached_doc("Techy Ops Settings").get("labour_cost_rate"))
    rows = frappe.get_all("Techy Service Contract", fields=["name", "title", "customer_name", "status", "subscription",
        "start_date", "end_date"], limit_page_length=0)
    result = []
    for doc in rows:
        if doc.status == "Cancelled" or (doc.start_date and getdate(doc.start_date) > getdate(end)) \
                or (doc.end_date and getdate(doc.end_date) < getdate(start)):
            continue
        machines = set(frappe.get_all("Techy Contract Equipment", filters={"parent": doc.name,
            "parenttype": "Techy Service Contract"}, pluck="equipment"))
        own = [j for j in jobs if j.status == "Completed" and _in(completed_at(j), start, end)
            and (j.custom_service_contract == doc.name or (j.custom_equipment and j.custom_equipment in machines))]
        subscription = 0
        if doc.subscription:
            subscription = flt(frappe.db.sql("""SELECT SUM(base_net_total) FROM `tabSales Invoice`
                WHERE subscription = %s AND docstatus = 1 AND posting_date BETWEEN %s AND %s""",
                (doc.subscription, getdate(start), getdate(end)))[0][0])
        invoiced = {name for name in frappe.get_all("Sales Invoice", filters={"docstatus": 1,
            "name": ["in", [j.custom_sales_invoice for j in own if j.custom_sales_invoice] or [""]]}, pluck="name")}
        extra = 0
        for job in own:
            if job.custom_sales_invoice in invoiced:
                labour, part_total = billing._job_total(job)
                extra += labour["amount"] + part_total
        parts_cost = flt(frappe.db.sql("""SELECT SUM(qty * valuation_rate) FROM `tabTechy Part Usage`
            WHERE status = 'Issued' AND work_order IN %s""", (tuple(j.name for j in own) or ("",),))[0][0])
        hours = sum(sum(logged[j.name].values()) if logged.get(j.name) else flt(j.custom_labour_hours) for j in own)
        income, cost = subscription + extra, parts_cost + hours * cost_rate
        result.append({"name": doc.name, "title": doc.title, "customer_name": doc.customer_name,
            "state": contracts.state(doc), "jobs": len(own), "subscription": subscription, "extra": extra,
            "income": income, "parts_cost": parts_cost, "labour_hours": round(hours, 1), "labour_cost": hours * cost_rate,
            "cost": cost, "profit": income - cost, "margin": round(100 * (income - cost) / income) if income else None})
    return {"rows": sorted(result, key=lambda r: r["profit"]), "labour_cost_rate": cost_rate}


@frappe.whitelist()
def dashboard(days=30):
    ops.system_user()
    ops.require_manager()
    days = cint(days) if cint(days) in PERIODS else 30
    today = getdate(nowdate())
    start, end = getdate(add_days(today, 1 - days)), today
    before = getdate(add_days(start, -days))
    jobs = _jobs(before)
    assigned = _assignees([j.name for j in jobs])
    logged = timer.hours_by_person([j.name for j in jobs if j.status == "Completed"])
    chart = buckets(start, end, days)
    for job in jobs:
        for col in chart:
            if _in(job.creation, col["start"], col["end"]):
                col["created"] += 1
            if job.status == "Completed" and _in(completed_at(job), col["start"], col["end"]):
                col["completed"] += 1
    return {
        "days": days, "start": start, "end": end, "currency": frappe.db.get_default("currency"),
        "work": work_summary(jobs, start, end, today),
        "previous": work_summary(jobs, before, getdate(add_days(start, -1)), getdate(add_days(start, -1))),
        "chart": [{k: c[k] for k in ("label", "created", "completed")} for c in chart],
        "pm": pm_summary(jobs, start, end, today),
        "categories": by_category(jobs, start, end),
        "technicians": by_technician(jobs, assigned, start, end, today, logged),
        "machines": repeat_failures(jobs, start, end),
        "requests": request_summary(start, end),
        "contracts": contract_profit(start, end, jobs, logged),
        "failures": failure_counts(jobs, start, end),
        "downtime": downtime(jobs, start, end),
    }
