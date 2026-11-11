"""Failure codes and downtime on jobs, MaintainX style.

A job can record what was wrong (problem), why (cause) and what fixed it (remedy), from Techy Failure Code lists
managers keep. It can also record that the machine was down, from when until it was back in service. Completing the
job closes an open downtime. Techy Ops Settings can require problem and cause codes before a repair is completed.
The reports count the failures and work out each machine's downtime, time to repair and availability.
"""
import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from projectit import ops

DOCTYPE = "Techy Failure Code"
KINDS = ("Problem", "Cause", "Remedy")
FIELDS = {"Problem": "custom_problem_code", "Cause": "custom_cause_code", "Remedy": "custom_remedy_code"}
# Common water-treatment codes for a new site; managers edit or add their own.
DEFAULTS = [
    ("LEAK", "Leak", "Problem"), ("LOW-FLOW", "Low product flow", "Problem"),
    ("HIGH-TDS", "Product water quality out of range", "Problem"), ("NO-START", "Will not start", "Problem"),
    ("PRESSURE", "Pressure out of range", "Problem"), ("NOISE", "Noise or vibration", "Problem"),
    ("ALARM", "Alarm or controller fault", "Problem"),
    ("FOULING", "Membrane fouling or scaling", "Cause"), ("FILTER-BLOCKED", "Pre-filters blocked", "Cause"),
    ("WEAR", "Normal wear", "Cause"), ("POWER", "Power supply problem", "Cause"),
    ("FEED-WATER", "Feed water quality changed", "Cause"), ("MISUSE", "Operated incorrectly", "Cause"),
    ("SEAL", "Seal or fitting failed", "Cause"), ("ELECTRICAL", "Electrical fault", "Cause"),
    ("REPLACED", "Replaced part", "Remedy"), ("CLEANED", "Cleaned or flushed (CIP)", "Remedy"),
    ("ADJUSTED", "Adjusted or recalibrated", "Remedy"), ("REPAIRED", "Repaired", "Remedy"),
    ("TRAINED", "Trained the operator", "Remedy"), ("RESET", "Reset", "Remedy"),
]


def setting():
    return cint(frappe.db.get_single_value("Techy Ops Settings", "require_failure_codes"))


def needs_codes(doc):
    """Repairs on a machine must carry problem and cause codes when the setting is on."""
    return bool(setting() and doc.get("custom_work_category") == "Corrective"
        and (doc.get("custom_equipment") or doc.get("custom_asset")))


def missing(doc):
    return [kind for kind in ("Problem", "Cause") if not doc.get(FIELDS[kind])] if needs_codes(doc) else []


def downtime_missing(doc):
    """With the setting on, a repair on a machine must say whether the machine was down."""
    return needs_codes(doc) and not cint(doc.get("custom_machine_down")) and not cint(doc.get("custom_down_answered"))


def check_complete(doc, action):
    """The failure details a repair needs before it is completed or sent for review."""
    gaps = missing(doc)
    if gaps:
        frappe.throw(_("Choose the {0} code before {1} this repair.").format(" and ".join(_(k).lower() for k in gaps), action))
    if downtime_missing(doc):
        frappe.throw(_("Say whether the machine was down (Failure & downtime) before {0} this repair.").format(action))


@frappe.whitelist()
def options(include_disabled=0):
    """{Problem: [{code, title}], Cause: [...], Remedy: [...]} for the job form (managers can see disabled ones)."""
    ops.system_user()
    filters = {} if cint(include_disabled) and ops.manager() else {"disabled": 0}
    rows = frappe.get_all(DOCTYPE, filters=filters, fields=["code", "title", "kind", "disabled", "description"],
        order_by="title asc", limit_page_length=0)
    return {kind: [r for r in rows if r.kind == kind] for kind in KINDS}


def hours(down_from, down_to=None):
    if not down_from:
        return None
    end = get_datetime(down_to) if down_to else now_datetime()
    return round(max(0.0, (end - get_datetime(down_from)).total_seconds() / 3600), 2)


