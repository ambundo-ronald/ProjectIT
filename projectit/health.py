"""Machine health: a score with its reasons, graphs, forecasts, and the starting numbers for the what-if planner
and the reverse-osmosis process model on the machine's Health tab.

Health score (out of 100), from what the app already records about the machine:

- Condition (30): gauge readings against their Above / Below limits (inside, close to a limit, or past it).
- Service (25): services due and not done (meter services past due, overdue preventive jobs, a missed contract
  visit).
- Reliability (20): breakdowns (repair jobs) in the last 90 days.
- Availability (15): hours down in the last 90 days; a machine down now scores nothing here.
- Open repairs (10): repair jobs still open, and whether they are overdue.

A part that does not apply (no limits set, nothing scheduled) is left out and the score is scaled to what is
measured. 80 and over is Good, 60 to 79 Watch, below 60 At risk; a machine that is down now is At risk.

Forecasts are straight-line projections of recent readings and history, each with how far to trust it:

- readings flagged unusual when typed (and not confirmed), or far from the trend, are left out and listed;
- confidence is High, Medium or Low from the number of readings, the time they span, how fresh the latest one
  is and (gauges) how well a straight line fits;
- dates come as a range: the dates at the trend's likely fastest and slowest rates (about 80% likely).

Meters not read for 45 days do not count towards Condition. The planner and the process model run in the browser
from the numbers returned here. Costs (parts at stock cost plus labour at the cost per hour) are for
managers only.
"""
import re
from collections import Counter, defaultdict
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, get_datetime, getdate, now_datetime, nowdate

from projectit import ops

SCORE_DAYS = 90
STALE_DAYS = 45  # a reading older than this no longer says how the machine is now
Z80 = 1.28  # an ~80% range around a rate
MIN_HISTORY_DAYS = 30  # rates per year and breakdown forecasts need at least this much history
MAX_POINTS = 200
NEAR = 0.1  # within 10% of a limit counts as close
PROCESS_HINTS = re.compile(r"\b(ro|reverse osmosis|osmosis|desal)\b", re.I)
JOB_FIELDS = ["name", "subject", "status", "creation", "modified", "custom_completed_at", "custom_work_category",
    "exp_end_date", "custom_machine_down", "custom_down_from", "custom_down_to", "custom_problem_code",
    "custom_labour_hours", "custom_down_answered"]


def _days_between(a, b):
    return (get_datetime(b) - get_datetime(a)).total_seconds() / 86400


def trend(points):
    """Least-squares rate per day from [(datetime, value)], with the fitted value at the last reading, the rate's
    standard error, R² and each point's residual. None with fewer than 2 points or no time between them."""
    if len(points) < 2:
        return None
    t0 = get_datetime(points[0][0])
    xs = [_days_between(t0, p[0]) for p in points]
    ys = [flt(p[1]) for p in points]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var < 1e-9:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    residuals = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in residuals)
    sst = sum((y - my) ** 2 for y in ys)
    se = (sse / (n - 2) / var) ** 0.5 if n > 2 else abs(slope)
    return {"rate": slope, "at_last": my + slope * (xs[-1] - mx), "last_on": get_datetime(points[-1][0]), "se": se,
        "r2": 1 - sse / sst if sst > 1e-12 else 1.0, "residuals": residuals, "n": n, "span": xs[-1] - xs[0]}


