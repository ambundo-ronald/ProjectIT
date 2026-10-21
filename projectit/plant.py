"""The customer app (Techy Plant): what a customer's admin and operators see of their own machines.

Every endpoint starts from customer_accounts.require_account() or require_machine(), and reads with the database
directly, so customers never need role rights on any DocType. Only customer-safe fields leave here: no costs,
labour, internal notes, investigations or technician chat.
"""
import base64
import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, escape_html, flt, get_datetime, get_fullname, getdate, \
    now_datetime, nowdate

from projectit import customer_accounts, customer_notify

LOG = "Techy Plant Log"
# How often a machine should be logged: (window in days, logs expected in it).
SCHEDULE = {"Daily": (1, 1), "Twice a day": (1, 2), "Weekly": (7, 1)}
FIX_HOURS = 24  # an operator may correct their own log for this long; after that, only we can
LATE_DAYS = 7  # a log sent later from a phone that was offline keeps the time it was taken, up to a week back
LOG_FIELDS = ["name", "log_on", "logged_by", "source", "note", "edited_on", "creation"]


def _machine_rows(names):
    if not names:
        return []
    return frappe.get_all("Techy Equipment", filters={"name": ["in", names]},
        fields=["name", "equipment_name", "tag", "site", "status", "installed_on", "warranty_until", "contract_until"],
        order_by="equipment_name asc")


@frappe.whitelist()
def me():
    """Who I am in the customer app, and the machines I may see."""
    acc = customer_accounts.require_account()
    settings = frappe.get_cached_doc("Techy Ops Settings")
    return {"preview": bool(acc.get("preview")), "user": acc.user, "full_name": acc.full_name, "access": acc.access, "admin": acc.access == "Customer admin",
        "customer": acc.customer, "customer_name": acc.customer_name or acc.customer,
        "machines": _machine_rows(customer_accounts.machines(acc)),
        "company": frappe.db.get_single_value("Global Defaults", "default_company"),
        "support_phone": settings.get("support_phone"), "support_email": settings.get("support_email"),
        "notify": customer_notify.preferences(acc)}


@frappe.whitelist(methods=["POST"])
def set_notifications(visits=None, reminders=None):
    """My choices: visit news, and log reminders."""
    acc = customer_accounts.writable()
    values = {}
    if visits is not None:
        values[customer_notify.VISITS] = 1 if cint(visits) else 0
    if reminders is not None:
        values[customer_notify.REMINDERS] = 1 if cint(reminders) else 0
    if values:
        frappe.db.set_value("Techy Customer User", acc.name, values)
    return customer_notify.preferences(acc)


# The operator's log ---------------------------------------------------------------------------------------------

def _meters(equipment):
    """The machine's active meters in log order: the RO set first (feed to permeate), then any others."""
    from projectit import ro
    rows = frappe.get_all("Techy Meter", filters={"equipment": equipment, "active": 1},
        fields=["name", "meter_name", "unit", "meter_type", "last_reading", "last_reading_on"],
        order_by="creation asc, name asc", limit_page_length=50)
    found = ro.roles(equipment)
    order = {m.name: i for i, m in enumerate(found[r] for r in ro.METERS if r in found)}
    needed = {found[r].name for r, required in ro.LOG_STEPS if required and r in found}
    rows.sort(key=lambda r: order.get(r.name, len(order)))
    return [{"name": r.name, "meter_name": r.meter_name, "unit": r.unit, "meter_type": r.meter_type,
        "last": r.last_reading if r.last_reading_on else None, "last_on": r.last_reading_on, "ro": r.name in needed}
        for r in rows]


def log_status(equipment):
    """Whether this machine's log is done for now, by its schedule."""
    schedule = frappe.db.get_value("Techy Equipment", equipment, "log_schedule") or "Daily"
    last = frappe.db.get_value(LOG, {"equipment": equipment}, "log_on", order_by="log_on desc")
    if schedule not in SCHEDULE:
        return {"schedule": schedule, "expected": 0, "done": 0, "due": False, "last_on": last}
    days, expected = SCHEDULE[schedule]
    since = get_datetime(add_days(getdate(nowdate()), 1 - days))
    done = frappe.db.count(LOG, {"equipment": equipment, "log_on": [">=", since]})
    return {"schedule": schedule, "expected": expected, "done": done, "due": done < expected, "last_on": last}


