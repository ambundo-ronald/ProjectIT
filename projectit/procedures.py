"""MaintainX-style procedures: reusable checklists with typed steps, run on work orders.

A Techy Procedure is a template. Attaching it to a work order copies its steps into a Techy Procedure Run
(one per work order), so later template edits never rewrite completed work. Answers are saved one at a time;
a failed Pass/Fail or out-of-range Number can raise a follow-up work order, and a work order cannot be
completed while required steps are unanswered (enforced in work_orders.validate_task, so Desk too).
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from projectit import ops

TYPES = ("Heading", "Checkbox", "Pass/Fail", "Yes/No/N/A", "Number", "Text", "Multiple Choice", "Photo", "Signature")
CATEGORIES = ("Corrective", "Preventive", "Inspection", "Safety", "Other")
STEP_FIELDS = ("field_type", "label", "help", "required", "options", "min_value", "max_value", "unit",
    "create_follow_up")
CHOICES = {"Pass/Fail": ("Pass", "Fail"), "Yes/No/N/A": ("Yes", "No", "N/A")}
FAILABLE = ("Pass/Fail", "Number")
MAX_STEPS = 100


# Templates ---------------------------------------------------------------------------------------------------

def _number(value, label):
    value = str(value if value is not None else "").strip()
    if not value:
        return ""
    try:
        float(value)
    except ValueError:
        frappe.throw(_("{0} must be a number.").format(label))
    return value


def _clean_steps(steps):
    steps = frappe.parse_json(steps) if isinstance(steps, str) else (steps or [])
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        frappe.throw(_("A procedure can have at most {0} steps.").format(MAX_STEPS))
    clean = []
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict) or step.get("field_type") not in TYPES:
            frappe.throw(_("Step {0} needs a valid type.").format(i))
        kind = step["field_type"]
        row = {"field_type": kind, "label": ops.text(step.get("label"), f"step {i}", 140),
            "help": ops.text(step.get("help"), f"instructions for step {i}", 500, required=False),
            "required": int(bool(cint(step.get("required"))) and kind != "Heading"),
            "options": "", "min_value": "", "max_value": "", "unit": "",
            "create_follow_up": int(bool(cint(step.get("create_follow_up"))) and kind in FAILABLE)}
        if kind == "Multiple Choice":
            options = step.get("options") or []
            options = options.splitlines() if isinstance(options, str) else options
            options = list(dict.fromkeys(str(o).strip()[:80] for o in options if str(o).strip()))
            if not 2 <= len(options) <= 20:
                frappe.throw(_("Step {0}: give between 2 and 20 choices.").format(i))
            row["options"] = "\n".join(options)
        if kind == "Number":
            row["min_value"] = _number(step.get("min_value"), _("Step {0} minimum").format(i))
            row["max_value"] = _number(step.get("max_value"), _("Step {0} maximum").format(i))
            if row["min_value"] and row["max_value"] and flt(row["min_value"]) > flt(row["max_value"]):
                frappe.throw(_("Step {0}: the minimum is above the maximum.").format(i))
            row["unit"] = ops.text(step.get("unit"), f"the unit for step {i}", 20, required=False)
            if row["create_follow_up"] and not (row["min_value"] or row["max_value"]):
                frappe.throw(_("Step {0}: set a minimum or maximum so a reading can fail.").format(i))
        clean.append(row)
    if not any(s["field_type"] != "Heading" for s in clean):
        frappe.throw(_("Add at least one step to answer."))
    return clean


def _step(row):
    return {field: row.get(field) or ("" if field not in ("required", "create_follow_up") else 0)
        for field in STEP_FIELDS}


@frappe.whitelist()
def list_procedures(search=None, archived=0):
    ops.system_user()
    filters = {"disabled": 1 if cint(archived) and ops.manager() else 0}
    or_filters = None
    if search:
        like = f"%{str(search).strip()[:80]}%"
        or_filters = {"title": ["like", like], "name": ["like", like], "category": ["like", like]}
    rows = frappe.get_all("Techy Procedure", filters=filters, or_filters=or_filters,
        fields=["name", "title", "category", "description", "disabled", "modified"], order_by="title asc",
        limit_page_length=200)
    counts, used = {}, {}
    if rows:
        counts = dict(frappe.db.sql("""SELECT parent, COUNT(*) FROM `tabTechy Procedure Step`
            WHERE parenttype = 'Techy Procedure' AND field_type != 'Heading' AND parent IN %(names)s
            GROUP BY parent""", {"names": tuple(r.name for r in rows)}))
        used = dict(frappe.db.sql("""SELECT `procedure`, COUNT(*) FROM `tabTechy Procedure Run`
            WHERE `procedure` IN %(names)s GROUP BY `procedure`""", {"names": tuple(r.name for r in rows)}))
    for row in rows:
        row.steps = counts.get(row.name, 0)
        row.used = used.get(row.name, 0)
    return {"procedures": rows, "manager": ops.manager()}


@frappe.whitelist()
def get_procedure(name):
    ops.system_user()
    doc = frappe.get_doc("Techy Procedure", name)
    if doc.disabled and not ops.manager():
        frappe.throw(_("This procedure is archived."))
    return {"name": doc.name, "title": doc.title, "category": doc.category or "", "description": doc.description or "",
        "disabled": doc.disabled, "modified": doc.modified, "steps": [_step(s) for s in doc.steps],
        "manager": ops.manager()}


@frappe.whitelist(methods=["POST"])
def save_procedure(title, steps, name=None, category=None, description=None, modified=None):
    ops.system_user()
    ops.require_manager()
    if category and category not in CATEGORIES:
        frappe.throw(_("Invalid category."))
    if name:
        doc = frappe.get_doc("Techy Procedure", name, for_update=True)
        if modified and str(doc.modified) != str(modified):
            frappe.throw(_("Someone else changed this procedure. Reload it before saving."))
    else:
        doc = frappe.new_doc("Techy Procedure")
    doc.title = ops.text(title, "a title", 140)
    doc.category = category or ""
    doc.description = ops.text(description, "a description", 1000, required=False)
    doc.set("steps", _clean_steps(steps))
    # Managers are authorised above; the Desk role grid stays the source of truth for Desk editing.
    doc.save(ignore_permissions=True)
    return get_procedure(doc.name)


@frappe.whitelist(methods=["POST"])
def archive_procedure(name, archived=1):
    ops.system_user()
    ops.require_manager()
    frappe.db.set_value("Techy Procedure", frappe.get_doc("Techy Procedure", name).name, "disabled",
        int(bool(cint(archived))))
    return get_procedure(name)


# Runs on work orders -----------------------------------------------------------------------------------------

def _run_name(work_order):
    return frappe.db.get_value("Techy Procedure Run", {"work_order": work_order}, "name")


def start(work_order, procedure):
    """Copy a procedure onto a work order (callers have authorised the work order write)."""
    template = frappe.get_doc("Techy Procedure", procedure)
    if template.disabled:
        frappe.throw(_("Procedure {0} is archived.").format(template.title))
    existing = _run_name(work_order.name)
    if existing:
        frappe.delete_doc("Techy Procedure Run", existing, ignore_permissions=True)
    frappe.get_doc({"doctype": "Techy Procedure Run", "work_order": work_order.name, "procedure": template.name,
        "title": template.title, "responses": [_step(s) for s in template.steps]}).insert(ignore_permissions=True)


def run_data(work_order):
    """The work order's procedure with answers, for get_work_order (access already checked)."""
    name = _run_name(work_order)
    if not name:
        return None
    run = frappe.get_doc("Techy Procedure Run", name)
    steps = []
    for row in run.responses:
        step = _step(row)
        step.update(name=row.name, value=row.value or "", failed=row.failed, answered_on=row.answered_on,
            answered_by=frappe.utils.get_fullname(row.answered_by) if row.answered_by else "",
            follow_up_work_order=row.follow_up_work_order)
        steps.append(step)
    answerable = [s for s in steps if s["field_type"] != "Heading"]
    return {"name": run.name, "procedure": run.procedure, "title": run.title, "steps": steps,
        "answered": sum(1 for s in answerable if s["value"]), "total": len(answerable),
        "missing": sum(1 for s in answerable if s["required"] and not s["value"]),
        "failed": sum(1 for s in answerable if s["failed"])}


