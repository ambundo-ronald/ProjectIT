"""Mobile/Desk access to native ERPNext Tasks, child Tasks and assignments."""
from html import escape
import base64
import binascii
import io

import frappe
from frappe import _
from frappe.utils import cint, strip_html

FIELDS = ["name", "subject", "project", "parent_task", "is_group", "status", "priority", "exp_end_date", "progress", "modified"]
STATUSES = ("Open", "Working", "Pending Review", "Completed", "Cancelled")


def _manager():
    return frappe.session.user != "Guest" and bool(set(frappe.get_roles()) & {"Projects Manager", "System Manager"})


def _login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please sign in."), frappe.PermissionError)


def _assigned_names():
    return frappe.get_all("ToDo", filters={"reference_type": "Task", "allocated_to": frappe.session.user,
        "status": ["!=", "Cancelled"]}, pluck="reference_name")


def _allocated_projects():
    from projectit.attendance import _employee
    employee = _employee()
    rows = frappe.db.sql("""SELECT DISTINCT p.project
        FROM `tabProject Allocation and Instrucions` p
        JOIN `tabEmployee Allocation Instruction` e ON e.parent = p.name
        WHERE e.employee = %s AND e.parenttype = 'Project Allocation and Instrucions'
    """, (employee.name,), as_dict=True)
    return [row.project for row in rows]


def _task(name, write=False):
    _login()
    doc = frappe.get_doc("Task", name, for_update=write)
    doc.check_permission("write" if write else "read")
    if not doc.project or doc.is_template:
        frappe.throw(_("Select a project task, not a template."))
    frappe.get_doc("Project", doc.project).check_permission("read")
    if not _manager():
        if doc.project not in _allocated_projects() or doc.name not in _assigned_names():
            frappe.throw(_("This task must be assigned to you in an allocated project."), frappe.PermissionError)
    return doc


def _workflow():
    return frappe.db.get_value("Workflow", {"document_type": "Task", "is_active": 1}, "name")


@frappe.whitelist()
def list_tasks(project=None, start=0, mine=1):
    _login()
    filters = {"is_template": 0, "project": ["is", "set"]}
    if project:
        frappe.get_doc("Project", project).check_permission("read")
        filters["project"] = project
    if not _manager():
        projects = _allocated_projects()
        if project and project not in projects:
            frappe.throw(_("You are not allocated to this project."), frappe.PermissionError)
        if not project:
            filters["project"] = ["in", projects or [""]]
    if cint(mine) or not _manager():
        filters["name"] = ["in", _assigned_names() or [""]]
    start = max(0, cint(start))
    rows = frappe.get_list("Task", filters=filters, fields=FIELDS,
        order_by="modified desc", limit_start=start, limit_page_length=51)
    return {"tasks": rows[:50], "has_more": len(rows) > 50, "manager": _manager()}


@frappe.whitelist()
def get_task(name):
    doc = _task(name)
    children_filters = {"parent_task": doc.name, "project": doc.project, "is_template": 0}
    if not _manager():
        children_filters["name"] = ["in", _assigned_names() or [""]]
    children = frappe.get_list("Task", filters=children_filters, fields=FIELDS,
        order_by="creation asc", limit_page_length=0)
    # These reads are scoped to a Task whose document permission was checked above.
    comments = frappe.get_all("Comment", filters={"reference_doctype": "Task", "reference_name": doc.name,
        "comment_type": "Comment"}, fields=["name", "content", "comment_by", "creation"],
        order_by="creation desc", limit_page_length=30)
    for comment in comments:
        comment.content = strip_html(comment.content or "")
    files = frappe.get_list("File", filters={"attached_to_doctype": "Task", "attached_to_name": doc.name},
        fields=["name", "file_name", "file_url"], limit_page_length=50)
    return {"task": {field: doc.get(field) for field in FIELDS}, "description": strip_html(doc.description or ""),
        "children": children, "comments": comments, "files": files, "workflow": _workflow(),
        "can_write": frappe.has_permission("Task", "write", doc=doc), "manager": _manager()}


@frappe.whitelist(methods=["POST"])
def update_status(name, status, modified):
    doc = _task(name, write=True)
    if _workflow():
        frappe.throw(_("This task uses an ERPNext Workflow. Use its workflow actions in Desk."))
    if status not in STATUSES or (status == "Cancelled" and not _manager()):
        frappe.throw(_("This status change is not allowed."), frappe.PermissionError)
    if str(doc.modified) != str(modified):
        frappe.throw(_("This task changed. Refresh it before saving."))
    doc.status = status
    doc.save()  # Native dependency/group validation, progress, audit and ToDo closure.
    return get_task(doc.name)