def summary(doc, can_write):
    """The failure and downtime card on the job page."""
    codes = [doc.get(f) for f in FIELDS.values() if doc.get(f)]
    titles = dict(frappe.get_all(DOCTYPE, filters={"name": ["in", codes]}, fields=["name", "title"], as_list=True)) if codes else {}
    return {kind.lower(): {"code": doc.get(field), "title": titles.get(doc.get(field))} if doc.get(field) else None
        for kind, field in FIELDS.items()} | {
        "machine_down": bool(doc.get("custom_machine_down")), "down_answered": bool(cint(doc.get("custom_down_answered"))),
        "downtime_missing": downtime_missing(doc), "down_from": doc.get("custom_down_from"),
        "down_to": doc.get("custom_down_to"),
        "down_hours": hours(doc.get("custom_down_from"), doc.get("custom_down_to")) if doc.get("custom_machine_down") else None,
        "required": needs_codes(doc), "missing": missing(doc), "can_edit": bool(can_write),
        "has_machine": bool(doc.get("custom_equipment") or doc.get("custom_asset"))}


def _code(value, kind):
    if not value:
        return None
    row = frappe.db.get_value(DOCTYPE, value, ["kind", "disabled"], as_dict=True)
    if not row or row.kind != kind:
        frappe.throw(_("Choose a {0} code from the list.").format(_(kind).lower()))
    return value


def _when(value, label):
    if not value:
        return None
    when = get_datetime(str(value).replace("T", " "))
    if when > now_datetime():
        frappe.throw(_("{0} cannot be in the future.").format(label))
    return when


@frappe.whitelist(methods=["POST"])
def set_failure(work_order, problem=None, cause=None, remedy=None, machine_down=None, down_from=None, down_to=None):
    """Record the failure codes and downtime of a job. Values not sent are left as they are; '' clears one."""
    from projectit import work_orders
    doc = work_orders._work_order(work_order)
    if not frappe.has_permission("Task", "write", doc=doc):
        frappe.throw(_("You cannot change this job."), frappe.PermissionError)
    values = {}
    for kind, value in (("Problem", problem), ("Cause", cause), ("Remedy", remedy)):
        if value is not None:
            values[FIELDS[kind]] = _code(value, kind)
    if machine_down is not None:
        values["custom_machine_down"] = cint(machine_down)
        values["custom_down_answered"] = 1
        if cint(machine_down) and not doc.get("custom_down_from") and down_from is None:
            values["custom_down_from"] = now_datetime()
        if not cint(machine_down):
            values.update(custom_down_from=None, custom_down_to=None)
    if down_from is not None:
        values["custom_down_from"] = _when(down_from, _("Down from"))
    if down_to is not None:
        values["custom_down_to"] = _when(down_to, _("Back in service"))
    start = values.get("custom_down_from", doc.get("custom_down_from"))
    end = values.get("custom_down_to", doc.get("custom_down_to"))
    if start and end and get_datetime(end) < get_datetime(start):
        frappe.throw(_("Back in service must be after the machine went down."))
    if values:
        # Job fields only; a full save would re-run status and dependency validation.
        frappe.db.set_value("Task", doc.name, values)
    return work_orders.get_work_order(doc.name)


def on_complete(doc):
    """Task validate, when a job is completed: require codes if the site asks, close an open downtime."""
    check_complete(doc, _("completing"))
    if doc.get("custom_machine_down") and doc.get("custom_down_from") and not doc.get("custom_down_to"):
        doc.custom_down_to = now_datetime()


@frappe.whitelist(methods=["POST"])
def save_code(code, title, kind, description=None, disabled=0):
    """Add or change a failure code (managers)."""
    ops.require_manager()
    code = ops.text(code, "a code", 40).upper().replace(" ", "-")
    title = ops.text(title, "a title", 140)
    if kind not in KINDS:
        frappe.throw(_("Choose problem, cause or remedy."))
    values = {"title": title, "kind": kind, "disabled": cint(disabled),
        "description": ops.text(description, "a description", 500, required=False) or None}
    if frappe.db.exists(DOCTYPE, code):
        existing = frappe.get_doc(DOCTYPE, code)
        if existing.kind != kind and _used(code):
            frappe.throw(_("{0} is already used on jobs as a {1}. Add a new code instead.").format(code, existing.kind.lower()))
        existing.update(values)
        existing.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": DOCTYPE, "code": code, **values}).insert(ignore_permissions=True)
    return options(include_disabled=1)


def _used(code):
    return any(frappe.db.exists("Task", {field: code}) for field in FIELDS.values())


@frappe.whitelist(methods=["POST"])
def add_defaults():
    """Start a new site with common water-treatment failure codes (existing codes are kept)."""
    ops.require_manager()
    for code, title, kind in DEFAULTS:
        if not frappe.db.exists(DOCTYPE, code):
            frappe.get_doc({"doctype": DOCTYPE, "code": code, "title": title, "kind": kind}).insert(ignore_permissions=True)
    return options(include_disabled=1)
