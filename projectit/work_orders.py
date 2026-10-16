"""MaintainX-style work orders on native ERPNext Tasks (custom_work_order = 1).

Assignments are ToDos, checklist steps are child Tasks, activity is Task Comments
and photos are private Files, so everything stays visible in ERPNext Desk.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, nowdate

from projectit import billing, equipment as installed, failures, meters, ops, parts, procedures, ratings, service_report, timer

FIELDS = ["name", "subject", "status", "priority", "exp_end_date", "custom_work_category", "custom_asset",
    "custom_location", "custom_equipment", "custom_customer", "project", "is_group", "progress", "owner", "creation",
    "modified"]
STATUSES = ("Open", "Working", "Pending Review", "Completed", "Cancelled")
PRIORITIES = ("Low", "Medium", "High", "Urgent")
CATEGORIES = ("Corrective", "Preventive", "Inspection", "Installation", "Safety", "Other")


def _assignees(names):
    """Open and completed (not cancelled) assignees for each Task name."""
    result = {name: [] for name in names}
    if names:
        for row in frappe.get_all("ToDo", filters={"reference_type": "Task", "reference_name": ["in", names],
                "status": ["!=", "Cancelled"]}, fields=["reference_name", "allocated_to"], order_by="creation asc"):
            if row.allocated_to not in result[row.reference_name]:
                result[row.reference_name].append(row.allocated_to)
    return result


def _mine():
    return frappe.get_all("ToDo", filters={"reference_type": "Task", "allocated_to": frappe.session.user,
        "status": ["!=", "Cancelled"]}, pluck="reference_name")


def _work_order(name, write=False):
    ops.system_user()
    doc = frappe.get_doc("Task", name, for_update=write)
    doc.check_permission("write" if write else "read")
    if not doc.custom_work_order:
        frappe.throw(_("{0} is not a work order.").format(name))
    if not ops.manager() and doc.owner != frappe.session.user and frappe.session.user not in _assignees([name])[name]:
        frappe.throw(_("This work order is not assigned to you."), frappe.PermissionError)
    return doc


def _workflow():
    return frappe.db.get_value("Workflow", {"document_type": "Task", "is_active": 1}, "name")


@frappe.whitelist()
def list_work_orders(scope="mine", status=None, asset=None, location=None, search=None, start=0, page_length=None):
    ops.system_user()
    filters = {"custom_work_order": 1, "is_template": 0, "parent_task": ["is", "not set"]}
    if status == "Open":
        filters["status"] = ["in", ["Open", "Overdue"]]
    elif status == "Active":
        filters["status"] = ["not in", ["Completed", "Cancelled"]]
    elif status in STATUSES:
        filters["status"] = status
    for field, value in (("custom_asset", asset), ("custom_location", location)):
        if value:
            filters[field] = value
    or_filters = None
    if scope != "all" or not ops.manager():
        or_filters = {"name": ["in", _mine() or [""]], "owner": frappe.session.user}
    if search:
        filters["subject"] = ["like", f"%{str(search).strip()[:80]}%"]
    start = max(0, cint(start))
    # The screen filters and counts what it loads, so it may ask for a large batch (at most 500).
    size = min(max(cint(page_length) or 100, 1), 500)
    rows = frappe.get_list("Task", filters=filters, or_filters=or_filters, fields=FIELDS,
        order_by="modified desc", limit_start=start, limit_page_length=size + 1)
    assigned = _assignees([row.name for row in rows])
    labels = ops.asset_names(row.custom_asset for row in rows)
    machines = installed.labels(row.custom_equipment for row in rows)
    for row in rows:
        row.assignees = ops.people(assigned[row.name])
        row.asset_name = labels.get(row.custom_asset)
        row.equipment = machines.get(row.custom_equipment)
    return {"work_orders": rows[:size], "has_more": len(rows) > size, "manager": ops.manager()}


@frappe.whitelist()
def get_work_order(name):
    return detail(_work_order(name))


def detail(doc):
    """A work order's page data; callers have checked access (get_work_order, or an authorised report)."""
    steps = frappe.get_all("Task", filters={"parent_task": doc.name, "is_template": 0},
        fields=["name", "subject", "status", "modified"], order_by="creation asc", limit_page_length=0)
    # Comments and files are read only after the Task permission check above.
    comments = frappe.get_all("Comment", filters={"reference_doctype": "Task", "reference_name": doc.name,
        "comment_type": ["in", ["Comment", "Info"]]}, fields=["name", "content", "comment_type", "comment_by",
        "comment_email", "creation"], order_by="creation asc", limit_page_length=200)
    for comment in comments:
        comment.content = ops.plain(comment.content)
    asset = None
    if doc.custom_asset:
        asset = frappe.db.get_value("Asset", doc.custom_asset, ["name", "asset_name", "location"], as_dict=True)
    request = None
    if doc.custom_work_request:
        request = frappe.db.get_value("Issue", doc.custom_work_request, ["name", "subject", "raised_by"], as_dict=True)
    can_write = bool(frappe.has_permission("Task", "write", doc=doc))
    return {"work_order": {field: doc.get(field) for field in FIELDS}, "description": ops.plain(doc.description),
        "assignees": ops.people(_assignees([doc.name])[doc.name]), "steps": steps, "comments": comments,
        "files": [f for f in ops.files("Task", doc.name) if not f.file_name.startswith("signature-")],
        "asset": asset, "request": request, "procedure": procedures.run_data(doc.name),
        "equipment": installed.summary(doc.custom_equipment),
        "parts": parts.summary(doc.name, can_write and doc.status not in ("Completed", "Cancelled")),
        "billing": billing.summary(doc, can_write),
        "meters": meters.for_machine(doc.custom_equipment, None if doc.custom_equipment else doc.custom_asset),
        "report": service_report.summary(doc, can_write), "timer": timer.summary(doc, can_write),
        "failure": failures.summary(doc, can_write), "rating": ratings.summary(doc),
        "pm_log": doc.custom_asset_maintenance_log, "workflow": _workflow(), "can_write": can_write,
        "manager": ops.manager()}


