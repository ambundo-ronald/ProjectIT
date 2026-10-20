"""Reverse-osmosis logging and normalised performance (in the spirit of ASTM D4516).

Logging: "Set up RO logging" gives a machine the standard RO meters (feed, concentrate and permeate pressure;
feed and permeate TDS; product and concentrate flow; water temperature; running hours), keeping any it already
has, and adds the "RO log sheet" procedure, whose Number steps record each reading on its meter. Attach the
procedure to the machine's service visits so every visit records a complete, comparable set.

Normalisation: readings taken together (on one job, or else on one day) form a log. Against a baseline log
(the first complete one, or one a manager chooses after new membranes), each log gives:

- normalised permeate flow: today's flow corrected to the baseline's net driving pressure and temperature;
- normalised salt passage: today's salt passage corrected to the baseline's net driving pressure;
- normalised pressure drop: feed minus concentrate pressure, corrected to the baseline's average flow (power 1.5).

Net driving pressure = (feed + concentrate pressure)/2 - permeate pressure - osmotic pressure of the average
feed/concentrate water + osmotic pressure of the permeate, with osmotic pressure about 0.7 bar per 1,000 mg/L
and the log-mean concentration along the membranes. Temperature uses the standard correction exp(2640 (1/298 -
1/(273+T))). Missing pieces fall back (no temperature: 25 °C; no permeate pressure: 0; no concentrate flow: 75%
recovery) and are reported, since they make the result less reliable.

Cleaning rules (Techy Ops Settings): clean when normalised flow falls 10%, salt passage rises 10% or pressure
drop rises 15% from the baseline. When the latest log breaks one, a "Membrane cleaning (CIP)" job is raised once
(while it is open, no other) and managers are told.
"""
import math
import re
from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime

from projectit import ops

OSMOTIC = 0.0007  # bar per mg/L
CIP_SUBJECT = "Membrane cleaning (CIP)"
LOG_SHEET = "RO log sheet"
DEFAULT_RECOVERY = 0.75
DEFAULTS = {"cip_flow_drop": 10, "cip_salt_rise": 10, "cip_dp_rise": 15}

# role: (meter name, unit, how to recognise an existing meter by name)
METERS = OrderedDict([
    ("feed_p", ("Feed pressure", "bar", r"feed.*press|press.*feed|^pressure$")),
    ("conc_p", ("Concentrate pressure", "bar", r"(concentrate|reject|brine).*press")),
    ("perm_p", ("Permeate pressure", "bar", r"(permeate|product).*press")),
    ("feed_c", ("Feed TDS", "mg/L", r"(feed|raw).*(tds|conductiv)")),
    ("perm_c", ("Permeate TDS", "mg/L", r"(permeate|product).*(tds|conductiv)")),
    ("perm_q", ("Product flow", "L/h", r"(product|permeate).*flow|^flow$")),
    ("conc_q", ("Concentrate flow", "L/h", r"(concentrate|reject|brine).*flow")),
    ("temp", ("Water temperature", "°C", r"temp")),
])
LOG_STEPS = [("feed_p", True), ("conc_p", True), ("perm_p", False), ("feed_c", True), ("perm_c", True),
    ("perm_q", True), ("conc_q", True), ("temp", True)]


def settings():
    doc = frappe.get_cached_doc("Techy Ops Settings")
    return {k: flt(doc.get(k)) or v for k, v in DEFAULTS.items()}


def roles(equipment):
    """{role: meter row} for the machine's active meters recognised by name."""
    rows = frappe.get_all("Techy Meter", filters={"equipment": equipment, "active": 1}, fields=["name", "meter_name", "unit"])
    found = {}
    for role, (_name, _unit, pattern) in METERS.items():
        for r in rows:
            if r.name not in [m.name for m in found.values()] and re.search(pattern, r.meter_name.strip().lower()):
                found[role] = r
                break
    return found


def tcf(t):
    return math.exp(2640 * (1 / 298.15 - 1 / (273.15 + t)))


def compute(log):
    """Net driving pressure, recovery, salt passage and flows for one log, with what had to be assumed."""
    assumed = []
    qp, pf, cf = log.get("perm_q"), log.get("feed_p"), log.get("feed_c")
    if not qp or pf is None or not cf:
        return None
    t = log.get("temp")
    if t is None:
        t = 25.0
        assumed.append("temperature")
    pp = log.get("perm_p") or 0.0
    pc = log.get("conc_p")
    has_dp = pc is not None
    if pc is None:
        pc = pf - 0.7
        assumed.append("concentrate pressure")
    qc = log.get("conc_q")
    if not qc:
        qc = qp * (1 - DEFAULT_RECOVERY) / DEFAULT_RECOVERY
        assumed.append("concentrate flow")
    r = qp / (qp + qc)
    cfc = cf * math.log(1 / (1 - r)) / r
    cp = log.get("perm_c")
    ndp = (pf + pc) / 2 - pp - OSMOTIC * cfc + OSMOTIC * (cp or 0)
    qf = qp + qc
    return {"ndp": ndp, "tcf": tcf(t), "qp": qp, "sp": cp / cfc if cp is not None and cfc else None,
        "dp": pf - pc if has_dp else None, "qavg": (qf + qc) / 2, "recovery": r, "assumed": assumed}