def can_fix(log, user=None):
    age = (now_datetime() - get_datetime(log.creation)).total_seconds() / 3600
    return log.logged_by == (user or frappe.session.user) and age < FIX_HOURS


def _log_row(log):
    readings = frappe.get_all("Techy Meter Reading", filters={"plant_log": log.name},
        fields=["name", "meter", "value", "unusual"], order_by="creation asc")
    names = {m.name: m for m in frappe.get_all("Techy Meter", filters={"name": ["in", [r.meter for r in readings] or [""]]},
        fields=["name", "meter_name", "unit"])}
    return {"name": log.name, "log_on": log.log_on, "by": get_fullname(log.logged_by), "mine": log.logged_by == frappe.session.user,
        "source": log.source, "note": log.note, "edited_on": log.edited_on, "can_fix": can_fix(log),
        "has_photo": bool(frappe.db.exists("File", {"attached_to_doctype": LOG, "attached_to_name": log.name})),
        "readings": [{"meter": r.meter, "meter_name": names[r.meter].meter_name if r.meter in names else r.meter,
            "unit": names[r.meter].unit if r.meter in names else "", "value": r.value, "unusual": bool(r.unusual)}
            for r in readings]}


def recent(equipment, limit=30):
    return [_log_row(l) for l in frappe.get_all(LOG, filters={"equipment": equipment}, fields=LOG_FIELDS,
        order_by="log_on desc", limit_page_length=limit)]


@frappe.whitelist()
def log_form(equipment):
    """What the operator fills in for this machine, and how logging is going."""
    customer_accounts.require_machine(equipment)
    return {"equipment": equipment, "meters": _meters(equipment), "status": log_status(equipment),
        "recent": recent(equipment, 30)}


def _taken_on(value):
    """When the log was taken: now, or the time a phone that was offline recorded it (within the last week)."""
    now = now_datetime()
    if not value:
        return now
    try:
        when = get_datetime(value)
    except Exception:
        return now
    if not when or when > add_to_date(now, minutes=5) or when < add_days(now, -LATE_DAYS):
        return now
    return when


@frappe.whitelist(methods=["POST"])
def save_log(equipment, values, note=None, photo=None, confirm=0, taken_on=None, client_id=None):
    """Save one log: a reading for each meter filled in. Unusual readings are not saved until the operator confirms
    them (`confirm=1`); a log sent later from a phone that was offline (`confirm=2`) is saved with them marked."""
    from projectit import meters, ops, ro
    customer_accounts.writable(customer_accounts.require_machine(equipment))
    client_id = str(client_id or "")[:64] or None
    if client_id:
        done = frappe.db.get_value(LOG, {"client_id": client_id}, LOG_FIELDS + ["equipment"], as_dict=True)
        if done and done.equipment == equipment:  # already received: the phone sent it twice
            return {"log": _log_row(done), "status": log_status(equipment)}
        if done:
            client_id = None  # another log's id (never from the same phone): save this one on its own
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    allowed = {m["name"] for m in _meters(equipment)}
    entries = {m: meters._value(v) for m, v in (values or {}).items() if m in allowed and v not in (None, "")}
    if not entries:
        frappe.throw(_("Fill in at least one reading."))
    note = ops.text(note, "a note", 500, required=False) or None
    when = _taken_on(taken_on)

    docs = {m: frappe.get_doc("Techy Meter", m, for_update=True) for m in entries}
    for m, doc in docs.items():
        if doc.meter_type == "Counter" and doc.last_reading_on and entries[m] < flt(doc.last_reading):
            frappe.throw(_("{0} only goes up: the last reading was {1} {2}. Check the number; if the meter was replaced, "
                "tell us.").format(doc.meter_name, meters.fmt(doc.last_reading), doc.unit))
    warnings = {m: w for m, w in ((m, meters.unusual(doc, entries[m])) for m, doc in docs.items()) if w}
    if warnings and not cint(confirm):
        return {"needs_confirm": True, "warnings": [{"meter": m, "meter_name": docs[m].meter_name, "warning": w}
            for m, w in warnings.items()]}

    log = frappe.get_doc({"doctype": LOG, "equipment": equipment, "log_on": when, "logged_by": frappe.session.user,
        "source": "Customer", "note": note, "client_id": client_id, "readings": len(entries), "flagged": len(warnings)})
    log.insert(ignore_permissions=True)
    for m, doc in docs.items():
        meters._record(doc, entries[m], flagged=m in warnings, confirmed=m in warnings and cint(confirm) == 1,
            source="Customer", plant_log=log.name, when=when, check_ro=False)
    if photo:
        ops.save_photo(LOG, log.name, photo, "plant-log", ignore_permissions=True)
    ro.after_reading(equipment, from_customer=True)  # once, on the whole log
    return {"log": _log_row(log), "status": log_status(equipment)}


