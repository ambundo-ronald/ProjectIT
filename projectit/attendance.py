"""Authenticated field-work punches. HRMS owns attendance calculation.

Each POST is one Frappe transaction: timesheet, photo and punch succeed together.
Employee row locks serialize Techy App retries and simultaneous phone requests.
No attendance status, shift, employee ID or timestamp is accepted from the client.
"""
import base64
import binascii
import io
from html import escape
import math

import frappe
from frappe import _
from frappe.utils import get_datetime, get_time, now_datetime

from projectit.work_time import split_work_time


def _employee(lock=False):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please sign in."), frappe.PermissionError)
    employees = frappe.get_all(
        "Employee", filters={"user_id": frappe.session.user, "status": "Active"},
        fields=["name", "company"], limit_page_length=2,
    )
    if len(employees) != 1:
        frappe.throw(_("Your account must be linked to exactly one active Employee."), frappe.PermissionError)
    employee = employees[0]
    if lock:
        frappe.db.get_value("Employee", employee.name, "name", for_update=True)
    if not frappe.db.exists("Mobile Module", {
        "parent": employee.name, "parenttype": "Employee",
        "parentfield": "custom_mobile_module", "module_name": "WorkIT",
    }):
        frappe.throw(_("Techy Work access is required."), frappe.PermissionError)
    return employee


def _coordinates(latitude, longitude):
    try:
        lat, lon = float(latitude), float(longitude)
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except (TypeError, ValueError):
        frappe.throw(_("A valid GPS location is required."))
    return lat, lon


def _photo(content, filename, timesheet):
    from PIL import Image
    try:
        image = base64.b64decode(content, validate=True)
        with Image.open(io.BytesIO(image)) as photo:
            if photo.format not in ("PNG", "JPEG"):
                raise ValueError
            extension = "png" if photo.format == "PNG" else "jpg"
            photo.verify()
    except (ValueError, TypeError, binascii.Error, OSError):
        frappe.throw(_("Please capture a valid PNG or JPEG photo."))
    # Generate the filename on the server; keep employee photos private.
    frappe.get_doc({
        "doctype": "File", "file_name": f"techy-{frappe.generate_hash(length=12)}.{extension}",
        "attached_to_doctype": "Timesheet", "attached_to_name": timesheet,
        "is_private": 1, "content": image,
    }).insert()


def _active_timesheet(employee, lock=False):
    rows = frappe.db.sql("""
        SELECT DISTINCT t.name
        FROM `tabTimesheet` t
        INNER JOIN `tabEmployee Checkin` c ON c.custom_timesheet = t.name
        WHERE t.employee = %(employee)s AND t.docstatus = 0
          AND c.employee = t.employee AND c.log_type = 'IN'
        ORDER BY t.name
        LIMIT 2
    """ + (" FOR UPDATE" if lock else ""), {"employee": employee}, as_dict=True)
    if len(rows) > 1:
        frappe.throw(_("Multiple open check-ins exist. Ask your manager to reconcile them before continuing."))
    if rows:
        return frappe.get_doc("Timesheet", rows[0].name, for_update=lock)


def _summary(doc):
    return {
        "name": doc.name, "project": doc.parent_project,
        "project_name": frappe.db.get_value("Project", doc.parent_project, "project_name"),
        "from_time": min(get_datetime(row.from_time) for row in doc.time_logs),
        "note": doc.note or "", "docstatus": doc.docstatus,
        "task": doc.time_logs[0].get("task") if doc.time_logs else None,
    }


def _punch(employee, timesheet, log_type, timestamp, latitude, longitude):
    log = frappe.get_doc({
        "doctype": "Employee Checkin", "employee": employee,
        "custom_timesheet": timesheet, "log_type": log_type, "time": timestamp,
        "latitude": latitude, "longitude": longitude, "skip_auto_attendance": 0,
    })
    # Use normal permissions and HRMS validation (shift lookup and geofencing included).
    log.insert()
    return log


@frappe.whitelist()
def get_active_session():
    employee = _employee()
    doc = _active_timesheet(employee.name)
    if doc:
        doc.check_permission("read")
        return _summary(doc)


@frappe.whitelist(methods=["POST"])
def check_in(project, latitude, longitude, photo, filename=None, task=None):
    employee = _employee(lock=True)
    latitude, longitude = _coordinates(latitude, longitude)
    active = _active_timesheet(employee.name, lock=True)
    if active:
        active.check_permission("read")
        if active.parent_project != project or (task and active.time_logs[0].get("task") != task):
            frappe.throw(_("Check out of your current project first."))
        return _summary(active)
    if task:
        from projectit.tasks import _task
        task_doc = _task(task)
        if task_doc.project != project or task_doc.is_group or task_doc.status in ("Completed", "Cancelled"):
            frappe.throw(_("Choose an open task in the selected project."))
        if not frappe.db.exists("ToDo", {"reference_type": "Task", "reference_name": task,
                "allocated_to": frappe.session.user, "status": "Open"}):
            frappe.throw(_("The task must be assigned to you."), frappe.PermissionError)
    project_doc = frappe.get_doc("Project", project)
    project_doc.check_permission("read")
    if project_doc.status != "Open":
        frappe.throw(_("This project is not open."))
    allocation = frappe.db.sql("""
        SELECT e.name FROM `tabEmployee Allocation Instruction` e
        INNER JOIN `tabProject Allocation and Instrucions` p ON p.name = e.parent
        WHERE p.project = %(project)s AND e.employee = %(employee)s
          AND e.parenttype = 'Project Allocation and Instrucions'
        LIMIT 1
    """, {"project": project, "employee": employee.name})
    if not allocation:
        frappe.throw(_("You are not allocated to this project."), frappe.PermissionError)
    timestamp = now_datetime().replace(microsecond=0)
    doc = frappe.get_doc({
        "doctype": "Timesheet", "employee": employee.name, "company": employee.company,
        "parent_project": project, "customer": project_doc.customer,
        "note": f"<p>Check in at {timestamp}</p>",
        "time_logs": [{"from_time": timestamp, "project": project, "task": task}],
    })
    doc.insert()
    _punch(employee.name, doc.name, "IN", timestamp, latitude, longitude)
    _photo(photo, filename, doc.name)
    return _summary(doc)