def logs(equipment, found=None):
    """Readings of the RO meters grouped into logs (a plant log, else a job, else a day), oldest first."""
    found = found or roles(equipment)
    by_meter = {m.name: role for role, m in found.items()}
    if not by_meter:
        return []
    rows = frappe.get_all("Techy Meter Reading", filters={"meter": ["in", list(by_meter)], "reset": 0},
        fields=["meter", "value", "reading_on", "work_order", "plant_log", "unusual", "confirmed"], order_by="reading_on asc",
        limit_page_length=5000)
    # Leave out readings that would throw a whole log: unusual and unconfirmed, or far from the meter's trend
    # (the same check as the Health tab's charts).
    from projectit.health import robust_trend
    drop = set()
    for meter in by_meter:
        mine = [(i, r) for i, r in enumerate(rows) if r.meter == meter]
        drop |= {i for i, r in mine if cint(r.unusual) and not cint(r.confirmed)}
        usable = [(i, r) for i, r in mine if i not in drop]
        keep = {k for k, (_i, r) in enumerate(usable) if cint(r.confirmed)}
        _fit, far = robust_trend([(r.reading_on, flt(r.value)) for _i, r in usable], keep)
        drop |= {usable[k][0] for k in far}
    groups = OrderedDict()
    for i, r in enumerate(rows):
        if i in drop:
            continue
        # One log: a customer's log entry, else a job's readings, else one day's readings.
        key = ("log", r.plant_log) if r.plant_log else ("job", r.work_order) if r.work_order else ("day", getdate(r.reading_on))
        g = groups.setdefault(key, {"on": r.reading_on, "job": r.work_order})
        g[by_meter[r.meter]] = flt(r.value)
        g["on"] = max(get_datetime(g["on"]), get_datetime(r.reading_on))
    return sorted(groups.values(), key=lambda g: get_datetime(g["on"]))


def performance(equipment):
    """Normalised flow, salt passage and pressure drop over time, against the baseline, with the cleaning call."""
    found = roles(equipment)
    missing = [METERS[r][0] for r in METERS if r not in found and r != "perm_p"]
    entries = [(g, compute(g)) for g in logs(equipment, found)]
    entries = [(g, c) for g, c in entries if c]
    rules = settings()
    result = {"meters": {r: m.meter_name for r, m in found.items()}, "missing": missing, "rules": rules,
        "points": [], "baseline": None, "latest": None, "breaches": [], "assumed": [], "cip_job": open_cip(equipment)}
    if not entries:
        return result
    chosen = frappe.db.get_value("Techy Equipment", equipment, "ro_baseline_on")
    base = next(((g, c) for g, c in entries if not chosen or get_datetime(g["on"]) >= get_datetime(chosen)), entries[0])
    bg, b = base
    if b["ndp"] <= 0:
        result["problem"] = _("The baseline log has no net driving pressure: check its readings.")
        return result
    for g, c in entries:
        if get_datetime(g["on"]) < get_datetime(bg["on"]) or c["ndp"] <= 0:
            continue
        npf = c["qp"] * (b["ndp"] / c["ndp"]) * (b["tcf"] / c["tcf"])
        point = {"on": g["on"], "job": g.get("job"), "flow": round(100 * (npf / b["qp"] - 1), 1),
            "salt": round(100 * (c["sp"] * c["ndp"] / b["ndp"] / b["sp"] - 1), 1) if c["sp"] is not None and b["sp"] else None,
            "dp": round(100 * (c["dp"] * (b["qavg"] / c["qavg"]) ** 1.5 / b["dp"] - 1), 1) if c["dp"] and b["dp"] else None,
            "recovery": round(100 * c["recovery"], 1), "assumed": c["assumed"]}
        result["points"].append(point)
    latest = result["points"][-1]
    result.update(baseline={"on": bg["on"], "job": bg.get("job"), "chosen": bool(chosen)}, latest=latest,
        assumed=sorted({a for p in result["points"][-5:] for a in p["assumed"]}),
        breaches=breaches(latest, rules))
    return result


def breaches(point, rules):
    out = []
    if point["flow"] is not None and point["flow"] <= -rules["cip_flow_drop"]:
        out.append(_("normalised flow is down {0}% (clean at {1}%)").format(abs(point["flow"]), rules["cip_flow_drop"]))
    if point["salt"] is not None and point["salt"] >= rules["cip_salt_rise"]:
        out.append(_("normalised salt passage is up {0}% (clean at {1}%)").format(point["salt"], rules["cip_salt_rise"]))
    if point["dp"] is not None and point["dp"] >= rules["cip_dp_rise"]:
        out.append(_("normalised pressure drop is up {0}% (clean at {1}%)").format(point["dp"], rules["cip_dp_rise"]))
    return out