def _visible_log(name):
    log = frappe.get_doc(LOG, name) if name and frappe.db.exists(LOG, name) else None
    if not log:
        frappe.throw(_("This log was not found."), frappe.PermissionError)
    customer_accounts.require_machine(log.equipment)
    return log


@frappe.whitelist(methods=["POST"])
def fix_log(log, values):
    """Correct a typo in my own log, within a day of saving it. The change is recorded on the log."""
    from projectit import meters, ro
    log = _visible_log(log)
    customer_accounts.writable()
    if not can_fix(log):
        frappe.throw(_("Only the person who saved a log can correct it, within {0} hours. Ask us to correct it.").format(
            FIX_HOURS), frappe.PermissionError)
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    changes = []
    for r in frappe.get_all("Techy Meter Reading", filters={"plant_log": log.name}, fields=["name", "meter", "value", "reading_on"]):
        if r.meter not in values or values[r.meter] in (None, ""):
            continue
        value = meters._value(values[r.meter])
        if value == flt(r.value):
            continue
        meter = frappe.get_doc("Techy Meter", r.meter, for_update=True)
        if meter.meter_type == "Counter":
            before = frappe.get_all("Techy Meter Reading", filters={"meter": r.meter, "name": ["!=", r.name],
                "reading_on": ["<", r.reading_on], "reset": 0}, pluck="value", order_by="reading_on desc", limit_page_length=1)
            if before and value < flt(before[0]):
                frappe.throw(_("{0} only goes up: the reading before was {1} {2}.").format(meter.meter_name,
                    meters.fmt(before[0]), meter.unit))
        # A correction is the person's own check, so the reading is no longer marked unusual.
        frappe.db.set_value("Techy Meter Reading", r.name, {"value": value, "unusual": 0, "confirmed": 0})
        if meter.last_reading_on and get_datetime(meter.last_reading_on) == get_datetime(r.reading_on):
            frappe.db.set_value("Techy Meter", meter.name, "last_reading", value)
        changes.append(_("{0} from {1} to {2} {3}").format(meter.meter_name, meters.fmt(r.value), meters.fmt(value), meter.unit))
    if changes:
        log.db_set("edited_on", now_datetime())
        log.add_comment("Info", escape_html(_("{0} corrected {1}.").format(get_fullname(), "; ".join(changes))))
        ro.after_reading(log.equipment, from_customer=True)
    return {"log": _log_row(frappe.get_doc(LOG, log.name)), "changed": len(changes)}


@frappe.whitelist()
def log_photo(log):
    """The photo taken with a log, as a data URL (customers have no access to files directly)."""
    log = _visible_log(log)
    name = frappe.db.get_value("File", {"attached_to_doctype": LOG, "attached_to_name": log.name}, "name")
    if not name:
        return None
    f = frappe.get_doc("File", name)
    kind = "png" if f.file_name.lower().endswith(".png") else "jpeg"
    return f"data:image/{kind};base64," + base64.b64encode(f.get_content()).decode()


# The dashboard ---------------------------------------------------------------------------------------------------

KEY_ROLES = (("perm_q", "Water produced"), ("perm_c", "Water quality (TDS)"), ("feed_p", "Feed pressure"))
HOURS = re.compile(r"hour|hrs|\bh\b", re.I)