def _steps(value):
    values = frappe.parse_json(value) if isinstance(value, str) else (value or [])
    if not isinstance(values, list) or len(values) > 50:
        frappe.throw(_("Provide at most 50 checklist steps."))
    return [ops.text(v, "each checklist step", 140) for v in values]


def create(subject, description=None, priority="Medium", category="Corrective", asset=None, location=None,
        assignees=None, due_date=None, steps=None, project=None, request=None, pm_log=None, procedure=None,
        ignore_permissions=False, equipment=None, service_contract=None, machine_down=False):
    """Create a work order; callers have already authorised the action. `machine_down` starts its downtime now."""
    from frappe.desk.form.assign_to import add
    subject = ops.text(subject, "a title", 140)
    description = ops.text(description, "a description", 4000, required=False)
    if priority not in PRIORITIES or category not in CATEGORIES:
        frappe.throw(_("Invalid priority or category."))
    assignees = ops.active_users(assignees)
    steps = _steps(steps)
    if asset:
        asset_location = frappe.db.get_value("Asset", asset, "location")
        if asset_location is None and not frappe.db.exists("Asset", asset):
            frappe.throw(_("Asset {0} was not found.").format(asset))
        location = location or asset_location
    customer = None
    if equipment:
        machine = frappe.db.get_value("Techy Equipment", equipment, ["customer", "status"], as_dict=True)
        if not machine or machine.status in installed.RETIRED:
            frappe.throw(_("Choose customer equipment that is in service."))
        customer = machine.customer
    if location and not frappe.db.exists("Location", location):
        frappe.throw(_("Location {0} was not found.").format(location))
    if project and frappe.db.get_value("Project", project, "status") != "Open":
        frappe.throw(_("Choose an open project."))

    def insert(title, parent=None, group=False, details=None):
        doc = frappe.get_doc({"doctype": "Task", "subject": title, "description": escape(details or ""),
            "parent_task": parent, "is_group": int(group), "priority": priority, "status": "Open",
            "exp_end_date": due_date or None, "project": project or None, "custom_work_order": int(not parent),
            "custom_work_category": category, "custom_asset": asset or None, "custom_location": location or None,
            "custom_equipment": equipment or None, "custom_customer": customer,
            "custom_service_contract": service_contract if not parent else None,
            "custom_work_request": request if not parent else None,
            "custom_asset_maintenance_log": pm_log if not parent else None,
            "custom_machine_down": int(bool(machine_down) and not parent),
            "custom_down_from": now_datetime() if machine_down and not parent else None})
        doc.insert(ignore_permissions=ignore_permissions)
        if assignees:
            add({"doctype": "Task", "name": doc.name, "assign_to": assignees, "description": title})
        return doc

    root = insert(subject, group=bool(steps), details=description)
    for step in steps:
        insert(step, root.name)
    if procedure:
        procedures.start(root, procedure)
    ops.notify(assignees, _("Work order assigned: {0}").format(subject), "Task", root.name, "Assignment")
    _announce(root, _("created"))
    return root


