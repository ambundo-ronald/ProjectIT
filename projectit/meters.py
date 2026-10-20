"""Meter readings on machines, and the jobs they trigger.

A Techy Meter belongs to customer equipment or to one of our Assets. A Counter only goes up (running
hours, water produced); a Gauge goes up and down (TDS, pressure). Technicians record readings from the
machine or job page. Each meter's triggers raise jobs by themselves:

- Every N: a Preventive job each time a counter passes its next due reading, which then moves on by N.
- Above / Below: a High-priority Corrective job when a reading crosses the limit.

A trigger raises one job at a time: while its job is open, later readings past the limit are added to
that job as comments instead of raising another. Managers are notified of each job raised.

Items can list standard meters (Item > Techy Ops Meters); every new machine of the item gets them, so the
commissioning procedure's Number steps that name a meter record its first readings.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from projectit import ops

TYPES = ("Counter", "Gauge")
TRIGGERS = ("Every", "Above", "Below")
PRIORITIES = ("Low", "Medium", "High", "Urgent")
CLOSED = ("Completed", "Cancelled")
METER_FIELDS = ["name", "meter_name", "equipment", "asset", "unit", "meter_type", "active", "last_reading",
    "last_reading_on", "last_reading_by", "notes"]
MAX_VALUE = 1e12


def fmt(value):
    value = flt(value)
    return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}".rstrip("0").rstrip(".")


def _check_machine(equipment=None, asset=None):
    ops.system_user()
    if bool(equipment) == bool(asset):
        frappe.throw(_("Choose one machine."))
    if asset:
        ops.require_asset_access()
        if not frappe.db.exists("Asset", asset):
            frappe.throw(_("Asset {0} was not found.").format(asset), frappe.DoesNotExistError)
    elif not frappe.db.exists("Techy Equipment", equipment):
        frappe.throw(_("Equipment {0} was not found.").format(equipment), frappe.DoesNotExistError)


def _meter(name, for_update=False):
    doc = frappe.get_doc("Techy Meter", name, for_update=for_update)
    _check_machine(doc.equipment, doc.asset)
    return doc


def _managers():
    users = frappe.get_all("Has Role", filters={"role": ["in", list(ops.MANAGER_ROLES - {"System Manager"})],
        "parenttype": "User"}, pluck="parent")
    return frappe.get_all("User", filters={"name": ["in", users or [""]], "enabled": 1, "user_type": "System User"},
        pluck="name")


def _job(name):
    if not name:
        return None
    return frappe.db.get_value("Task", name, ["name", "subject", "status"], as_dict=True)


def is_open(job):
    return bool(job) and job.status not in CLOSED


def trigger_label(meter, row):
    unit = meter.get("unit") or ""
    if row.trigger_type == "Every":
        return _("Service every {0} {1}").format(fmt(row.value), unit).strip()
    return _("Job when {0} {1} {2}").format(_("above") if row.trigger_type == "Above" else _("below"),
        fmt(row.value), unit).strip()


def forecast(readings, next_due):
    """Date a counter should reach next_due at its recent rate of use (readings newest first)."""
    recent = [r for r in readings if not r.get("reset")][:30]
    if len(recent) < 2 or next_due is None:
        return None
    newest, oldest = recent[0], recent[-1]
    days = (get_datetime(newest.reading_on) - get_datetime(oldest.reading_on)).total_seconds() / 86400
    rise = flt(newest.value) - flt(oldest.value)
    if days < 1 or rise <= 0:
        return None
    remaining = flt(next_due) - flt(newest.value)
    ahead = max(0, remaining) / (rise / days)
    if ahead >= 3650:
        return None
    # Never in the past: a counter already due (or read long ago) is due now.
    return max(getdate(add_days(getdate(newest.reading_on), int(ahead))), getdate(nowdate()))


def summary(meter, readings=None):
    if readings is None:
        readings = frappe.get_all("Techy Meter Reading", filters={"meter": meter.name},
            fields=["value", "reading_on", "reset"], order_by="reading_on desc, creation desc", limit_page_length=30)
    triggers = []
    for row in meter.get("triggers") or []:
        job = _job(row.open_job)
        triggers.append({"name": row.name, "trigger_type": row.trigger_type, "value": row.value,
            "label": trigger_label(meter, row), "next_due": row.next_due if row.trigger_type == "Every" else None,
            "due_on": forecast(readings, row.next_due) if row.trigger_type == "Every" and meter.meter_type == "Counter" else None,
            "job_title": row.job_title, "priority": row.priority, "procedure": row.procedure,
            "open_job": job if is_open(job) else None})
    alert = any(t["open_job"] and t["trigger_type"] != "Every" for t in triggers)
    return {"name": meter.name, "meter_name": meter.meter_name, "unit": meter.unit, "meter_type": meter.meter_type,
        "active": cint(meter.active), "equipment": meter.equipment, "asset": meter.asset, "notes": meter.notes,
        "last_reading": meter.last_reading if meter.last_reading_on else None, "last_reading_on": meter.last_reading_on,
        "last_reading_by": frappe.utils.get_fullname(meter.last_reading_by) if meter.last_reading_by else None,
        "triggers": triggers, "alert": alert,
        "trend": [{"value": r.value, "on": r.reading_on} for r in reversed(readings[:12])]}


def for_machine(equipment=None, asset=None, include_inactive=False):
    """Meters on a machine, for the machine and job pages (callers have checked access)."""
    if not equipment and not asset:
        return []
    filters = {"equipment": equipment} if equipment else {"asset": asset}
    if not include_inactive:
        filters["active"] = 1
    return [summary(frappe.get_doc("Techy Meter", name)) for name in
        frappe.get_all("Techy Meter", filters=filters, pluck="name", order_by="creation asc, name asc", limit_page_length=50)]


@frappe.whitelist()
def list_meters(equipment=None, asset=None):
    _check_machine(equipment, asset)
    return {"meters": for_machine(equipment, asset, include_inactive=ops.manager()), "manager": ops.manager()}


@frappe.whitelist()
def get_meter(name):
    doc = _meter(name)
    rows = frappe.get_all("Techy Meter Reading", filters={"meter": doc.name}, fields=["name", "value", "reading_on",
        "recorded_by", "work_order", "triggered_job", "reset", "note"], order_by="reading_on desc, creation desc",
        limit_page_length=200)
    for row in rows:
        row.recorded_by_name = frappe.utils.get_fullname(row.recorded_by) if row.recorded_by else ""
    return {"meter": summary(doc, rows[:30]), "readings": rows, "manager": ops.manager()}


# Recording -----------------------------------------------------------------------------------------------------

def _value(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        frappe.throw(_("Enter the reading as a number."))
    if value != value or abs(value) >= MAX_VALUE:
        frappe.throw(_("Enter the reading as a number."))
    return value


CHECK_HISTORY = 12


def unusual(doc, value):
    """Why a new reading looks wrong next to this meter's recent readings, or None when it looks fine.

    Gauges: far from the median of recent readings (five times their usual spread, which is at least 5% of the
    median). Counters: a rise much bigger than the meter's usual rate over the time since the last reading."""
    rows = frappe.get_all("Techy Meter Reading", filters={"meter": doc.name, "reset": 0}, fields=["value", "reading_on"],
        order_by="reading_on desc, creation desc", limit_page_length=CHECK_HISTORY)
    unit = doc.unit or ""
    if doc.meter_type == "Gauge":
        if len(rows) < 4:
            return None
        values = sorted(flt(r.value) for r in rows)
        median = values[len(values) // 2]
        spread = sorted(abs(v - median) for v in values)[len(values) // 2] * 1.4826
        spread = max(spread, abs(median) * 0.05, 1e-6)
        if abs(value - median) > 5 * spread:
            return _("{0} {1} is far from this meter's usual readings (around {2} {1}).").format(fmt(value), unit, fmt(median))
        return None
    if len(rows) < 3 or not doc.last_reading_on:
        return None
    days = (get_datetime(rows[0].reading_on) - get_datetime(rows[-1].reading_on)).total_seconds() / 86400
    rate = (flt(rows[0].value) - flt(rows[-1].value)) / days if days >= 1 else 0
    if rate <= 0:
        return None
    since = max((now_datetime() - get_datetime(doc.last_reading_on)).total_seconds() / 86400, 1)
    rise = value - flt(doc.last_reading)
    if rise > max(3 * rate * since, rate * (since + 7)):
        return _("That is {0} {1} more in {2} day(s); it usually goes up about {3} {1} a day.").format(
            fmt(rise), unit, int(round(since)), fmt(rate))
    return None


def _job_for_reading(work_order, meter):
    """A reading taken on a job must be for that job's machine, by someone who can see the job."""
    if not work_order:
        return None
    from projectit import work_orders
    task = work_orders._work_order(work_order)
    if (meter.equipment and task.custom_equipment != meter.equipment) or (meter.asset and task.custom_asset != meter.asset):
        frappe.throw(_("This meter is not on the job's machine."))
    return task.name


@frappe.whitelist(methods=["POST"])
def record_reading(meter, value, work_order=None, note=None, reset=0, confirm=0):
    """Record a reading. An unusual one is not saved until the person confirms it (`confirm=1`); a reading sent
    later from a phone that was offline (`confirm=2`) is saved and marked unusual without asking."""
    doc = _meter(meter, for_update=True)
    reset = bool(cint(reset))
    if reset and not ops.manager():
        frappe.throw(_("Only managers can record a replaced or reset meter."), frappe.PermissionError)
    job = _job_for_reading(work_order, doc)
    warning = None if reset else unusual(doc, _value(value))
    if warning and not cint(confirm):
        return {"needs_confirm": True, "warning": warning}
    reading, raised = _record(doc, value, job, ops.text(note, "a note", 280, required=False), reset,
        flagged=bool(warning), confirmed=bool(warning) and cint(confirm) == 1)
    if job:
        frappe.get_doc("Task", job).add_comment("Info", escape(_("{0} recorded {1}: {2} {3}.").format(
            frappe.utils.get_fullname(), doc.meter_name, fmt(reading.value), doc.unit)))
    return {"meter": summary(doc), "raised": [{"name": t.name, "subject": t.subject} for t in raised]}


def _record(doc, value, job=None, note=None, reset=False, flagged=False, confirmed=False, source=None, plant_log=None,
        when=None, check_ro=True):
    """Save a reading on a locked meter and run its triggers; returns (reading, jobs raised).

    A customer's reading (source "Customer", from the plant app) never raises a job: it tells the managers instead,
    once, when it first sets off a trigger. `when` is the time it was taken (a log sent later from a phone that was
    offline); `check_ro=False` leaves the RO cleaning check to the caller, who runs it once for a whole log."""
    if not cint(doc.active):
        frappe.throw(_("{0} is no longer in use.").format(doc.meter_name))
    value = _value(value)
    if doc.meter_type == "Counter" and doc.last_reading_on and value < flt(doc.last_reading) and not reset:
        frappe.throw(_("{0} only goes up: the last reading was {1} {2}. If the meter was replaced or reset, ask a manager "
            "to record it.").format(doc.meter_name, fmt(doc.last_reading), doc.unit))
    if doc.meter_type == "Counter" and value < 0:
        frappe.throw(_("A counter reading cannot be negative."))
    previous = flt(doc.last_reading) if doc.last_reading_on else None
    reading = frappe.get_doc({"doctype": "Techy Meter Reading", "meter": doc.name, "value": value,
        "reading_on": when or now_datetime(), "recorded_by": frappe.session.user, "equipment": doc.equipment,
        "asset": doc.asset, "work_order": job, "reset": int(reset), "note": note, "unusual": int(flagged),
        "confirmed": int(confirmed), "source": source or "", "plant_log": plant_log})
    reading.insert(ignore_permissions=True)
    if not doc.last_reading_on or get_datetime(reading.reading_on) >= get_datetime(doc.last_reading_on):
        doc.last_reading, doc.last_reading_on, doc.last_reading_by = value, reading.reading_on, frappe.session.user
    if reset:
        for row in doc.triggers:
            if row.trigger_type == "Every":
                row.next_due = value + flt(row.value)
    if source == "Customer":
        raised = []
        customer_alerts(doc, value, previous)
    else:
        raised = evaluate(doc, reading)
    doc.flags.ignore_permissions = True
    doc.save()
    if raised:
        reading.db_set("triggered_job", raised[0].name)
    if doc.equipment and check_ro:
        from projectit import ro
        ro.after_reading(doc.equipment)
    return reading, raised


def find_meter(meter_name, equipment=None, asset=None):
    """The active meter of that name on the machine (names compare without case), if any."""
    if not meter_name or not (equipment or asset):
        return None
    filters = {"equipment": equipment} if equipment else {"asset": asset}
    for row in frappe.get_all("Techy Meter", filters={**filters, "active": 1}, fields=["name", "meter_name"]):
        if row.meter_name.strip().lower() == str(meter_name).strip().lower():
            return row.name
    return None


def step_warning(task, meter_name, value):
    """The unusual-reading warning for a procedure Number step saved to a meter, or None."""
    name = find_meter(meter_name, task.get("custom_equipment"), None if task.get("custom_equipment") else task.get("custom_asset"))
    if not name or value in (None, ""):
        return None
    return unusual(frappe.get_doc("Techy Meter", name), _value(value))


def record_from_step(task, meter_name, value, label, previous=None, flagged=False, confirmed=False):
    """A procedure Number step saved to a meter: replace the step's earlier reading, record the new one.

    The caller has checked the technician may answer the job. Returns the reading name, or None when the
    job's machine has no such meter or the answer was cleared."""
    name = find_meter(meter_name, task.get("custom_equipment"), None if task.get("custom_equipment") else task.get("custom_asset"))
    if not name:
        return None
    doc = frappe.get_doc("Techy Meter", name, for_update=True)
    if previous and frappe.db.exists("Techy Meter Reading", {"name": previous, "meter": doc.name}):
        _remove(doc, previous)
        doc = frappe.get_doc("Techy Meter", name, for_update=True)
    if value in (None, ""):
        return None
    reading, _raised = _record(doc, value, task.name, _("Procedure step: {0}").format(label)[:280], flagged=flagged,
        confirmed=confirmed)
    return reading.name


# Standard meters from the item ---------------------------------------------------------------------------------

def _templates(item_code):
    if not item_code:
        return []
    return frappe.get_all("Techy Meter Template", filters={"parent": item_code, "parenttype": "Item",
        "parentfield": "custom_meter_templates"}, fields=["meter_name", "unit", "meter_type", "service_every",
        "service_procedure", "alert_above", "alert_below"], order_by="idx asc")


def _existing(equipment):
    return {n.strip().lower() for n in frappe.get_all("Techy Meter", filters={"equipment": equipment}, pluck="meter_name")}


def missing_templates(equipment, item_code):
    """Standard meters of the item that the machine does not have yet."""
    have = _existing(equipment) if equipment else set()
    return [t.meter_name for t in _templates(item_code) if t.meter_name.strip().lower() not in have]


def apply_templates(eq):
    """Create the item's standard meters on a machine (skipping names it already has)."""
    have, created = _existing(eq.name), []
    for t in _templates(eq.item_code):
        if t.meter_name.strip().lower() in have:
            continue
        triggers = []
        if t.meter_type == "Counter" and flt(t.service_every) > 0:
            procedure = t.service_procedure if t.service_procedure and not frappe.db.get_value("Techy Procedure",
                t.service_procedure, "disabled") else None
            triggers.append({"trigger_type": "Every", "value": flt(t.service_every), "next_due": flt(t.service_every),
                "priority": "Medium", "procedure": procedure})
        for kind, limit in (("Above", t.alert_above), ("Below", t.alert_below)):
            if flt(limit):
                triggers.append({"trigger_type": kind, "value": flt(limit), "priority": "High"})
        doc = frappe.get_doc({"doctype": "Techy Meter", "meter_name": t.meter_name, "unit": t.unit,
            "meter_type": t.meter_type if t.meter_type in TYPES else "Counter", "equipment": eq.name, "active": 1,
            "triggers": triggers})
        doc.insert(ignore_permissions=True)
        have.add(t.meter_name.strip().lower())
        created.append(doc.name)
    return created


@frappe.whitelist(methods=["POST"])
def add_standard_meters(equipment):
    """Managers: give an existing machine its item's standard meters."""
    ops.require_manager()
    _check_machine(equipment, None)
    eq = frappe.get_doc("Techy Equipment", equipment)
    if not apply_templates(eq):
        frappe.throw(_("This machine already has all the standard meters of {0}.").format(eq.item_code or _("its item")))
    return {"meters": for_machine(equipment=eq.name, include_inactive=True)}


def _machine_label(doc):
    if doc.equipment:
        row = frappe.db.get_value("Techy Equipment", doc.equipment, ["equipment_name", "customer_name", "site"],
            as_dict=True) or {}
        return " – ".join(x for x in (row.get("equipment_name"), row.get("site") or row.get("customer_name")) if x) \
            or doc.equipment
    return frappe.db.get_value("Asset", doc.asset, "asset_name") or doc.asset


def crossed(row, value):
    """Whether a reading sets off a trigger."""
    if row.trigger_type == "Every":
        return row.next_due is not None and value >= flt(row.next_due)
    if row.trigger_type == "Above":
        return value > flt(row.value)
    return value < flt(row.value)


def advance(next_due, every, value):
    """Next due reading after value, in steps of every."""
    next_due, every = flt(next_due), flt(every)
    if every <= 0:
        return next_due
    while next_due <= value:
        next_due += every
    return next_due


def evaluate(doc, reading):
    """Raise jobs for the triggers this reading sets off; returns the jobs created."""
    from projectit import work_orders
    value, raised = flt(reading.value), []
    for row in doc.triggers:
        if not crossed(row, value):
            continue
        current = _job(row.open_job)
        if row.trigger_type == "Every":
            row.next_due = advance(row.next_due, row.value, value)
        if is_open(current):
            frappe.get_doc("Task", current.name).add_comment("Info", escape(_("New {0} reading: {1} {2}.").format(
                doc.meter_name, fmt(value), doc.unit)))
            continue
        label, machine = trigger_label(doc, row), _machine_label(doc)
        if row.trigger_type == "Every":
            title = row.job_title or _("{0} service – {1}").format(doc.meter_name, machine)
            details = _("{0} reached {1} {2} (service every {3} {2}).").format(doc.meter_name, fmt(value), doc.unit, fmt(row.value))
        else:
            title = row.job_title or _("{0} {1} limit – {2}").format(doc.meter_name,
                _("over") if row.trigger_type == "Above" else _("under"), machine)
            limit = (_("over {0} {1}") if row.trigger_type == "Above" else _("under {0} {1}")).format(fmt(row.value), doc.unit)
            details = _("{0} read {1} {2}. It should not go {3}.").format(doc.meter_name, fmt(value), doc.unit, limit)
        frappe.db.savepoint("techy_meter")
        try:
            job = work_orders.create(title[:140], description=details, ignore_permissions=True,
                priority=row.priority if row.priority in PRIORITIES else ("Medium" if row.trigger_type == "Every" else "High"),
                category="Preventive" if row.trigger_type == "Every" else "Corrective",
                equipment=doc.equipment, asset=doc.asset, procedure=row.procedure or None)
        except Exception:
            frappe.db.rollback(save_point="techy_meter")
            frappe.log_error(title=f"Techy Ops: meter job for {doc.name} failed")
            continue
        row.open_job, row.last_triggered_on = job.name, now_datetime()
        raised.append(job)
        ops.notify(_managers(), _("Meter {0}: {1} – {2}").format(label.lower(), title, machine), "Task", job.name)
    return raised


def customer_alerts(doc, value, previous):
    """A customer's reading that sets off a trigger: tell the managers (the first time it does), raise nothing."""
    for row in doc.triggers:
        if not crossed(row, value) or (previous is not None and crossed(row, previous)):
            continue
        if is_open(_job(row.open_job)):
            continue  # a job for it is already open
        machine = _machine_label(doc)
        if row.trigger_type == "Every":
            what = _("{0} reached {1} {2}: service is due (every {3} {2})").format(doc.meter_name, fmt(value), doc.unit, fmt(row.value))
        else:
            limit = (_("over {0} {1}") if row.trigger_type == "Above" else _("under {0} {1}")).format(fmt(row.value), doc.unit)
            what = _("{0} read {1} {2}, {3}").format(doc.meter_name, fmt(value), doc.unit, limit)
        ops.notify(_managers(), _("Customer log – {0}: {1}. No job was raised; decide what to do.").format(machine, what),
            "Techy Equipment", doc.equipment)


@frappe.whitelist(methods=["POST"])
def delete_reading(name):
    """Managers remove a mistaken reading; the meter falls back to the latest remaining one."""
    ops.require_manager()
    reading = frappe.get_doc("Techy Meter Reading", name)
    doc = _meter(reading.meter, for_update=True)
    _remove(doc, reading.name)
    return get_meter(doc.name)


def _remove(doc, reading):
    # A procedure answer may point at the reading; unlink it so the delete is allowed.
    frappe.db.sql("UPDATE `tabTechy Procedure Response` SET meter_reading = NULL WHERE meter_reading = %s", (reading,))
    frappe.delete_doc("Techy Meter Reading", reading, ignore_permissions=True)
    latest = frappe.get_all("Techy Meter Reading", filters={"meter": doc.name}, fields=["value", "reading_on",
        "recorded_by"], order_by="reading_on desc, creation desc", limit_page_length=1)
    latest = latest[0] if latest else frappe._dict()
    doc.last_reading, doc.last_reading_on, doc.last_reading_by = latest.get("value"), latest.get("reading_on"), \
        latest.get("recorded_by")
    doc.flags.ignore_permissions = True
    doc.save()


# Set-up --------------------------------------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def save_meter(data, name=None):
    """Add or change a meter and its triggers (managers)."""
    ops.require_manager()
    data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
    if name:
        doc = _meter(name, for_update=True)
    else:
        _check_machine(data.get("equipment"), data.get("asset"))
        doc = frappe.new_doc("Techy Meter")
        doc.equipment, doc.asset = data.get("equipment") or None, data.get("asset") or None
    doc.meter_name = ops.text(data.get("meter_name"), "the meter name", 80)
    doc.unit = ops.text(data.get("unit"), "the unit", 20)
    meter_type = data.get("meter_type") or doc.meter_type or "Counter"
    if meter_type not in TYPES:
        frappe.throw(_("Choose counter or gauge."))
    if name and meter_type != doc.meter_type and doc.last_reading_on:
        frappe.throw(_("A meter with readings cannot change type. Add a new meter instead."))
    doc.meter_type = meter_type
    doc.active = 1 if data.get("active", 1) else 0
    doc.notes = ops.text(data.get("notes"), "notes", 1000, required=False)
    rows = data.get("triggers") or []
    if not isinstance(rows, list) or len(rows) > 10:
        frappe.throw(_("Add at most 10 triggers."))
    old = {row.name: row for row in doc.triggers}
    doc.set("triggers", [])
    for item in rows:
        kind = item.get("trigger_type")
        if kind not in TRIGGERS:
            frappe.throw(_("Choose when each trigger fires."))
        if kind == "Every" and meter_type != "Counter":
            frappe.throw(_("Only counters can trigger a service every so many units."))
        value = _value(item.get("value"))
        if kind == "Every" and value <= 0:
            frappe.throw(_("Enter how often the service is due, above zero."))
        procedure = item.get("procedure") or None
        if procedure and frappe.db.get_value("Techy Procedure", procedure, "disabled") in (None, 1):
            frappe.throw(_("Choose an active procedure."))
        priority = item.get("priority") or ("Medium" if kind == "Every" else "High")
        if priority not in PRIORITIES:
            frappe.throw(_("Invalid priority."))
        previous = old.get(item.get("name"))
        next_due = None
        if kind == "Every":
            if item.get("next_due") not in (None, ""):
                next_due = _value(item["next_due"])
            elif previous and previous.trigger_type == "Every" and flt(previous.value) == value and previous.next_due:
                next_due = previous.next_due
            else:
                next_due = advance(flt(doc.last_reading), value, flt(doc.last_reading)) if doc.last_reading_on else value
        doc.append("triggers", {"trigger_type": kind, "value": value, "priority": priority, "procedure": procedure,
            "job_title": ops.text(item.get("job_title"), "the job title", 140, required=False) or None,
            "next_due": next_due, "open_job": previous.open_job if previous and previous.trigger_type == kind else None,
            "last_triggered_on": previous.last_triggered_on if previous else None})
    doc.flags.ignore_permissions = True
    doc.save()
    return summary(doc)