def robust_trend(points, keep=()):
    """trend() without the readings far from the line (over 3.5 robust spreads), refitted once. Points whose index
    is in `keep` (readings confirmed by the person) always count. Returns (fit, indexes left out)."""
    fit = trend(points)
    if not fit or fit["n"] < 5:
        return fit, []
    abs_res = sorted(abs(r) for r in fit["residuals"])
    spread = 1.4826 * abs_res[len(abs_res) // 2]
    if spread <= 1e-9:
        return fit, []
    out = [i for i, r in enumerate(fit["residuals"]) if abs(r) > 3.5 * spread and i not in keep]
    if not out:
        return fit, []
    kept = [p for i, p in enumerate(points) if i not in out]
    return trend(kept) or fit, out


def confidence(fit, last_age_days, kind):
    """High / Medium / Low, and why, for a projection from this fit."""
    if not fit:
        return {"level": "Low", "why": _("Too few readings.")}
    why = _("{0} readings over {1} days; the latest is {2} days old.").format(fit["n"], int(fit["span"]), int(last_age_days))
    if last_age_days > STALE_DAYS:
        return {"level": "Low", "why": why + " " + _("Readings are out of date.")}
    fits = kind == "Counter" or fit["r2"] >= 0.5
    if fit["n"] >= 8 and fit["span"] >= 30 and fits:
        return {"level": "High", "why": why}
    if fit["n"] >= 4 and fit["span"] >= 14:
        return {"level": "Medium", "why": why + ("" if fits else " " + _("The readings vary a lot around the trend."))}
    return {"level": "Low", "why": why}


def _reach(start_value, target, rate, start_on, limit_days):
    """When a line from start_value at `rate` per day reaches target (None if never, or after limit_days)."""
    if abs(rate) < 1e-12:
        return None
    days = (target - start_value) / rate
    return start_on + timedelta(days=days) if 0 <= days <= limit_days else None


def _thin(points, limit=MAX_POINTS):
    if len(points) <= limit:
        return points
    step = len(points) / limit
    return [points[int(i * step)] for i in range(limit - 1)] + [points[-1]]


def meter_series(meter, since):
    """Readings for the chart, its limits and a forecast (counters: next service; gauges: a limit crossing), with
    the readings left out of the trend and how far to trust the forecast."""
    rows = frappe.get_all("Techy Meter Reading", filters={"meter": meter.name, "reading_on": [">=", since]},
        fields=["value", "reading_on", "reset", "unusual", "confirmed"], order_by="reading_on asc, creation asc",
        limit_page_length=2000)
    points = [(r.reading_on, flt(r.value)) for r in rows]
    # A reset starts the counter again: judge and forecast from the readings since the last reset.
    resets = [i for i, r in enumerate(rows) if cint(r.reset)]
    first = resets[-1] if resets else 0
    since_reset = list(range(first, len(rows)))
    # Left out: flagged unusual when typed (and not confirmed), or far from the trend over the whole chart period.
    flagged = {i for i in since_reset if cint(rows[i].unusual) and not cint(rows[i].confirmed)}
    candidates = [i for i in since_reset if i not in flagged]
    keep = {k for k, i in enumerate(candidates) if cint(rows[i].confirmed)}
    _fit_all, far = robust_trend([points[i] for i in candidates], keep)
    left_out = sorted(flagged | {candidates[k] for k in far})
    excluded = [{"on": rows[i].reading_on, "value": flt(rows[i].value), "why": _("Marked unusual when recorded")
        if i in flagged else _("Far from the trend")} for i in left_out]
    # The forecast: the last 90 days of good readings (or the last ten).
    good = [i for i in since_reset if i not in left_out]
    window = [i for i in good if _days_between(rows[i].reading_on, now_datetime()) <= SCORE_DAYS]
    if len(window) < 2:
        window = good[-10:]
    fit = trend([points[i] for i in window])
    limits = [{"type": t.trigger_type, "value": flt(t.value)} for t in meter.triggers if t.trigger_type in ("Above", "Below")]
    every = next((t for t in meter.triggers if t.trigger_type == "Every"), None)
    trusted = [points[i] for i in good]
    last = trusted[-1] if trusted else (points[-1] if points else None)
    last_age = _days_between(last[0], now_datetime()) if last else None
    trust = confidence(fit, last_age or 0, meter.meter_type) if points else None
    forecast = None
    now = now_datetime()
    if fit and last:
        last_on, last_value = get_datetime(last[0]), last[1]
        low, high = fit["rate"] - Z80 * fit["se"], fit["rate"] + Z80 * fit["se"]
        if meter.meter_type == "Counter" and every and every.next_due is not None and fit["rate"] > 0:
            on = _reach(last_value, flt(every.next_due), fit["rate"], last_on, 730)
            if on:
                on = max(on, now)
                forecast = {"kind": "service", "rate_per_day": round(fit["rate"], 3), "on": on, "target": flt(every.next_due),
                    "earliest": max(_reach(last_value, flt(every.next_due), high, last_on, 730) or on, now),
                    "latest": _reach(last_value, flt(every.next_due), low, last_on, 730) if low > 0 else None,
                    "line": [(last_on, last_value), (on, flt(every.next_due))]}
        elif meter.meter_type == "Gauge" and abs(fit["rate"]) > 1e-9:
            for limit in limits:
                heading = (limit["type"] == "Above" and fit["rate"] > 0 and last_value < limit["value"]) or \
                    (limit["type"] == "Below" and fit["rate"] < 0 and last_value > limit["value"])
                on = heading and _reach(last_value, limit["value"], fit["rate"], last_on, 365)
                if on:
                    steep, shallow = (high, low) if fit["rate"] > 0 else (low, high)
                    same_way = (shallow > 0) == (fit["rate"] > 0)
                    forecast = {"kind": "limit", "rate_per_day": round(fit["rate"], 4), "on": on, "target": limit["value"],
                        "limit": limit["type"], "earliest": max(_reach(last_value, limit["value"], steep, last_on, 365) or on, now),
                        "latest": _reach(last_value, limit["value"], shallow, last_on, 365) if same_way else None,
                        "line": [(last_on, last_value), (on, limit["value"])]}
                    break
            if not forecast:
                end_on = last_on + timedelta(days=60)
                forecast = {"kind": "trend", "rate_per_day": round(fit["rate"], 4), "on": None,
                    "line": [(last_on, last_value), (end_on, last_value + fit["rate"] * 60)]}
        if forecast:
            forecast["confidence"] = trust
    return {"name": meter.name, "meter_name": meter.meter_name, "unit": meter.unit or "", "meter_type": meter.meter_type,
        "points": [{"on": p[0], "value": p[1]} for p in _thin([q for i, q in enumerate(points) if i not in set(left_out)])],
        "limits": limits, "excluded": excluded,
        "next_due": flt(every.next_due) if every and every.next_due is not None else None,
        "every": flt(every.value) if every else None, "last": last[1] if last else None,
        "last_on": last[0] if last else None, "stale": last_age is not None and last_age > STALE_DAYS,
        "confidence": trust,
        "forecast": forecast and {**forecast, "line": [{"on": a, "value": round(b, 3)} for a, b in forecast["line"]]}}


def _condition(series):
    """Points for gauge readings against their limits; None when no gauge has limits."""
    judged = []
    notes = []
    stale = []
    for s in series:
        if s["meter_type"] != "Gauge" or not s["limits"] or s["last"] is None:
            continue
        if s["stale"]:
            stale.append(s["meter_name"])
            continue
        worst = 1.0
        for limit in s["limits"]:
            v, lim = s["last"], limit["value"]
            past = v > lim if limit["type"] == "Above" else v < lim
            margin = abs(lim) * NEAR or NEAR
            close = (lim - v <= margin) if limit["type"] == "Above" else (v - lim <= margin)
            if past:
                worst = 0.0
                notes.append(_("{0} is {1} its limit ({2} {3})").format(s["meter_name"],
                    _("above") if limit["type"] == "Above" else _("below"), ops_num(lim), s["unit"]))
            elif close and worst > 0.5:
                worst = 0.5
                notes.append(_("{0} is close to its limit ({1} {2})").format(s["meter_name"], ops_num(lim), s["unit"]))
        judged.append(worst)
    old = _("Not read for {0} days, so not counted: {1}.").format(STALE_DAYS, ", ".join(stale)) if stale else ""
    if not judged:
        return {"share": None, "detail": old} if stale else None
    detail = "; ".join(notes) or _("All recent readings are inside their limits.")
    return {"share": sum(judged) / len(judged), "detail": f"{detail} {old}".strip()}


def ops_num(v):
    v = flt(v)
    return f"{v:,.0f}" if v == int(v) else f"{v:,.2f}".rstrip("0").rstrip(".")


def score(row, series, jobs, service_due, down_hours, down_now, open_repairs):
    today = getdate(nowdate())
    factors = []

    def add(key, label, maximum, share, detail):
        factors.append({"key": key, "label": label, "max": maximum,
            "points": None if share is None else round(maximum * max(0.0, min(1.0, share)), 1), "detail": detail})

    cond = _condition(series)
    add("condition", _("Condition"), 30, cond["share"] if cond else None, cond["detail"] if cond else _("No readings with limits yet."))
    if service_due is None:
        add("service", _("Service"), 25, None, _("No service schedule (meter service, PM job or contract visits)."))
    else:
        add("service", _("Service"), 25, 1 - 0.5 * len(service_due),
            "; ".join(service_due) if service_due else _("Services are up to date."))
    since = getdate(add_days(today, -SCORE_DAYS))
    breakdowns = [j for j in jobs if j.custom_work_category == "Corrective" and getdate(j.creation) >= since]
    add("reliability", _("Reliability"), 20, {0: 1, 1: 0.7, 2: 0.4}.get(len(breakdowns), 0.1),
        _("{0} breakdown(s) in the last {1} days.").format(len(breakdowns), SCORE_DAYS))
    availability = max(0.0, 100 * (1 - down_hours / (SCORE_DAYS * 24)))
    share = 0 if down_now else 1 if availability >= 99 else 0.75 if availability >= 97 else 0.45 if availability >= 95 else 0.2
    add("availability", _("Availability"), 15, share, _("Down now.") if down_now else
        _("{0}% available in the last {1} days ({2} h down).").format(round(availability, 1), SCORE_DAYS, round(down_hours, 1)))
    overdue = [j for j in open_repairs if j.exp_end_date and getdate(j.exp_end_date) < today]
    share = 1 if not open_repairs else 0.6 if len(open_repairs) == 1 and not overdue else 0.3 if len(open_repairs) == 1 else 0.2
    add("repairs", _("Open repairs"), 10, share, _("No open repairs.") if not open_repairs else
        _("{0} open, {1} overdue.").format(len(open_repairs), len(overdue)))
    used = [f for f in factors if f["points"] is not None]
    total = round(100 * sum(f["points"] for f in used) / sum(f["max"] for f in used)) if used else None
    if total is not None and down_now:
        total = min(total, 40)
    grade = None if total is None else "Good" if total >= 80 else "Watch" if total >= 60 else "At risk"
    return {"score": total, "grade": grade, "factors": factors}


def _service_due(row, series, jobs):
    """What is due and not done; None when the machine has no service schedule at all."""
    today = getdate(nowdate())
    due, scheduled = [], False
    for s in series:
        if s["next_due"] is not None:
            scheduled = True
            if s["last"] is not None and s["last"] >= s["next_due"]:
                due.append(_("{0} service is due ({1} {2})").format(s["meter_name"], ops_num(s["next_due"]), s["unit"]))
    pm = [j for j in jobs if j.custom_work_category == "Preventive"]
    if pm:
        scheduled = True
    for j in pm:
        if j.status not in ("Completed", "Cancelled") and j.exp_end_date and getdate(j.exp_end_date) < today:
            due.append(_("Preventive job overdue: {0}").format(j.subject))
    if row.service_contract:
        visit = frappe.db.get_value("Techy Contract Equipment", {"parent": row.service_contract,
            "parenttype": "Techy Service Contract", "equipment": row.name}, "next_visit")
        if visit:
            scheduled = True
            if getdate(visit) < today:
                due.append(_("Contract visit was due {0}").format(getdate(visit).strftime("%d %b")))
    return due if scheduled else None


def _down(jobs, start, end):
    """Hours down between start and end, whether it is down now, and each stop's repair time."""
    hours, now_down, repairs = 0.0, False, []
    for j in jobs:
        if not cint(j.custom_machine_down) or not j.custom_down_from:
            continue
        a = get_datetime(j.custom_down_from)
        b = get_datetime(j.custom_down_to) if j.custom_down_to else now_datetime()
        overlap = (min(b, end) - max(a, start)).total_seconds() / 3600
        if overlap > 0:
            hours += overlap
        if not j.custom_down_to:
            now_down = True
        else:
            repairs.append((b - a).total_seconds() / 3600)
    return hours, now_down, repairs


def months(jobs, costs, start):
    """Twelve calendar months: jobs opened by kind, hours down and (managers) cost."""
    result = []
    first = getdate(start).replace(day=1)
    for i in range(12):
        m0 = getdate(add_months(first, i))
        m1 = getdate(add_months(first, i + 1))
        a, b = get_datetime(m0), min(get_datetime(m1), now_datetime())
        opened = [j for j in jobs if m0 <= getdate(j.creation) < m1]
        down, _now, _r = _down(jobs, a, b) if a < b else (0, False, [])
        result.append({"label": m0.strftime("%b %y" if i == 0 or m0.month == 1 else "%b"), "month": m0,
            "repairs": sum(1 for j in opened if j.custom_work_category == "Corrective"),
            "services": sum(1 for j in opened if j.custom_work_category in ("Preventive", "Inspection")),
            "other": sum(1 for j in opened if j.custom_work_category not in ("Corrective", "Preventive", "Inspection")),
            "down_hours": round(down, 1),
            "cost": None if costs is None else round(sum(c for d, c in costs if m0 <= getdate(d) < m1), 2)})
    return result


def _job_costs(jobs):
    """[(completed on, cost)] for completed jobs: parts at stock cost plus labour at the cost per hour."""
    from projectit import reports, timer
    done = [j for j in jobs if j.status == "Completed"]
    parts = reports.parts_cost(j.name for j in done)
    logged = timer.hours_by_person([j.name for j in done])
    rate = flt(frappe.get_cached_doc("Techy Ops Settings").get("labour_cost_rate"))
    out = []
    for j in done:
        hours = sum(logged[j.name].values()) if logged.get(j.name) else flt(j.custom_labour_hours)
        out.append((j.custom_completed_at or j.modified, parts.get(j.name, 0) + hours * rate, j))
    return out, rate


def _process_inputs(row, series):
    """Starting numbers for the RO model: the machine's own readings where meters exist, else typical values."""
    name = f"{row.equipment_name or ''} {row.item_code or ''}"
    meters = {s["meter_name"].lower(): s for s in series}
    relevant = bool(PROCESS_HINTS.search(name)) or any("tds" in k for k in meters)
    if not relevant:
        return None

    def reading(*words):
        for key, s in meters.items():
            if all(w in key for w in words) and s["last"] is not None:
                return {"value": s["last"], "meter": s["meter_name"]}
        return None

    capacity = re.search(r"(\d[\d,]*)\s*(lph|l/h|lpd|gpd|m3/d|m³/d)", name, re.I)
    lph = None
    if capacity:
        value = flt(capacity.group(1).replace(",", ""))
        unit = capacity.group(2).lower()
        lph = value if unit in ("lph", "l/h") else value / 24 if unit == "lpd" else value * 3.785 / 24 if unit == "gpd" else value * 1000 / 24
    found = {"feed_tds": reading("feed", "tds") or reading("raw", "tds"),
        "permeate_tds": reading("permeate", "tds") or reading("product", "tds"),
        "pressure": reading("feed", "pressure") or reading("pressure"),
        "permeate_flow": reading("permeate", "flow") or reading("product", "flow"),
        "recovery": reading("recovery"), "temperature": reading("temp")}
    return {"capacity_lph": lph or 500, "from_name": bool(lph), "readings": {k: v for k, v in found.items() if v},
        "installed_on": row.installed_on}


@frappe.whitelist()
def machine_health(equipment):
    """Everything the Health tab shows for one machine."""
    ops.system_user()
    row = frappe.db.get_value("Techy Equipment", equipment, ["name", "equipment_name", "item_code", "status",
        "installed_on", "delivered_on", "service_contract", "warranty_until"], as_dict=True)
    if not row:
        frappe.throw(_("Equipment {0} was not found.").format(equipment), frappe.DoesNotExistError)
    manager = ops.manager()
    now = now_datetime()
    start = get_datetime(add_months(getdate(nowdate()).replace(day=1), -11))
    meters = [frappe.get_doc("Techy Meter", n) for n in frappe.get_all("Techy Meter", filters={"equipment": row.name,
        "active": 1}, pluck="name", order_by="creation asc", limit_page_length=30)]
    series = [meter_series(m, start) for m in meters]
    base = {"custom_work_order": 1, "is_template": 0, "parent_task": ["is", "not set"], "custom_equipment": row.name,
        "status": ["!=", "Cancelled"]}
    jobs = frappe.get_all("Task", filters={**base, "creation": [">=", start]}, fields=JOB_FIELDS, limit_page_length=0)
    seen = {j.name for j in jobs}
    jobs += [j for j in frappe.get_all("Task", filters={**base, "status": ["not in", ["Completed", "Cancelled"]]},
        fields=JOB_FIELDS, limit_page_length=0) if j.name not in seen]
    # Downtime that began before the window but ran into it.
    jobs += [j for j in frappe.get_all("Task", filters={**base, "custom_machine_down": 1, "creation": ["<", start]},
        or_filters=[["custom_down_to", ">=", start], ["custom_down_to", "is", "not set"]], fields=JOB_FIELDS,
        limit_page_length=0) if j.name not in seen]
    open_repairs = [j for j in jobs if j.custom_work_category == "Corrective" and j.status not in ("Completed", "Cancelled")]
    down_hours, down_now, _r = _down(jobs, now - timedelta(days=SCORE_DAYS), now)
    health = score(row, series, jobs, _service_due(row, series, jobs), down_hours, down_now, open_repairs)

    costs, rate = _job_costs(jobs) if manager else (None, None)
    chart = months(jobs, [(d, c) for d, c, _j in costs] if costs is not None else None, start)
    codes = Counter(j.custom_problem_code for j in jobs if j.custom_problem_code)
    titles = dict(frappe.get_all("Techy Failure Code", filters={"name": ["in", list(codes)]}, fields=["name", "title"],
        as_list=True)) if codes else {}
    failures = [{"code": c, "title": titles.get(c, c), "jobs": n} for c, n in codes.most_common(6)]

    # Breakdowns over the year: time between them and the next one at that pace.
    in_service = get_datetime(row.installed_on or row.delivered_on) if (row.installed_on or row.delivered_on) else start
    span_from = max(start, in_service)
    repairs = sorted((j for j in jobs if j.custom_work_category == "Corrective" and get_datetime(j.creation) >= start),
        key=lambda j: j.creation)
    _h, _n, repair_times = _down(jobs, start, now)
    observed = _days_between(span_from, now)
    enough = observed >= MIN_HISTORY_DAYS  # a few days of history would give nonsense yearly rates
    running_days = max(1.0, observed - (_h / 24))
    mtbf = running_days / len(repairs) if repairs and enough else None
    next_breakdown = (get_datetime(repairs[-1].creation) + timedelta(days=mtbf)) if mtbf else None
    year_fraction = min(1.0, max(observed, 1) / 365)
    per_year = lambda n: round(n / year_fraction, 1) if enough else None
    events = len(repairs)
    breakdown_trust = {"level": "High" if events >= 6 else "Medium" if events >= 3 else "Low",
        "why": _("Based on {0} breakdown(s) in {1} days.").format(events, int(observed))}
    forecasts = {"history_days": int(observed), "enough_history": enough, "mtbf_days": round(mtbf, 1) if mtbf else None,
        "next_breakdown": max(next_breakdown, now) if next_breakdown else None,
        "breakdown_range": [max(get_datetime(repairs[-1].creation) + timedelta(days=mtbf * 0.5), now),
            get_datetime(repairs[-1].creation) + timedelta(days=mtbf * 1.5)] if mtbf else None,
        "breakdown_confidence": breakdown_trust if mtbf else None,
        "breakdowns_per_year": per_year(len(repairs)),
        "mttr_hours": round(sum(repair_times) / len(repair_times), 1) if repair_times else None,
        "meters": [{"meter": s["meter_name"], "unit": s["unit"], **{k: s["forecast"].get(k) for k in ("kind", "on", "target",
            "rate_per_day", "earliest", "latest", "confidence", "limit")}} for s in series if s["forecast"] and s["forecast"]["kind"] != "trend"]}

    # What-if planner: the main counter (running hours if there is one) and this year's costs.
    counters = [s for s in series if s["meter_type"] == "Counter" and s["forecast"]]
    main = next((s for s in counters if re.search(r"hour|hrs|\bh\b", f"{s['meter_name']} {s['unit']}", re.I)), counters[0] if counters else None)
    planner = {"meter": main and {"name": main["meter_name"], "unit": main["unit"], "per_day": main["forecast"]["rate_per_day"],
        "every": main["every"]}, "breakdowns_per_year": forecasts["breakdowns_per_year"],
        "mttr_hours": forecasts["mttr_hours"] or 4, "services_per_year": per_year(sum(1 for j in jobs
            if j.custom_work_category == "Preventive" and get_datetime(j.creation) >= start))}
    if costs is not None:
        def avg(kind):
            values = [c for _d, c, j in costs if j.custom_work_category == kind]
            return round(sum(values) / len(values), 2) if values else None
        planner.update(cost_per_service=avg("Preventive"), cost_per_breakdown=avg("Corrective"), labour_rate=rate)
        forecasts["cost_next_year"] = round(sum(c for _d, c, _j in costs) / year_fraction, 2) if enough else None
    process = _process_inputs(row, series)
    ro_perf = None
    if process:
        from projectit import ro
        ro_perf = ro.performance(row.name)
        # Fouling from normalised flow is the better measure: temperature and pressure are taken out.
        pts = ro_perf["points"]
        if len(pts) >= 3:
            fit = trend([(p["on"], p["flow"]) for p in pts[-12:]])
            if fit and fit["rate"] < 0:
                process["normalised_fouling"] = round(-fit["rate"] * 365, 1)
    year_repairs = [j for j in jobs if j.custom_work_category == "Corrective" and get_datetime(j.creation) >= start]
    data = {"meters": len(series), "stale": [s["meter_name"] for s in series if s["stale"] or s["last"] is None],
        "readings_90": sum(1 for s in series for p in s["points"] if _days_between(p["on"], now) <= SCORE_DAYS),
        "left_out": sum(len(s["excluded"]) for s in series),
        "repairs": len(year_repairs),
        "uncoded": sum(1 for j in year_repairs if not j.custom_problem_code),
        "downtime_unknown": sum(1 for j in year_repairs if j.status == "Completed" and not cint(j.custom_machine_down)
            and not cint(j.get("custom_down_answered"))),
        "untimed": sum(1 for j in jobs if j.status == "Completed" and get_datetime(j.creation) >= start
            and not flt(j.custom_labour_hours)) if manager else None,
        "labour_rate_set": bool(rate) if manager else None}
    return {"machine": {"name": row.name, "equipment_name": row.equipment_name, "status": row.status}, "data": data,
        "health": {**health, "down_now": down_now}, "meters": series, "months": chart, "failures": failures,
        "forecasts": forecasts, "planner": planner, "process": process, "ro": ro_perf, "manager": manager,
        "currency": frappe.db.get_default("currency"), "as_of": now}