@frappe.whitelist(methods=["POST"])
def create_work_order(subject, description=None, priority="Medium", category="Corrective", asset=None,
        location=None, assignees=None, due_date=None, steps=None, project=None, procedure=None, equipment=None,
        chat_message=None, machine_down=0):
    """chat_message: the chat message this job comes from; its photos are copied and its thread gets a link."""
    ops.system_user()
    if not frappe.has_permission("Task", "create"):
        frappe.throw(_("You are not permitted to create work orders."), frappe.PermissionError)
    people = ops.active_users(assignees)
    if not ops.manager() and set(people) - {frappe.session.user}:
        frappe.throw(_("Only managers can assign work orders to other people."), frappe.PermissionError)
    if project:
        frappe.get_doc("Project", project).check_permission("read")
    from projectit import chat
    message = chat.message_source(chat_message) if chat_message else None
    doc = create(subject, description, priority, category, asset, location, people, due_date, steps, project,
        procedure=procedure, equipment=equipment, machine_down=cint(machine_down) and bool(asset or equipment))
    if message:
        chat.link_work_order(message, doc)
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_work_order(name, modified, status=None, priority=None, due_date=None, assignees=None):
    from frappe.desk.form.assign_to import add, remove
    doc = _work_order(name, write=True)
    if str(doc.modified) != str(modified):
        frappe.throw(_("This work order changed. Refresh it before saving."))
    if status and status != doc.status:
        if _workflow():
            frappe.throw(_("Tasks use an ERPNext Workflow. Use its workflow actions in Desk."))
        if status not in STATUSES or (status == "Cancelled" and not ops.manager()):
            frappe.throw(_("This status change is not allowed."), frappe.PermissionError)
        doc.status = status
    if (priority or due_date or assignees is not None) and not ops.manager():
        frappe.throw(_("Only managers can change priority, due date or assignees."), frappe.PermissionError)
    if priority:
        if priority not in PRIORITIES:
            frappe.throw(_("Invalid priority."))
        doc.priority = priority
    if due_date:
        doc.exp_end_date = getdate(due_date)
    doc.save()  # Native dependency/group validation, progress, audit and ToDo closure.
    if assignees is not None:
        wanted = set(ops.active_users(assignees))
        current = set(_assignees([doc.name])[doc.name])
        if wanted - current:
            add({"doctype": "Task", "name": doc.name, "assign_to": sorted(wanted - current), "description": doc.subject})
            ops.notify(wanted - current, _("Work order assigned: {0}").format(doc.subject), "Task", doc.name,
                "Assignment")
        for user in current - wanted:
            remove("Task", doc.name, user)
    return get_work_order(doc.name)


@frappe.whitelist(methods=["POST"])
def toggle_step(name, step, done):
    parent = _work_order(name, write=True)
    child = frappe.get_doc("Task", step, for_update=True)
    if child.parent_task != parent.name:
        frappe.throw(_("This step does not belong to the work order."))
    child.check_permission("write")
    child.status = "Completed" if cint(done) else "Open"
    child.save()
    if parent.status == "Open" and cint(done):
        parent.reload()
        parent.status = "Working"
        parent.save()
    return get_work_order(parent.name)


@frappe.whitelist(methods=["POST"])
def add_comment(name, content):
    doc = _work_order(name, write=True)
    content = ops.text(content, "a comment", 4000)
    doc.add_comment("Comment", escape(content))
    people = set(_assignees([doc.name])[doc.name]) | {doc.owner}
    mentioned = ops.mentions(content)
    ops.notify(mentioned, _("{0} mentioned you on {1}").format(frappe.utils.get_fullname(), doc.subject),
        "Task", doc.name, "Mention")
    ops.push(people | set(mentioned), "techy_work_order", {"name": doc.name})
    return get_work_order(doc.name)


@frappe.whitelist(methods=["POST"])
def attach_photo(name, content):
    doc = _work_order(name, write=True)
    ops.save_photo("Task", doc.name, content, "work-order")
    return get_work_order(doc.name)


@frappe.whitelist()
def options():
    ops.system_user()
    projects = frappe.get_list("Project", filters={"status": "Open"}, fields=["name", "project_name"],
        order_by="project_name asc", limit_page_length=200)
    locations = frappe.get_all("Location", fields=["name", "location_name", "parent_location"],
        order_by="name asc", limit_page_length=500)
    return {"projects": projects, "locations": locations, "priorities": PRIORITIES, "categories": CATEGORIES,
        "statuses": STATUSES, "manager": ops.manager(), "can_create": bool(frappe.has_permission("Task", "create"))}