def _week_change(points, value):
    """The change from about a week ago (the reading nearest 7 days back, at least 4 days old)."""
    if value is None or not points:
        return None
    now = now_datetime()
    older = [p for p in points if get_datetime(p["on"]) <= now - timedelta(days=4)]
    if not older:
        return None
    target = now - timedelta(days=7)
    then = min(older, key=lambda p: abs((get_datetime(p["on"]) - target).total_seconds()))
    return {"from": then["value"], "on": then["on"], "change": round(flt(value) - flt(then["value"]), 2)}


def _status(h, ro_perf, overdue_log):
    """Running well / Needs attention / Action needed, with the reasons in plain words."""
    act, watch = [], []
    if h["health"].get("down_now"):
        act.append(_("The machine is reported as not working."))
    if ro_perf and ro_perf["breaches"]:
        act.append(_("The membranes need cleaning: they make less water or let more salt through than when they were clean."))
    if h["health"].get("grade") == "At risk":
        act.append(_("Several things need looking at (readings, service or repairs)."))
    elif h["health"].get("grade") == "Watch":
        watch.append(_("Some readings or services need watching."))
    if overdue_log:
        watch.append(_("No log for a while: the latest readings help us spot problems early."))
    if h["data"]["stale"]:
        watch.append(_("Not read recently: {0}.").format(", ".join(h["data"]["stale"][:3])))
    return {"level": "action" if act else "watch" if watch else "good", "reasons": act + watch}


def _fmt(value):
    from projectit.meters import fmt
    return fmt(value)