def missing_required(work_order):
    name = _run_name(work_order)
    if not name:
        return 0
    return frappe.db.sql("""SELECT COUNT(*) FROM `tabTechy Procedure Response` WHERE parent = %s
        AND parenttype = 'Techy Procedure Run' AND required = 1 AND field_type != 'Heading'
        AND IFNULL(value, '') = ''""", (name,))[0][0]


def _has_answers(run):
    return bool(frappe.db.sql("""SELECT 1 FROM `tabTechy Procedure Response` WHERE parent = %s
        AND parenttype = 'Techy Procedure Run' AND IFNULL(value, '') != '' LIMIT 1""", (run,)))


def _work_order(name, write=True):
    from projectit import work_orders
    doc = work_orders._work_order(name, write=write)
    if write and doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("Reopen the work order to change its procedure."))
    return doc


def _result(doc):
    from projectit import work_orders
    people = set(work_orders._assignees([doc.name])[doc.name]) | {doc.owner}
    ops.push(people, "techy_work_order", {"name": doc.name})
    return work_orders.get_work_order(doc.name)


@frappe.whitelist(methods=["POST"])
def attach(work_order, procedure):
    doc = _work_order(work_order)
    name = _run_name(doc.name)
    if name and _has_answers(name) and not ops.manager():
        frappe.throw(_("This procedure has answers. Ask a manager to replace it."), frappe.PermissionError)
    start(doc, procedure)
    doc.add_comment("Info", escape(_("{0} attached the procedure {1}.").format(frappe.utils.get_fullname(),
        frappe.db.get_value("Techy Procedure", procedure, "title"))))
    return _result(doc)