@frappe.whitelist()
def summary():
    """Counts for the dashboard header; scoped like list_work_orders(scope='mine') for technicians."""
    ops.system_user()
    filters = {"custom_work_order": 1, "is_template": 0, "status": ["not in", ["Completed", "Cancelled"]]}
    or_filters = None if ops.manager() else {"name": ["in", _mine() or [""]], "owner": frappe.session.user}
    rows = frappe.get_list("Task", filters=filters, or_filters=or_filters, fields=["status", "priority",
        "exp_end_date"], limit_page_length=0)
    today = getdate(nowdate())
    return {"open": len(rows),
        "overdue": sum(1 for r in rows if r.status == "Overdue" or (r.exp_end_date and getdate(r.exp_end_date) < today)),
        "due_today": sum(1 for r in rows if r.exp_end_date and getdate(r.exp_end_date) == today),
        "urgent": sum(1 for r in rows if r.priority in ("High", "Urgent")),
        "by_status": {s: sum(1 for r in rows if r.status == s) for s in ("Open", "Overdue", "Working", "Pending Review")}}


def _announce(doc, verb):
    """Post work order activity into chat channels linked to the work order's project."""
    if not doc.project:
        return
    from projectit.chat import post_system_message
    for channel in frappe.get_all("Techy Channel", filters={"project": doc.project, "archived": 0}, pluck="name"):
        post_system_message(channel, _("Work order #{0} {1}: {2}").format(doc.name, verb, doc.subject))


# Document events ---------------------------------------------------------------------------------------------

FINISHED = ("Pending Review", "Completed")


def _stamp_times(doc):
    """Record when a job was first started and when it was completed, for the reports."""
    if not doc.get("custom_work_order") or not doc.has_value_changed("status"):
        return
    if doc.status in ("Working", "Pending Review", "Completed") and not doc.get("custom_started_at"):
        doc.custom_started_at = now_datetime()
    doc.custom_completed_at = now_datetime() if doc.status == "Completed" else None
    # A job taken back from review or reopened after completion: the technician scorecard counts it.
    before = doc.get_doc_before_save() if callable(getattr(doc, "get_doc_before_save", None)) else None
    if before and before.status in FINISHED and doc.status not in FINISHED + ("Cancelled",):
        doc.custom_sent_back = cint(doc.get("custom_sent_back")) + 1


def validate_task(doc, method=None):
    """Block completing a work order with unanswered required procedure steps, or a PM work order whose
    maintenance task requires a certificate but has no file."""
    _stamp_times(doc)
    if doc.status != "Completed" or not doc.has_value_changed("status"):
        return
    if doc.get("custom_work_order") and not doc.is_new():
        missing = procedures.missing_required(doc.name)
        if missing:
            frappe.throw(_("Finish the procedure first: {0} required step(s) still need an answer.").format(missing))
        parts.check_open(doc.name)
        failures.on_complete(doc)
    if not doc.get("custom_asset_maintenance_log"):
        return
    if frappe.db.get_value("Asset Maintenance Log", doc.custom_asset_maintenance_log, "has_certificate") \
            and not ops.files("Task", doc.name):
        frappe.throw(_("This preventive maintenance task requires a certificate. Attach a photo or file first."))


def on_task_update(doc, method=None):
    if not doc.get("custom_work_order") or not doc.has_value_changed("status"):
        return
    people = set(_assignees([doc.name])[doc.name]) | {doc.owner}
    ops.push(people, "techy_work_order", {"name": doc.name, "status": doc.status})
    if doc.status in ("Pending Review", "Completed", "Cancelled"):
        timer.stop_all(doc)
    if doc.status != "Completed":
        return
    if doc.custom_asset_maintenance_log:
        from projectit.maintenance import complete_log
        complete_log(doc)
    if doc.get("custom_equipment") and doc.custom_work_category == "Installation":
        installed.complete_installation(doc)
    ratings.on_completed(doc)
    service_report.on_completed(doc)
    if doc.custom_work_request:
        request = frappe.get_doc("Issue", doc.custom_work_request)
        if request.status not in ("Resolved", "Closed"):
            request.status = "Resolved"
            request.flags.ignore_permissions = True
            request.save()
        request.add_comment("Info", escape(_("Work order {0} was completed.").format(doc.name)))
        requester = frappe.db.get_value("User", {"name": request.raised_by, "enabled": 1})
        ops.notify([requester], _("Your request was completed: {0}").format(request.subject), "Issue", request.name)
    _announce(doc, _("completed"))