@frappe.whitelist()
def dashboard(equipment, days=90):
    """The plant at a glance for the customer: status, key numbers, charts, what is next and how logging is going.
    Built from the same numbers as our Health tab, passing on only what a customer should see."""
    from projectit import health, ro
    customer_accounts.require_machine(equipment)
    days = 30 if cint(days) == 30 else 90
    h = health.compute_health(equipment, manager=False)
    row = frappe.db.get_value("Techy Equipment", equipment, ["name", "equipment_name", "status", "warranty_until",
        "contract_until", "service_contract"], as_dict=True)
    now = now_datetime()
    since = now - timedelta(days=days)
    found = ro.roles(equipment)
    by_name = {s["name"]: s for s in h["meters"]}

    def series(meter):
        s = by_name.get(meter)
        if not s:
            return None
        return {"meter": s["meter_name"], "unit": s["unit"], "last": s["last"], "last_on": s["last_on"],
            "points": [p for p in s["points"] if get_datetime(p["on"]) >= since], "limits": s["limits"],
            "week": _week_change(s["points"], s["last"])}

    charts = []
    for role, label in KEY_ROLES:
        s = series(found[role].name) if role in found else None
        if s:
            charts.append({**s, "key": role, "label": _(label)})
    numbers = [{"key": c["key"], "label": c["label"], "value": c["last"], "unit": c["unit"], "on": c["last_on"],
        "week": c["week"]} for c in charts[:2]]
    ro_perf = h["ro"]
    if ro_perf and ro_perf["latest"]:
        numbers.append({"key": "recovery", "label": _("Recovery"), "value": ro_perf["latest"]["recovery"], "unit": "%",
            "on": ro_perf["latest"]["on"], "help": _("Share of the feed water that becomes clean water."),
            "week": _week_change([{"on": p["on"], "value": p["recovery"]} for p in ro_perf["points"]], ro_perf["latest"]["recovery"])})
    hours = next((s for s in h["meters"] if s["meter_type"] == "Counter" and HOURS.search(f"{s['meter_name']} {s['unit']}")), None)
    if hours:
        numbers.append({"key": "hours", "label": hours["meter_name"], "value": hours["last"], "unit": hours["unit"],
            "on": hours["last_on"], "week": _week_change(hours["points"], hours["last"])})

    membranes = None
    if ro_perf and ro_perf["points"]:
        pts = [p for p in ro_perf["points"] if get_datetime(p["on"]) >= since] or ro_perf["points"][-1:]
        rules = ro_perf["rules"]
        membranes = {"since": ro_perf["baseline"]["on"], "latest": {k: ro_perf["latest"].get(k) for k in ("on", "flow", "salt")},
            "flow": [{"on": p["on"], "value": p["flow"]} for p in pts],
            "salt": [{"on": p["on"], "value": p["salt"]} for p in pts if p["salt"] is not None],
            "clean_at": {"flow": -rules["cip_flow_drop"], "salt": rules["cip_salt_rise"]},
            "needs_cleaning": bool(ro_perf["breaches"]), "cleaning_planned": bool(ro_perf["cip_job"])}

    # What is next: a planned visit (its date and kind only), service due by running hours, cover end dates.
    today = getdate(nowdate())
    upcoming = frappe.get_all("Task", filters={"custom_work_order": 1, "custom_equipment": equipment,
        "parent_task": ["is", "not set"], "is_template": 0, "status": ["not in", ["Completed", "Cancelled"]],
        "exp_start_date": [">=", today]}, fields=["exp_start_date", "custom_work_category"],
        order_by="exp_start_date asc", limit_page_length=1)
    contract_visit = frappe.db.get_value("Techy Contract Equipment", {"parent": row.service_contract, "parenttype":
        "Techy Service Contract", "equipment": equipment}, "next_visit") if row.service_contract else None
    kinds = {"Preventive": _("Service visit"), "Corrective": _("Repair visit"), "Inspection": _("Inspection visit"),
        "Installation": _("Installation")}
    nxt = []
    going = frappe.get_all("Task", filters={"custom_work_order": 1, "custom_equipment": equipment, "parent_task": ["is", "not set"],
        "status": ["in", ["Open", "Overdue"]], "custom_on_way_at": ["is", "set"]}, fields=["status", "custom_on_way_at",
        "custom_eta_minutes"], order_by="custom_on_way_at desc", limit_page_length=1)
    if going and on_the_way(going[0]):
        nxt.append({"kind": "onway", "label": _("Our technician is on the way"), "on": going[0].custom_on_way_at,
            "minutes": cint(going[0].custom_eta_minutes) or None})
    if upcoming:
        nxt.append({"kind": "visit", "label": kinds.get(upcoming[0].custom_work_category, _("Visit")), "on": upcoming[0].exp_start_date})
    elif contract_visit and getdate(contract_visit) >= today:
        nxt.append({"kind": "visit", "label": _("Service visit (contract)"), "on": contract_visit})
    service = next((f for f in h["forecasts"]["meters"] if f.get("kind") == "service"), None)
    if service:
        nxt.append({"kind": "service", "label": _("Service due at {0} {1}").format(_fmt(service["target"]), service.get("unit") or ""),
            "on": service["on"], "estimate": True, "confidence": (service.get("confidence") or {}).get("level")})
    for field, label in (("warranty_until", _("Warranty ends")), ("contract_until", _("Service contract ends"))):
        if row.get(field):
            nxt.append({"kind": field, "label": label, "on": row.get(field), "past": getdate(row.get(field)) < today})

    logging = health.customer_logging(equipment) or {"schedule": "Daily", "logs": 0, "done": 0, "expected": 0, "days": 30}
    today_log = log_status(equipment)
    window = SCHEDULE.get(today_log["schedule"], (0, 0))[0]
    overdue_log = bool(window) and (not today_log["last_on"] or
        get_datetime(today_log["last_on"]) < now - timedelta(days=2 * window + 1))
    return {"machine": {"name": row.name, "equipment_name": row.equipment_name, "status": row.status},
        "status": _status(h, ro_perf, overdue_log), "numbers": numbers, "charts": charts, "membranes": membranes,
        "next": nxt, "logging": {**logging, "today": today_log}, "days": days, "as_of": now}


# Service: requests, visits, reports, ratings and cover --------------------------------------------------------------

VISIT_KINDS = {"Preventive": "Service visit", "Corrective": "Repair", "Inspection": "Inspection", "Installation": "Installation",
    "Safety": "Safety check", "Other": "Visit"}
JOB_FIELDS = ["name", "subject", "status", "custom_work_category", "custom_completed_at", "custom_work_summary",
    "exp_start_date", "custom_customer", "custom_rating", "custom_rating_comment", "custom_rated_on",
    "custom_rating_key", "custom_work_order", "custom_equipment", "modified", "creation", "company"]
