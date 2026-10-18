"""Who may see and change tasks and work orders.

Technicians (Maintenance User) and field staff (Employee) get Task read and write through their roles (set up on
migrate, see setup.ensure_task_permissions), narrowed by these hooks to:

- tasks and work orders assigned to them, or that they created, and the checklist steps under those;
- read-only: open work orders that nobody is assigned to yet, so they can pick one up;
- read-only: the projects they are allocated to in Techy Manage (and no others).

They can never delete a task. People with a wider role keep ERPNext's normal access: managers, Projects Users
(office staff who plan projects), HR and System Managers. A technician should therefore not also hold Projects
User, which would let them see, change and delete every task in Desk.

The same rules apply in Desk (lists, forms, reports) and in the app.
"""
import frappe

# Roles whose Task access is ERPNext's own (everything their role permissions allow).
FULL_ACCESS = {"System Manager", "Projects Manager", "Projects User", "Maintenance Manager", "HR Manager", "HR User"}
OPEN = ("Open", "Overdue")


def limited(user=None):
    """True for technicians and field staff, whose task access is narrowed to their own work."""
    user = user or frappe.session.user
    if user == "Administrator":
        return False
    return not set(frappe.get_roles(user)) & FULL_ACCESS


def assigned_to(name, user):
    return bool(name) and bool(frappe.db.exists("ToDo", {"reference_type": "Task", "reference_name": name,
        "allocated_to": user, "status": ["!=", "Cancelled"]}))


def is_mine(doc, user=None):
    """Assigned to the user or created by them (or a checklist step of such a task)."""
    user = user or frappe.session.user
    if doc.get("owner") == user or assigned_to(doc.name, user):
        return True
    parent = doc.get("parent_task")
    return bool(parent) and (assigned_to(parent, user) or frappe.db.get_value("Task", parent, "owner") == user)


def is_available(doc):
    """An open work order nobody is assigned to: anyone in Techy Ops may pick it up."""
    return bool(doc.get("custom_work_order")) and not doc.get("parent_task") and not doc.get("is_template") \
        and doc.get("status") in OPEN and not frappe.db.exists("ToDo", {"reference_type": "Task",
            "reference_name": doc.name, "status": ["!=", "Cancelled"]})


def task_permission(doc, ptype=None, user=None, debug=False):
    """has_permission hook for Task. It can only narrow what roles allow, never widen it."""
    user = user or frappe.session.user
    if not limited(user):
        return True
    if ptype == "delete":
        return False
    if ptype == "create" or doc.is_new():
        return True
    if is_mine(doc, user):
        return True
    return ptype in ("read", "print", "email") and is_available(doc)


def task_query(user=None):
    """permission_query_conditions hook for Task: the same rule for lists and reports."""
    user = user or frappe.session.user
    if not limited(user):
        return ""
    me = frappe.db.escape(user)
    todo = lambda field: (f"exists (select 1 from `tabToDo` td where td.reference_type = 'Task' "
        f"and td.reference_name = {field} and td.allocated_to = {me} and td.status != 'Cancelled')")
    nobody = ("not exists (select 1 from `tabToDo` td where td.reference_type = 'Task' "
        "and td.reference_name = `tabTask`.name and td.status != 'Cancelled')")
    mine = f"(`tabTask`.owner = {me} or {todo('`tabTask`.name')})"
    steps = (f"(ifnull(`tabTask`.parent_task, '') != '' and ({todo('`tabTask`.parent_task')} or exists "
        f"(select 1 from `tabTask` pt where pt.name = `tabTask`.parent_task and pt.owner = {me})))")
    pool = (f"(`tabTask`.custom_work_order = 1 and ifnull(`tabTask`.parent_task, '') = '' and `tabTask`.is_template = 0 "
        f"and `tabTask`.status in ('Open', 'Overdue') and {nobody})")
    return f"({mine} or {steps} or {pool})"


# Projects: field staff read the projects they are allocated to ------------------------------------------------

ALLOCATED = """select p.project from `tabProject Allocation and Instrucions` p
    join `tabEmployee Allocation Instruction` a on a.parent = p.name and a.parenttype = 'Project Allocation and Instrucions'
    join `tabEmployee` e on e.name = a.employee
    where e.user_id = {user} and e.status = 'Active'"""


def allocated_projects(user=None):
    user = user or frappe.session.user
    return {r[0] for r in frappe.db.sql(ALLOCATED.format(user="%s"), (user,))}


def project_permission(doc, ptype=None, user=None, debug=False):
    """has_permission hook for Project: field staff read only the projects they are allocated to."""
    user = user or frappe.session.user
    if not limited(user):
        return True
    return ptype in ("read", "print") and doc.name in allocated_projects(user)


def project_query(user=None):
    user = user or frappe.session.user
    if not limited(user):
        return ""
    return f"`tabProject`.name in ({ALLOCATED.format(user=frappe.db.escape(user))})"
