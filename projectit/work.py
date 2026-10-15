"""Techy Work screens for the signed-in employee.

Every read is scoped to the session's own Employee (resolved by attendance._employee, which also
requires the WorkIT module); no employee ID is accepted from the client.
"""
import frappe
from frappe.utils import cint, flt, get_datetime, getdate, nowdate, strip_html

from projectit import attendance, ops


def _projects(employee):
    rows = frappe.db.sql("""
        SELECT p.name AS project, p.project_name, pai.name AS allocation, pai.work_instruction,
            eai.instructions AS my_instructions
        FROM `tabEmployee Allocation Instruction` eai
        INNER JOIN `tabProject Allocation and Instrucions` pai ON pai.name = eai.parent
        INNER JOIN `tabProject` p ON p.name = pai.project
        WHERE eai.employee = %(employee)s AND eai.parenttype = 'Project Allocation and Instrucions'
          AND p.status = 'Open'
        ORDER BY p.project_name
    """, {"employee": employee}, as_dict=True)
    if not rows:
        return []
    # Teammates on the same allocations, and who has an open Techy check-in today.
    team = frappe.db.sql("""
        SELECT eai.parent AS allocation, eai.employee, eai.employee_name, e.user_id, e.image
        FROM `tabEmployee Allocation Instruction` eai
        INNER JOIN `tabEmployee` e ON e.name = eai.employee
        WHERE eai.parent IN %(allocations)s AND eai.parenttype = 'Project Allocation and Instrucions'
          AND e.status = 'Active'
        ORDER BY eai.employee_name
    """, {"allocations": tuple(r.allocation for r in rows)}, as_dict=True)
    on_site = {(r.employee, r.parent_project) for r in frappe.get_all("Timesheet", filters={
        "docstatus": 0, "start_date": nowdate(), "parent_project": ["in", [r.project for r in rows]],
    }, fields=["employee", "parent_project"])}
    for row in rows:
        row.work_instruction = strip_html(row.work_instruction or "")
        row.my_instructions = strip_html(row.my_instructions or "")
        row.team = [{"name": m.employee_name, "image": m.image, "me": m.employee == employee,
            "on_site": (m.employee, row.project) in on_site} for m in team if m.allocation == row.allocation]
        del row["allocation"]
    return rows


@frappe.whitelist()
def today():
    """Everything the Today screen needs in one round trip."""
    employee = attendance._employee()
    settings = frappe.get_single("Work Time Settings")
    return {
        "employee": employee.name,
        "employee_name": frappe.db.get_value("Employee", employee.name, "employee_name"),
        "session": attendance.get_active_session(),
        "projects": _projects(employee.name),
        "attendance": attendance.get_attendance_status(),
        "hours": {"start": str(settings.start_time or ""), "end": str(settings.end_time or "")},
        "server_time": str(frappe.utils.now_datetime()),
    }


@frappe.whitelist()
def history(start=0, page_length=None):
    """The employee's own Techy timesheets, newest first, with per-entry time logs."""
    employee = attendance._employee()
    start, size = max(0, cint(start)), ops.page_size(page_length, 30)
    sheets, total = ops.paged("Timesheet", {"employee": employee.name, "docstatus": ["<", 2]}, None,
        "start_date desc, creation desc", start, size, ["name", "start_date", "parent_project", "docstatus", "total_hours"])
    has_more = start + len(sheets) < total
    names = [s.name for s in sheets]
    logs = frappe.get_all("Timesheet Detail", filters={"parent": ["in", names or [""]], "parenttype": "Timesheet"},
        fields=["parent", "from_time", "to_time", "hours", "activity_type", "task"], order_by="from_time asc",
        limit_page_length=0) if names else []
    projects = dict(frappe.get_all("Project", filters={"name": ["in", list({s.parent_project for s in sheets if s.parent_project}) or [""]]},
        fields=["name", "project_name"], as_list=True))
    tasks = dict(frappe.get_all("Task", filters={"name": ["in", list({l.task for l in logs if l.task}) or [""]]},
        fields=["name", "subject"], as_list=True))
    overtime = frappe.db.get_single_value("Work Time Settings", "over_time_activity_type")
    for sheet in sheets:
        sheet.project_name = projects.get(sheet.parent_project, sheet.parent_project)
        sheet.logs = [l for l in logs if l.parent == sheet.name]
        sheet.task = next((tasks.get(l.task) for l in sheet.logs if l.task), None)
        sheet.started = min((get_datetime(l.from_time) for l in sheet.logs), default=None)
        sheet.ended = max((get_datetime(l.to_time) for l in sheet.logs if l.to_time), default=None)
        sheet.overtime_hours = sum(flt(l.hours) for l in sheet.logs if overtime and l.activity_type == overtime)
        sheet.open = sheet.docstatus == 0
    today_date = getdate(nowdate())
    week_start = getdate(frappe.utils.get_first_day_of_week(today_date))
    # Totals come from all of this week's sheets, not just the loaded page.
    week = frappe.get_all("Timesheet", filters={"employee": employee.name, "docstatus": 1,
        "start_date": [">=", week_start]}, fields=["start_date", "total_hours"])
    return {"timesheets": sheets, "has_more": has_more, "total": total, "start": start, "page_length": size,
        "totals": {"today": sum(flt(w.total_hours) for w in week if getdate(w.start_date) == today_date),
            "week": sum(flt(w.total_hours) for w in week), "week_start": str(week_start)}}