DECLINED = "Declined:"


def on_the_way(job):
    """Our technician pressed On my way for this not-yet-started visit in the last few hours."""
    from projectit.work_orders import ON_WAY_HOURS
    at = job.get("custom_on_way_at")
    return bool(at) and job.get("status") in ("Open", "Overdue") and         (now_datetime() - get_datetime(at)).total_seconds() < ON_WAY_HOURS * 3600


def _request_state(issue, job):
    """What the customer sees of a request, in plain words."""
    if issue.status in ("Resolved", "Closed") and not issue.custom_work_order:
        return {"key": "closed", "label": _("Closed")}
    if not job:
        return {"key": "received", "label": _("Received")}
    if job.status == "Completed":
        return {"key": "done", "label": _("Done")}
    if job.status in ("Working", "Pending Review"):
        return {"key": "working", "label": _("In progress")}
    if on_the_way(job):
        return {"key": "onway", "label": _("On the way"), "note": _("Our technician is on the way{0}.").format(
            _(": about {0} min").format(job.custom_eta_minutes) if cint(job.custom_eta_minutes) else "")}
    if job.exp_start_date:
        return {"key": "scheduled", "label": _("Scheduled"), "on": job.exp_start_date}
    return {"key": "accepted", "label": _("Accepted"), "note": _("We will schedule a visit and tell you the date.")}


def _requests(equipment, customer):
    """Requests my company's people raised for this machine (not our staff's own notes)."""
    from projectit import ops
    users = frappe.get_all("Techy Customer User", filters={"customer": customer}, pluck="user")
    rows = frappe.get_all("Issue", filters={"custom_maintenance_request": 1, "custom_equipment": equipment,
        "raised_by": ["in", users or [""]]}, fields=["name", "subject", "description", "status", "raised_by", "creation",
        "custom_work_order", "priority"], order_by="creation desc", limit_page_length=30)
    linked = [r.custom_work_order for r in rows if r.custom_work_order]
    jobs = {j.name: j for j in frappe.get_all("Task", filters={"name": ["in", linked or [""]]},
        fields=["name", "status", "exp_start_date", "custom_on_way_at", "custom_eta_minutes"])}
    out = []
    for r in rows:
        state = _request_state(r, jobs.get(r.custom_work_order))
        reason = None
        if state["key"] == "closed":
            notes = frappe.get_all("Comment", filters={"reference_doctype": "Issue", "reference_name": r.name,
                "comment_type": "Comment"}, pluck="content", order_by="creation desc", limit_page_length=5)
            note = next((n for n in notes if DECLINED in (n or "")), None)
            reason = ops.plain(note).split(DECLINED, 1)[-1].strip() if note else None
        out.append({"name": r.name, "subject": r.subject, "description": ops.plain(r.description)[:400],
            "on": r.creation, "by": get_fullname(r.raised_by), "mine": r.raised_by == frappe.session.user,
            "urgent": r.priority in ("High", "Urgent"), "state": state, "reason": reason,
            "visit": r.custom_work_order if state["key"] == "done" else None})
    return out


def _visit_row(job, people):
    from projectit import ratings
    return {"name": job.name, "title": job.subject, "kind": _(VISIT_KINDS.get(job.custom_work_category, "Visit")),
        "on": job.custom_completed_at or job.modified, "summary": job.custom_work_summary or "",
        "technicians": [get_fullname(u).split(" ")[0] for u in people],
        "rating": cint(job.custom_rating) or None, "comment": job.custom_rating_comment or "",
        "can_rate": ratings.rateable(job) and ratings.still_open(job)}


def _visits(equipment, limit=20):
    from projectit.work_orders import _assignees
    jobs = frappe.get_all("Task", filters={"custom_work_order": 1, "custom_equipment": equipment, "parent_task": ["is", "not set"],
        "is_template": 0, "status": "Completed"}, fields=JOB_FIELDS, order_by="custom_completed_at desc, modified desc",
        limit_page_length=limit)
    people = _assignees([j.name for j in jobs])
    return [_visit_row(j, people[j.name]) for j in jobs]