def open_cip(equipment):
    return frappe.db.get_value("Task", {"custom_equipment": equipment, "custom_work_order": 1,
        "subject": ["like", f"{CIP_SUBJECT}%"], "status": ["not in", ["Completed", "Cancelled"]]}, ["name", "subject"], as_dict=True)


ALERT_DAYS = 7  # a customer's logs repeat the same cleaning alert at most once a week


def after_reading(equipment, from_customer=False):
    """After a reading on an RO machine: raise one cleaning job when the latest log breaks a cleaning rule.

    A customer's log raises nothing: the managers are told (at most once a week while it stays broken) and decide."""
    if not equipment:
        return
    try:
        perf = performance(equipment)
        if not perf["breaches"] or perf["cip_job"]:
            return
        from projectit import work_orders
        from projectit.meters import _managers
        reason = "; ".join(perf["breaches"])
        if from_customer:
            key = f"techy_cip_alert:{equipment}"
            if frappe.cache().get_value(key):
                return
            frappe.cache().set_value(key, 1, expires_in_sec=ALERT_DAYS * 86400)
            name = frappe.db.get_value("Techy Equipment", equipment, "equipment_name") or equipment
            ops.notify(_managers(), _("Customer log – {0}: membranes may need cleaning ({1}). No job was raised; decide "
                "what to do.").format(name, reason), "Techy Equipment", equipment)
            return
        # Raised by the cleaning rule, whoever recorded the reading.
        task = work_orders.create(f"{CIP_SUBJECT}: {reason}"[:140],
            _("The latest RO log shows {0}. Clean the membranes (CIP) and record a full RO log afterwards.").format(reason),
            priority="High", category="Preventive", equipment=equipment, ignore_permissions=True)
        ops.notify(_managers(), _("Membranes need cleaning: {0}").format(reason), "Task", task.name)
    except Exception:
        # A reading is never refused because the check after it failed.
        frappe.log_error(title=f"Techy Ops: RO check for {equipment} failed")


# Setting up logging ---------------------------------------------------------------------------------------------

def _log_sheet():
    """The standard RO log sheet procedure (made once; managers may edit it afterwards)."""
    name = frappe.db.get_value("Techy Procedure", {"title": LOG_SHEET})
    if name:
        return name
    steps = [{"field_type": "Heading", "label": _("Readings (with the plant running steadily)")}]
    for role, required in LOG_STEPS:
        meter, unit, _p = METERS[role]
        steps.append({"field_type": "Number", "label": meter, "unit": unit, "meter": meter, "required": int(required)})
    steps += [{"field_type": "Number", "label": "Running hours", "unit": "h", "meter": "Running hours"},
        {"field_type": "Heading", "label": _("Checks")},
        {"field_type": "Pass/Fail", "label": _("No leaks on pumps, vessels and pipework"), "required": 1},
        {"field_type": "Pass/Fail", "label": _("Antiscalant dosing working"), "required": 1},
        {"field_type": "Text", "label": _("Notes")}]
    from projectit.procedures import _clean_steps
    doc = frappe.get_doc({"doctype": "Techy Procedure", "title": LOG_SHEET, "category": "Inspection",
        "description": _("Standard reverse-osmosis log: each reading is recorded on the machine's meter, for "
            "normalised performance and cleaning alerts."), "steps": _clean_steps(steps)})
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist(methods=["POST"])
def setup(equipment):
    """Give a machine the standard RO meters it lacks, and make sure the RO log sheet exists (managers)."""
    ops.system_user()
    ops.require_manager()
    if not frappe.db.exists("Techy Equipment", equipment):
        frappe.throw(_("Equipment {0} was not found.").format(equipment), frappe.DoesNotExistError)
    found = roles(equipment)
    added = []
    for role, (meter, unit, _p) in METERS.items():
        if role in found:
            continue
        frappe.get_doc({"doctype": "Techy Meter", "meter_name": meter, "equipment": equipment, "unit": unit,
            "meter_type": "Gauge", "active": 1}).insert(ignore_permissions=True)
        added.append(meter)
    if not frappe.db.exists("Techy Meter", {"equipment": equipment, "meter_name": "Running hours"}):
        frappe.get_doc({"doctype": "Techy Meter", "meter_name": "Running hours", "equipment": equipment, "unit": "h",
            "meter_type": "Counter", "active": 1}).insert(ignore_permissions=True)
        added.append("Running hours")
    return {"added": added, "procedure": _log_sheet()}


@frappe.whitelist(methods=["POST"])
def set_baseline(equipment, on=None):
    """Compare from this log on (after new membranes, say); without `on`, from the latest log (managers)."""
    ops.system_user()
    ops.require_manager()
    entries = logs(equipment)
    if not entries:
        frappe.throw(_("Record a full RO log first."))
    when = get_datetime(on) if on else get_datetime(entries[-1]["on"])
    frappe.db.set_value("Techy Equipment", equipment, "ro_baseline_on", when)
    frappe.get_doc("Techy Equipment", equipment).add_comment("Info", _("{0} set the RO baseline to the log of {1}.").format(
        frappe.utils.get_fullname(), when.strftime("%d %b %Y")))
    return performance(equipment)
