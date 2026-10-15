"""Techy Manage: project crews, site instructions and per-person instructions.

Access requires the signed-in user's Employee to have the ManageIT module; reads use the user's
Project permissions. Writes need Project read on that project plus role permission to write
allocations. HRMS gives every employee a User Permission limited to their own Employee record,
which would otherwise block a manager from saving crew rows that link to other employees.
"""
import frappe
from frappe import _
from frappe.utils import strip_html

ALLOCATION = "Project Allocation and Instrucions"


def _require_manager():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please sign in."), frappe.PermissionError)
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
    if not employee or not frappe.db.exists("Mobile Module", {"parent": employee, "parenttype": "Employee",
            "parentfield": "custom_mobile_module", "module_name": "ManageIT"}):
        frappe.throw(_("Techy Manage access is required."), frappe.PermissionError)


def _text(value, limit=4000):
    value = str(value or "").strip()
    if len(value) > limit:
        frappe.throw(_("Keep instructions under {0} characters.").format(limit))
    return value


def _resolve(project):
    """Accept a Project ID or, for old bookmarked links, its project name."""
    if frappe.db.exists("Project", project):
        return project
    name = frappe.db.get_value("Project", {"project_name": project})
    if not name:
        frappe.throw(_("Project {0} was not found.").format(project), frappe.DoesNotExistError)
    return name


def _allocation(project, write=False):
    """The project's allocation document, created on demand for projects that predate Techy App."""
    frappe.get_doc("Project", project).check_permission("read")
    if write and not frappe.has_permission(ALLOCATION, "write"):
        frappe.throw(_("You are not permitted to change project crews."), frappe.PermissionError)
    name = frappe.db.get_value(ALLOCATION, {"project": project})
    if name:
        doc = frappe.get_doc(ALLOCATION, name, for_update=write)
    else:
        doc = frappe.get_doc({"doctype": ALLOCATION, "project": project})
    if write:
        # Authorised above (ManageIT, project read, role write); skip per-row Employee user permissions.
        doc.flags.ignore_permissions = True
        if doc.is_new():
            doc.insert()
    return doc


def _on_site(projects):
    """(employee, project) -> check-in time, for open Techy App check-ins."""
    if not projects:
        return {}
    rows = frappe.db.sql("""
        SELECT t.employee, t.parent_project, MIN(c.time) AS since
        FROM `tabTimesheet` t
        INNER JOIN `tabEmployee Checkin` c ON c.custom_timesheet = t.name AND c.log_type = 'IN'
        WHERE t.docstatus = 0 AND t.parent_project IN %(projects)s
        GROUP BY t.employee, t.parent_project
    """, {"projects": tuple(projects)}, as_dict=True)
    return {(r.employee, r.parent_project): r.since for r in rows}


def _crew(allocations, on_site):
    """Allocation name -> crew rows with on-site status."""
    names = [a.name for a in allocations if a.name]
    rows = frappe.db.sql("""
        SELECT eai.parent, eai.employee, eai.employee_name, eai.instructions, e.image, e.designation, e.status
        FROM `tabEmployee Allocation Instruction` eai
        LEFT JOIN `tabEmployee` e ON e.name = eai.employee
        WHERE eai.parent IN %(names)s AND eai.parenttype = %(doctype)s
        ORDER BY eai.employee_name
    """, {"names": tuple(names), "doctype": ALLOCATION}, as_dict=True) if names else []
    project_of = {a.name: a.project for a in allocations}
    crew = {}
    for r in rows:
        since = on_site.get((r.employee, project_of[r.parent]))
        crew.setdefault(r.parent, []).append({"employee": r.employee, "name": r.employee_name, "image": r.image,
            "designation": r.designation, "active": r.status == "Active", "instructions": strip_html(r.instructions or ""),
            "on_site": bool(since), "since": since})
    return crew


@frappe.whitelist()
def overview():
    _require_manager()
    projects = frappe.get_list("Project", filters={"status": "Open"}, fields=["name", "project_name", "expected_end_date"],
        order_by="project_name asc", limit_page_length=0)
    allocations = frappe.get_all(ALLOCATION, filters={"project": ["in", [p.name for p in projects] or [""]]},
        fields=["name", "project", "work_instruction"])
    by_project = {a.project: a for a in allocations}
    crew = _crew(allocations, _on_site([p.name for p in projects]))
    for p in projects:
        allocation = by_project.get(p.name)
        p.work_instruction = strip_html(allocation.work_instruction or "") if allocation else ""
        p.crew = crew.get(allocation.name, []) if allocation else []
    people = {m["employee"] for p in projects for m in p.crew}
    return {"projects": projects, "totals": {"projects": len(projects), "crew": len(people),
        "on_site": len({m["employee"] for p in projects for m in p.crew if m["on_site"]})}}


@frappe.whitelist()
def project(project):
    _require_manager()
    project = _resolve(project)
    doc = _allocation(project)
    info = frappe.db.get_value("Project", project, ["name", "project_name", "status", "expected_start_date",
        "expected_end_date", "customer"], as_dict=True)
    crew = _crew([doc], _on_site([project])).get(doc.name, []) if doc.name else []
    allocated = {m["employee"] for m in crew}
    # People who can be added: active employees with Techy Work enabled.
    available = frappe.db.sql("""
        SELECT DISTINCT e.name AS employee, e.employee_name AS name, e.image, e.designation
        FROM `tabEmployee` e
        INNER JOIN `tabMobile Module` mm ON mm.parent = e.name AND mm.parenttype = 'Employee'
            AND mm.parentfield = 'custom_mobile_module' AND mm.module_name = 'WorkIT'
        WHERE e.status = 'Active'
        ORDER BY e.employee_name
    """, as_dict=True)
    return {"project": info, "work_instruction": strip_html(doc.work_instruction or ""), "crew": crew,
        "available": [a for a in available if a.employee not in allocated],
        "can_edit": bool(frappe.has_permission(ALLOCATION, "write"))}


@frappe.whitelist(methods=["POST"])
def save_instructions(project, work_instruction):
    _require_manager()
    doc = _allocation(project, write=True)
    doc.work_instruction = _text(work_instruction)
    doc.save()
    return {"work_instruction": doc.work_instruction}


@frappe.whitelist(methods=["POST"])
def add_member(project, employee, instructions=None):
    _require_manager()
    doc = _allocation(project, write=True)
    if not frappe.db.exists("Employee", {"name": employee, "status": "Active"}):
        frappe.throw(_("Choose an active employee."))
    if any(row.employee == employee for row in doc.allocation):
        frappe.throw(_("{0} is already on this project.").format(frappe.db.get_value("Employee", employee, "employee_name")))
    doc.append("allocation", {"employee": employee, "instructions": _text(instructions)})
    doc.save()
    return project_detail(project)


@frappe.whitelist(methods=["POST"])
def update_member(project, employee, instructions):
    _require_manager()
    doc = _allocation(project, write=True)
    row = next((r for r in doc.allocation if r.employee == employee), None)
    if not row:
        frappe.throw(_("This person is not on the project."))
    row.instructions = _text(instructions)
    doc.save()
    return {"employee": employee, "instructions": row.instructions}


@frappe.whitelist(methods=["POST"])
def remove_member(project, employee):
    _require_manager()
    doc = _allocation(project, write=True)
    before = len(doc.allocation)
    doc.allocation = [r for r in doc.allocation if r.employee != employee]
    if len(doc.allocation) == before:
        frappe.throw(_("This person is not on the project."))
    doc.save()
    return project_detail(project)


project_detail = project