def _cover(equipment):
    """The warranty and service contract, as the customer may see them (no subscription or payment details)."""
    from projectit import contracts
    row = frappe.db.get_value("Techy Equipment", equipment, ["warranty_until", "contract_until", "service_contract",
        "installed_on"], as_dict=True)
    today = getdate(nowdate())
    terms = contracts.terms(row.service_contract) if row.service_contract else None
    contract = None
    if terms and terms["state"] != "Cancelled":
        start = frappe.db.get_value("Techy Service Contract", row.service_contract, "start_date")
        done = frappe.db.count("Task", {"custom_work_order": 1, "custom_equipment": equipment, "status": "Completed",
            "custom_work_category": "Preventive", "custom_completed_at": [">=", start]}) if start else None
        contract = {"title": terms["title"], "state": terms["state"], "start": start, "end": terms["end_date"],
            "visit_frequency": terms["visit_frequency"], "labour_included": bool(terms["labour_included"]),
            "callouts_included": terms["callouts_included"], "response_hours": terms["response_hours"],
            "fix_hours": terms["fix_hours"], "items": [i.item_name or i.item_code for i in terms["items"]],
            "visits_done": done}
    return {"installed_on": row.installed_on, "warranty_until": row.warranty_until,
        "warranty_active": bool(row.warranty_until and getdate(row.warranty_until) >= today), "contract": contract}


@frappe.whitelist()
def service(equipment):
    """The Service tab: my company's requests for this machine, past visits with their reports, and the cover."""
    acc = customer_accounts.require_machine(equipment)
    today = getdate(nowdate())
    planned = frappe.get_all("Task", filters={"custom_work_order": 1, "custom_equipment": equipment, "parent_task": ["is", "not set"],
        "is_template": 0, "status": ["not in", ["Completed", "Cancelled"]], "exp_start_date": [">=", today]},
        fields=["exp_start_date", "custom_work_category"], order_by="exp_start_date asc", limit_page_length=3)
    return {"requests": _requests(equipment, acc.customer), "visits": _visits(equipment), "cover": _cover(equipment),
        "planned": [{"on": p.exp_start_date, "kind": _(VISIT_KINDS.get(p.custom_work_category, "Visit"))} for p in planned]}


@frappe.whitelist(methods=["POST"])
def request_service(equipment, subject, description=None, urgent=0, photo=None):
    """Ask us for service on a machine. It arrives in our Requests inbox like any other work request."""
    from projectit import ops, work_requests
    acc = customer_accounts.writable(customer_accounts.require_machine(equipment))
    doc = work_requests._issue(subject, description, None, None, frappe.session.user,
        priority="High" if cint(urgent) else None, equipment=equipment)
    if photo:
        ops.save_photo("Issue", doc.name, photo, "request", ignore_permissions=True)
    return {"request": next((r for r in _requests(equipment, acc.customer) if r["name"] == doc.name), None)}


def _visit(job):
    """A completed job on one of my machines (for its report and rating)."""
    row = frappe.db.get_value("Task", str(job or "")[:140], JOB_FIELDS, as_dict=True) if job else None
    if not row or not row.custom_work_order or not row.custom_equipment:
        frappe.throw(_("This visit was not found."), frappe.PermissionError)
    customer_accounts.require_machine(row.custom_equipment)
    if row.status != "Completed":
        frappe.throw(_("The report is ready once the visit is completed."))
    return row


@frappe.whitelist()
def report(job):
    """The visit's service report (PDF, no prices), as we send it to customers."""
    from projectit import service_report
    row = _visit(job)
    pdf, filename = service_report.build(row.name, trusted=True)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def rate_visit(job, rating, comment=None):
    """Rate a completed visit from the app (the same rating as the emailed link)."""
    from projectit import ratings
    from projectit.work_orders import _assignees
    row = _visit(job)
    customer_accounts.writable()
    if not ratings.rateable(row):
        frappe.throw(_("This visit cannot be rated."))
    ratings.record(row, rating, comment)
    row = frappe.db.get_value("Task", row.name, JOB_FIELDS, as_dict=True)
    return {"visit": _visit_row(row, _assignees([row.name])[row.name])}