@frappe.whitelist(methods=["POST"])
def detach(work_order):
    doc = _work_order(work_order)
    name = _run_name(doc.name)
    if not name:
        return _result(doc)
    if _has_answers(name) and not ops.manager():
        frappe.throw(_("This procedure has answers. Ask a manager to remove it."), frappe.PermissionError)
    frappe.delete_doc("Techy Procedure Run", name, ignore_permissions=True)
    doc.add_comment("Info", escape(_("{0} removed the procedure.").format(frappe.utils.get_fullname())))
    return _result(doc)


def _value(row, value, photo):
    """Validate and normalise an answer; returns (stored value, failed)."""
    kind = row.field_type
    value = "" if value is None else str(value).strip()
    if kind == "Heading":
        frappe.throw(_("Headings don't take answers."))
    if kind == "Checkbox":
        return ("1" if value in ("1", "true", "True") else ""), 0
    if kind in CHOICES:
        if value and value not in CHOICES[kind]:
            frappe.throw(_("Choose one of: {0}.").format(", ".join(CHOICES[kind])))
        return value, int(value == "Fail")
    if kind == "Multiple Choice":
        if value and value not in (row.options or "").split("\n"):
            frappe.throw(_("Choose one of the listed options."))
        return value, 0
    if kind == "Number":
        if not value:
            return "", 0
        try:
            number = float(value)
        except ValueError:
            frappe.throw(_("Enter a number."))
        low, high = row.min_value, row.max_value
        failed = (low not in (None, "") and number < flt(low)) or (high not in (None, "") and number > flt(high))
        return ("%g" % number), int(bool(failed))
    if kind == "Text":
        return ops.text(value, "an answer", 2000, required=False), 0
    return value, 0  # Photo / Signature: set from the uploaded file below


def _follow_up(doc, row):
    """Raise a High-priority corrective work order for a failed step (once per step)."""
    from projectit import work_orders
    reading = f"{row.value} {row.unit or ''}".strip()
    subject = _("Follow-up: {0}").format(row.label)[:140]
    description = _("Raised automatically from work order {0} ({1}). Step \"{2}\" failed with: {3}.").format(
        doc.name, doc.subject, row.label, reading)
    # The procedure (written by a manager) asks for this work order; technicians may lack Task create.
    follow = work_orders.create(subject, description, "High", "Corrective", doc.custom_asset, doc.custom_location,
        project=doc.project, ignore_permissions=True)
    managers = frappe.get_all("Has Role", filters={"role": ["in", list(ops.MANAGER_ROLES - {"System Manager"})],
        "parenttype": "User"}, pluck="parent")
    ops.notify(managers, _("Failed check on {0}: {1}").format(doc.subject, row.label), "Task", follow.name)
    doc.add_comment("Info", escape(_("Step \"{0}\" failed ({1}). Follow-up work order #{2} was created.").format(
        row.label, reading, follow.name)))
    return follow.name


@frappe.whitelist(methods=["POST"])
def answer(work_order, step, value=None, photo=None):
    doc = _work_order(work_order)
    name = _run_name(doc.name)
    if not name:
        frappe.throw(_("This work order has no procedure."))
    run = frappe.get_doc("Techy Procedure Run", name, for_update=True)
    row = next((r for r in run.responses if r.name == step), None)
    if not row:
        frappe.throw(_("This step is not part of the procedure."))
    stored, failed = _value(row, value, photo)
    if row.field_type in ("Photo", "Signature"):
        if photo:
            prefix = "signature" if row.field_type == "Signature" else "procedure"
            stored = ops.save_photo("Task", doc.name, photo, prefix).file_url
        elif value:
            frappe.throw(_("Take a photo or sign first."))
    row.value = stored
    row.failed = failed
    row.answered_by = frappe.session.user if stored else None
    row.answered_on = now_datetime() if stored else None
    if failed and row.create_follow_up and not row.follow_up_work_order:
        row.follow_up_work_order = _follow_up(doc, row)
    run.save(ignore_permissions=True)
    if stored and doc.status in ("Open", "Overdue"):
        doc.reload()
        doc.status = "Working"
        doc.save()
    return _result(doc)
