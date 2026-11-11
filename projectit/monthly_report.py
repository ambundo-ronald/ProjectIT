"""The monthly plant report: one PDF per customer, emailed to their admins at the start of each month and
downloadable in the plant app.

For each of the customer's machines: water produced, how much it ran, how many days were logged, water quality
and recovery, the membranes' condition, the visits done (with their summaries), the customer's requests, filters
and chemicals, and what we recommend. Written for the customer: no costs, labour or internal notes.
"""
import calendar
import re
from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from projectit import ops

HOURS = re.compile(r"hour|hrs|\bh\b", re.I)
SHOWN_VISITS = 12  # the latest; the report says how many there were in all
KINDS = {"Preventive": "Service visit", "Corrective": "Repair", "Inspection": "Inspection", "Installation": "Installation"}


def month_range(month=None):
    """(first day, last day, label) of a month given as YYYY-MM (default: last month)."""
    today = getdate(nowdate())
    if month:
        try:
            year, mon = (int(x) for x in str(month).split("-")[:2])
            start = date(year, mon, 1)
        except (TypeError, ValueError):
            frappe.throw(_("Choose a month as YYYY-MM."))
    else:
        start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
    if start > today:
        frappe.throw(_("That month has not started yet."))
    return start, end, start.strftime("%B %Y")


def _readings(meter, start, end):
    return frappe.get_all("Techy Meter Reading", filters={"meter": meter, "reset": 0,
        "reading_on": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]}, fields=["value", "reading_on", "unusual", "confirmed"],
        order_by="reading_on asc", limit_page_length=2000)


def _good(rows):
    return [flt(r.value) for r in rows if not (cint(r.unusual) and not cint(r.confirmed))]


def _avg(values):
    return round(sum(values) / len(values), 1) if values else None