@frappe.whitelist(methods=["POST"])
def check_out(timesheet, latitude, longitude, photo, filename=None):
    employee = _employee(lock=True)
    latitude, longitude = _coordinates(latitude, longitude)
    doc = frappe.get_doc("Timesheet", timesheet, for_update=True)
    if doc.employee != employee.name:
        frappe.throw(_("You can only check out your own timesheet."), frappe.PermissionError)
    doc.check_permission("write")
    doc.check_permission("submit")
    punches = frappe.db.sql("""
        SELECT name, log_type, time FROM `tabEmployee Checkin`
        WHERE custom_timesheet = %(timesheet)s AND employee = %(employee)s
        ORDER BY time ASC FOR UPDATE
    """, {"timesheet": doc.name, "employee": employee.name}, as_dict=True)
    if doc.docstatus == 1 and any(p.log_type == "OUT" for p in punches):
        return _summary(doc)  # Retry after a lost success response.
    if doc.docstatus != 0 or any(p.log_type == "OUT" for p in punches):
        frappe.throw(_("This timesheet is not an open Techy App check-in."))
    starts = [get_datetime(p.time) for p in punches if p.log_type == "IN"]
    if len(starts) != 1:
        frappe.throw(_("A single linked IN log is required. Ask your manager to reconcile this timesheet."))
    timestamp = now_datetime().replace(microsecond=0)
    settings = frappe.get_single("Work Time Settings")
    if not all(settings.get(field) is not None and settings.get(field) != "" for field in (
        "start_time", "end_time", "regular_time_activity_type", "over_time_activity_type",
    )):
        frappe.throw(_("Ask your manager to configure all Work Time Settings before checkout."))
    try:
        segments = split_work_time(starts[0], timestamp, get_time(settings.start_time), get_time(settings.end_time))
    except ValueError as error:
        frappe.throw(_(str(error)))
    task_names = {row.get("task") for row in doc.time_logs}
    if len(task_names) > 1:
        frappe.throw(_("This timesheet contains multiple tasks. Ask your manager to review it before checkout."))
    task_name = next(iter(task_names), None)
    doc.set("time_logs", [])
    for start, end, regular in segments:
        doc.append("time_logs", {
            "from_time": start, "to_time": end, "project": doc.parent_project, "task": task_name,
            "activity_type": settings.regular_time_activity_type if regular else settings.over_time_activity_type,
        })
    doc.note = (doc.note or "") + f"<p>Check out at {timestamp}</p>"
    doc.submit()
    _punch(employee.name, doc.name, "OUT", timestamp, latitude, longitude)
    _photo(photo, filename, doc.name)
    return _summary(doc)


@frappe.whitelist()
def get_attendance_status():
    employee = _employee()
    # Scope these reads to the signed-in employee; never accept an employee ID.
    records = frappe.get_all("Attendance", filters={
        "employee": employee.name, "docstatus": ["<", 2],
    }, fields=["name", "attendance_date", "status", "docstatus", "shift", "working_hours"],
        order_by="attendance_date desc", limit_page_length=14)
    logs = frappe.get_all("Employee Checkin", filters={
        "employee": employee.name, "custom_timesheet": ["is", "set"],
    }, fields=["name", "log_type", "time", "shift", "offshift", "skip_auto_attendance", "attendance"],
        order_by="time desc", limit_page_length=1)
    message = _("Check in and out to record your working time. Attendance is calculated using your HRMS shift rules.")
    if logs:
        log = logs[0]
        if log.attendance:
            message = _("Your latest check-in has been processed by HRMS. See your attendance below.")
        elif log.skip_auto_attendance:
            message = _("Your latest check-in needs HR review: HRMS has skipped it for auto-attendance.")
        elif log.offshift or not log.shift:
            message = _("Your latest check-in is outside an assigned shift. Ask HR to check your shift assignment and punch window.")
        else:
            shift = frappe.get_cached_doc("Shift Type", log.shift)
            if not shift.enable_auto_attendance or not shift.process_attendance_after or not shift.last_sync_of_checkin:
                message = _("Your shift's auto-attendance setup is incomplete. Ask HR to enable it and configure the processing dates.")
            elif get_datetime(log.time) < get_datetime(shift.process_attendance_after):
                message = _("Your latest check-in is before the shift's attendance processing start date. Ask HR to review the shift settings.")
            elif log.log_type == "IN":
                message = _("Checked in. Check out when you finish; attendance will be calculated after your shift is processed.")
            else:
                message = _("Checked out. Attendance is pending HRMS shift processing; this does not yet mean Present.")
    return {"message": message, "records": records}


@frappe.whitelist(methods=["POST"])
def add_photo(timesheet, photo, caption=""):
    employee = _employee(lock=True)
    doc = frappe.get_doc("Timesheet", timesheet, for_update=True)
    if doc.employee != employee.name:
        frappe.throw(_("You can only update your own timesheet."), frappe.PermissionError)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("Photo updates require an open timesheet."))
    _photo(photo, None, doc.name)
    text = escape(str(caption or "")[:2000])
    doc.note = (doc.note or "") + f"<p>Photo update at {now_datetime()}: {text}</p>"
    doc.save()
    return _summary(doc)