@frappe.whitelist(methods=["POST"])
def add_comment(name, content):
    doc = _task(name, write=True)
    content = str(content or "").strip()
    if not content or len(content) > 4000:
        frappe.throw(_("Enter a comment of 1 to 4000 characters."))
    doc.add_comment("Comment", escape(content))
    return get_task(doc.name)


@frappe.whitelist(methods=["POST"])
def attach_photo(name, content):
    from PIL import Image
    doc = _task(name, write=True)
    if not isinstance(content, str) or len(content) > 14000000:
        frappe.throw(_("Choose a photo smaller than 10 MB."))
    try:
        data = base64.b64decode(content, validate=True)
        with Image.open(io.BytesIO(data)) as photo:
            if photo.format not in ("JPEG", "PNG"):
                raise ValueError
            extension = "jpg" if photo.format == "JPEG" else "png"
            photo.verify()
    except (ValueError, binascii.Error, OSError):
        frappe.throw(_("Choose a valid JPEG or PNG photo."))
    frappe.get_doc({"doctype": "File", "file_name": f"task-{frappe.generate_hash(length=12)}.{extension}",
        "content": data, "is_private": 1, "attached_to_doctype": "Task", "attached_to_name": doc.name}).insert()
    return get_task(doc.name)


@frappe.whitelist()
def task_options(project=None):
    _login()
    if not _manager():
        frappe.throw(_("Project manager access is required."), frappe.PermissionError)
    projects = frappe.get_list("Project", filters={"status": "Open"}, fields=["name", "project_name"],
        order_by="project_name asc", limit_page_length=0)
    people = []
    if project:
        frappe.get_doc("Project", project).check_permission("write")
        people = frappe.db.sql("""SELECT DISTINCT e.user_id, e.employee_name
            FROM `tabEmployee` e JOIN `tabEmployee Allocation Instruction` a ON a.employee = e.name
            JOIN `tabProject Allocation and Instrucions` p ON p.name = a.parent
            JOIN `tabUser` u ON u.name = e.user_id
            WHERE p.project = %s AND e.status = 'Active' AND u.enabled = 1
              AND a.parenttype = 'Project Allocation and Instrucions'
            ORDER BY e.employee_name
        """, (project,), as_dict=True)
    return {"projects": projects, "people": people}


def _steps(value):
    values = frappe.parse_json(value) if isinstance(value, str) else value
    if not isinstance(values, list) or len(values) > 50:
        frappe.throw(_("Provide at most 50 checklist steps."))
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 140:
            frappe.throw(_("Each step needs a title of 1 to 140 characters."))
        result.append(value.strip())
    return result


@frappe.whitelist(methods=["POST"])
def create_task(project, subject, assignee, steps=None, parent_task=None, due_date=None, priority="Medium"):
    from frappe.desk.form.assign_to import add
    options = task_options(project)  # Manager role AND project write permission.
    if assignee not in [person.user_id for person in options["people"]]:
        frappe.throw(_("Assign to an active user allocated to this project."), frappe.PermissionError)
    if not isinstance(subject, str) or not subject.strip() or len(subject.strip()) > 140:
        frappe.throw(_("Enter a task title of 1 to 140 characters."))
    if priority not in ("Low", "Medium", "High", "Urgent"):
        frappe.throw(_("Invalid task priority."))
    if frappe.get_doc("Project", project).status != "Open":
        frappe.throw(_("The project must be open."))
    steps = _steps(steps or [])
    if parent_task:
        parent = _task(parent_task, write=True)
        if parent.project != project or not parent.is_group or parent.status in ("Completed", "Cancelled"):
            frappe.throw(_("Choose an open group task in the same project."))
    def insert(title, parent=None, group=False):
        doc = frappe.get_doc({"doctype": "Task", "subject": title, "project": project,
            "parent_task": parent, "is_group": int(group), "priority": priority,
            "exp_end_date": due_date or None, "status": "Open"})
        doc.insert()
        add({"doctype": "Task", "name": doc.name, "assign_to": [assignee], "description": title})
        return doc
    root = insert(subject.strip(), parent_task, bool(steps))
    for step in steps:
        insert(step, root.name)
    return {"name": root.name}


@frappe.whitelist()
def work_tasks(project):
    _login()
    if project not in _allocated_projects():
        frappe.throw(_("You are not allocated to this project."), frappe.PermissionError)
    frappe.get_doc("Project", project).check_permission("read")
    return frappe.get_list("Task", filters={"project": project, "is_group": 0, "is_template": 0,
        "name": ["in", _assigned_names() or [""]], "status": ["not in", ["Completed", "Cancelled"]]},
        fields=["name", "subject"], order_by="subject asc", limit_page_length=0)