def machine_month(equipment, start, end):
    from projectit import ro, supplies
    from projectit.plant import LOG, SCHEDULE
    row = frappe.db.get_value("Techy Equipment", equipment, ["name", "equipment_name", "site", "tag", "log_schedule",
        "warranty_until", "contract_until"], as_dict=True)
    found = ro.roles(equipment)
    meters = frappe.get_all("Techy Meter", filters={"equipment": equipment, "active": 1}, fields=["name", "meter_name", "unit", "meter_type"])

    # Running hours and water produced (hours run x the average product flow).
    hours_meter = next((m for m in meters if m.meter_type == "Counter" and HOURS.search(f"{m.meter_name} {m.unit}")), None)
    ran = None
    if hours_meter:
        inside = _good(_readings(hours_meter.name, start, end))
        before = frappe.get_all("Techy Meter Reading", filters={"meter": hours_meter.name, "reset": 0,
            "reading_on": ["<", f"{start} 00:00:00"]}, pluck="value", order_by="reading_on desc", limit_page_length=1)
        first = flt(before[0]) if before else (inside[0] if inside else None)
        if inside and first is not None:
            ran = round(max(0.0, inside[-1] - first), 1)
    flow = _avg(_good(_readings(found["perm_q"].name, start, end))) if "perm_q" in found else None
    water = round(ran * flow / 1000, 1) if ran is not None and flow else None  # L/h x h = L; in m3

    quality = _good(_readings(found["perm_c"].name, start, end)) if "perm_c" in found else []
    perf = ro.performance(equipment) if found else None
    points = [p for p in (perf or {}).get("points", []) if start <= getdate(p["on"]) <= end]
    membranes = None
    if points:
        last = points[-1]
        membranes = {"flow": last["flow"], "salt": last["salt"], "on": last["on"],
            "needs_cleaning": bool(ro.breaches(last, perf["rules"])), "recovery": _avg([p["recovery"] for p in points])}

    # Logging, against the machine's schedule.
    schedule = row.log_schedule or "Daily"
    last_day = min(end, getdate(nowdate()))
    logs = frappe.get_all(LOG, filters={"equipment": equipment, "log_on": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]},
        pluck="log_on")
    days = (last_day - start).days + 1
    window, per = SCHEDULE.get(schedule, (0, 0))
    by_day = {}
    for on in logs:
        by_day[getdate(on)] = by_day.get(getdate(on), 0) + 1
    if window == 1:
        logged, expected = sum(1 for n in by_day.values() if n >= per), days
    elif window:
        logged, expected = min(len(logs), max(1, days // window)), max(1, days // window)
    else:
        logged, expected = len(by_day), 0

    visits = frappe.get_all("Task", filters={"custom_work_order": 1, "custom_equipment": equipment, "parent_task": ["is", "not set"],
        "is_template": 0, "status": "Completed", "custom_completed_at": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]},
        fields=["subject", "custom_work_category", "custom_completed_at", "custom_work_summary"], order_by="custom_completed_at asc")
    users = frappe.get_all("Techy Customer User", filters={"customer": frappe.db.get_value("Techy Equipment", equipment, "customer")},
        pluck="user")
    requests = frappe.get_all("Issue", filters={"custom_maintenance_request": 1, "custom_equipment": equipment,
        "raised_by": ["in", users or [""]], "creation": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]},
        fields=["subject", "creation", "status", "custom_work_order"], order_by="creation asc")
    changes = frappe.get_all("Techy Supply Change", filters={"equipment": equipment, "action": ["in", ["Changed", "Refilled"]],
        "changed_on": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]}, fields=["supply_name", "action"])
    supply_rows = supplies.rows(equipment)
    used = {}
    for c in changes:
        used[c.supply_name] = used.get(c.supply_name, 0) + 1

    out = {"name": row.name, "equipment_name": row.equipment_name, "site": row.site, "tag": row.tag, "ran": ran,
        "water": water, "per_day": round(water / days, 2) if water is not None and days else None, "flow": flow,
        "quality": {"avg": _avg(quality), "min": min(quality) if quality else None, "max": max(quality) if quality else None,
            "unit": found["perm_c"].unit if "perm_c" in found else ""},
        "membranes": membranes, "logged": logged, "expected": expected, "schedule": schedule,
        "visits": [{"on": v.custom_completed_at, "kind": _(KINDS.get(v.custom_work_category, "Visit")), "title": v.subject,
            "summary": v.custom_work_summary or ""} for v in visits[-SHOWN_VISITS:]],
        "visits_total": len(visits), "repairs": sum(1 for v in visits if v.custom_work_category == "Corrective"),
        "requests": [{"on": r.creation, "subject": r.subject,
            "state": _("Done") if r.status in ("Resolved", "Closed") and r.custom_work_order else
                _("Closed") if r.status in ("Resolved", "Closed") else _("Open")} for r in requests],
        "supplies": [{"name": s["supply_name"], "used": used.get(s["supply_name"], 0), "stock": s["stock"], "unit": s["unit"],
            "due": s["due"], "due_on": s["due_on"], "low": s["low"]} for s in supply_rows]}
    out["recommendations"] = recommend(out, row)
    return out


def recommend(m, row):
    """What we suggest, in plain words, from the month's numbers."""
    tips = []
    if m["membranes"] and m["membranes"]["needs_cleaning"]:
        tips.append(_("Clean the membranes (CIP): they make less water or let more salt through than when they were clean."))
    if m["expected"] and m["logged"] < 0.8 * m["expected"]:
        tips.append(_("Log every day: {0} of {1} logged this month. Daily readings let us spot problems before they stop the plant.").format(
            m["logged"], m["expected"]))
    for s in m["supplies"]:
        if s["due"]:
            tips.append(_("Change the {0}: it is due.").format(s["name"].lower()))
        elif s["low"]:
            tips.append(_("Order more {0}: {1} {2} left.").format(s["name"].lower(), ops_num(s["stock"]), s["unit"]))
    today = getdate(nowdate())
    for field, label in (("warranty_until", _("warranty")), ("contract_until", _("service contract"))):
        ends = row.get(field)
        if ends and 0 <= (getdate(ends) - today).days <= 60:
            tips.append(_("Your {0} ends on {1}: talk to us about what comes next.").format(label, frappe.utils.format_date(ends)))
    if not row.get("contract_until") or getdate(row.contract_until) < today:
        if m["repairs"]:
            tips.append(_("A service contract with regular visits costs less than repairs: ask us about one."))
    return tips


def ops_num(value):
    from projectit.meters import fmt
    return fmt(value)


def context(customer, month=None):
    from projectit.service_report import _company
    start, end, label = month_range(month)
    names = frappe.get_all("Techy Equipment", filters={"customer": customer, "status": "Active"}, pluck="name",
        order_by="equipment_name asc")
    with_meters = set(frappe.get_all("Techy Meter", filters={"equipment": ["in", names or [""]], "active": 1}, pluck="equipment"))
    machines = [machine_month(n, start, end) for n in names if n in with_meters]
    machines = [m for m in machines if m["ran"] is not None or m["logged"] or m["visits"] or m["requests"]] or machines[:10]
    status = {s.equipment: s.status for s in frappe.get_all("Techy Plant Status", filters={"equipment": ["in", names or [""]]},
        fields=["equipment", "status"])}
    for m in machines:
        m["status"] = status.get(m["name"])
    return {"company": _company(title=_("Monthly plant report")), "customer": frappe.db.get_value("Customer", customer, "customer_name") or customer,
        "month": label, "start": start, "end": end, "machines": machines,
        "water": round(sum(m["water"] or 0 for m in machines), 1) if any(m["water"] is not None for m in machines) else None,
        "visits": sum(m["visits_total"] for m in machines), "requests": sum(len(m["requests"]) for m in machines),
        "printed": frappe.utils.format_datetime(frappe.utils.now_datetime(), "dd MMM yyyy HH:mm")}


def build(customer, month=None):
    """(pdf bytes, file name)."""
    from frappe.utils.pdf import get_pdf
    ctx = context(customer, month)
    html = frappe.render_template("projectit/templates/monthly_plant_report.html", ctx)
    pdf = get_pdf(html, {"page-size": "A4", "margin-top": "12mm", "margin-bottom": "14mm", "margin-left": "12mm",
        "margin-right": "12mm", "encoding": "UTF-8", "load-error-handling": "ignore", "load-media-error-handling": "ignore"})
    return pdf, f"Plant report {ctx['customer']} {ctx['month']}.pdf"


def months(customer):
    """The months a customer can get a report for: from their first installation, up to the last 12."""
    first = frappe.db.sql("""select min(coalesce(installed_on, delivered_on, date(creation))) from `tabTechy Equipment`
        where customer = %s""", (customer,))[0][0]
    today = getdate(nowdate())
    start = getdate(first) if first else today
    out, cursor = [], today.replace(day=1)
    while cursor >= start.replace(day=1) and len(out) < 12:
        out.append({"month": cursor.strftime("%Y-%m"), "label": cursor.strftime("%B %Y"), "current": cursor.month == today.month
            and cursor.year == today.year})
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return out


# Sending ---------------------------------------------------------------------------------------------------------------

def send(customer, month=None):
    """Email the report to the customer's admins who want it. Returns the addresses it went to."""
    to = frappe.get_all("Techy Customer User", filters={"customer": customer, "enabled": 1, "access": "Customer admin",
        "notify_reports": ["!=", 0]}, pluck="user")
    if not to:
        return []
    pdf, filename = build(customer, month)
    _start, _end, label = month_range(month)
    company = frappe.db.get_single_value("Global Defaults", "default_company") or ""
    frappe.sendmail(recipients=to, subject=_("Your plant report for {0}").format(label),
        message=_("<p>Hello,</p><p>Attached is your plant report for <b>{0}</b>: water produced, logs, visits, the "
            "membranes' condition and what we recommend.</p><p>You can also open past reports in the plant app (Service).</p>"
            "<p>{1}</p>").format(label, frappe.utils.escape_html(company)),
        attachments=[{"fname": filename, "fcontent": pdf}], reference_doctype="Customer", reference_name=customer)
    return to


def send_all():
    """Monthly (scheduler): last month's report to every customer with an admin on the plant app."""
    for customer in frappe.get_all("Techy Customer User", filters={"enabled": 1, "access": "Customer admin"},
            pluck="customer", distinct=True):
        try:
            send(customer)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Techy Plant: monthly report for {customer} failed")


# Staff ------------------------------------------------------------------------------------------------------------------

@frappe.whitelist()
def download(customer, month=None):
    ops.system_user()
    ops.require_manager()
    pdf, filename = build(customer, month)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def send_now(customer, month=None):
    ops.system_user()
    ops.require_manager()
    to = send(customer, month)
    if not to:
        frappe.throw(_("Nobody at this customer gets the report: invite a customer admin first."))
    return {"sent_to": to}
