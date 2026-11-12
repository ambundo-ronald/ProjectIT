"""Contractors checking in and out at sites (Techy Site Visit), so we know they are there and for how long.

Contractors are not Employees, so their check-ins are kept here rather than in Employee Checkin (which feeds HR and
payroll). It is the same screen as staff use: a photo and GPS at check-in, GPS at check-out, and it works offline
(the phone's time is accepted under the same rules as staff punches, see attendance._when).

- A visit is for one job, or for a project when there is no single job.
- The distance from the site is saved when the site has a location (on the machine, else on the project); a
  check-in further than Techy Ops Settings' *Flag check-ins further than* is flagged for managers.
- A forgotten check-out is closed at the end of the day (auto_close) with no hours. Those hours count for pay only
  once a manager confirms them.
- Hours from confirmed visits are what *Hourly* pay lines use when they are set to count check-in time.
"""
import math

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from projectit import contractors, ops

DOCTYPE = "Techy Site Visit"
FIELDS = ["name", "user", "full_name", "contractor", "work_order", "project", "status", "check_in_at", "check_out_at",
    "hours", "confirmed", "offline", "distance_m", "far", "in_latitude", "in_longitude", "manager_note"]
DEFAULT_DISTANCE = 500


def _distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def site_location(work_order=None, project=None):
    """(latitude, longitude) of the site: the job's machine, else the project. None when not known."""
    if work_order:
        equipment, project = frappe.db.get_value("Task", work_order, ["custom_equipment", "project"]) or (None, project)
        if equipment:
            spot = frappe.db.get_value("Techy Equipment", equipment, ["latitude", "longitude"])
            if spot and flt(spot[0]) and flt(spot[1]):
                return flt(spot[0]), flt(spot[1])
    if project:
        spot = frappe.db.get_value("Project", project, ["custom_site_latitude", "custom_site_longitude"])
        if spot and flt(spot[0]) and flt(spot[1]):
            return flt(spot[0]), flt(spot[1])
    return None


def _limit():
    value = frappe.db.get_single_value("Techy Ops Settings", "site_distance_m")
    return cint(value) if cint(value) > 0 else DEFAULT_DISTANCE


def _row(doc):
    row = {f: doc.get(f) for f in FIELDS}
    row["subject"] = frappe.db.get_value("Task", doc.work_order, "subject") if doc.get("work_order") else None
    row["project_name"] = frappe.db.get_value("Project", doc.project, "project_name") if doc.get("project") else None
    return row


def open_visit(user=None):
    user = user or frappe.session.user
    name = frappe.db.get_value(DOCTYPE, {"user": user, "status": "On site"}, "name", order_by="check_in_at desc")
    return _row(frappe.get_doc(DOCTYPE, name)) if name else None


def _places(member):
    """Where I can check in: my accepted open jobs, and my contractor's projects."""
    filters = {"custom_work_order": 1, "parent_task": ["is", "not set"], "custom_contractor": member.contractor,
        "custom_contractor_state": "Accepted", "status": ["not in", ["Completed", "Cancelled"]]}
    jobs = frappe.get_list("Task", filters=filters, fields=["name", "subject", "project", "custom_equipment"],
        order_by="exp_end_date asc", limit_page_length=200)
    names = sorted(contractors.allocated_projects(member.contractor) | {j.project for j in jobs if j.project})
    projects = frappe.get_all("Project", filters={"name": ["in", names or [""]], "status": "Open"},
        fields=["name", "project_name"], order_by="project_name asc")
    return {"jobs": jobs, "projects": projects}


@frappe.whitelist()
def status():
    """My open visit, my visits of the last two weeks, and where I can check in."""
    member = contractors.require_member()
    since = add_days(nowdate(), -14)
    recent = frappe.get_all(DOCTYPE, filters={"user": frappe.session.user, "check_in_at": [">=", since]},
        fields=FIELDS, order_by="check_in_at desc", limit_page_length=50)
    titles = dict(frappe.get_all("Task", filters={"name": ["in", [v.work_order for v in recent if v.work_order] or [""]]},
        fields=["name", "subject"], as_list=True))
    projects = dict(frappe.get_all("Project", filters={"name": ["in", [v.project for v in recent if v.project] or [""]]},
        fields=["name", "project_name"], as_list=True))
    for v in recent:
        v.subject, v.project_name = titles.get(v.work_order), projects.get(v.project)
    return {"visit": open_visit(), "recent": recent, "places": _places(member)}


def _check_place(member, work_order, project):
    """The job or project must be one I may check in to; returns (work_order, project)."""
    if work_order:
        doc = frappe.get_doc("Task", work_order)
        if not contractors.sees_job(doc) or doc.get("custom_contractor") != member.contractor:
            frappe.throw(_("This job is not yours."), frappe.PermissionError)
        if doc.get("custom_contractor_state") != "Accepted":
            frappe.throw(_("Accept the job before checking in to it."))
        if doc.status in ("Completed", "Cancelled"):
            frappe.throw(_("This job is closed."))
        return doc.name, doc.project
    if not project:
        frappe.throw(_("Choose the job or project you are at."))
    if project not in contractors.projects_for(frappe.session.user):
        frappe.throw(_("This project is not given to you."), frappe.PermissionError)
    if frappe.db.get_value("Project", project, "status") != "Open":
        frappe.throw(_("This project is not open."))
    return None, project


def _coordinates(latitude, longitude):
    from projectit.attendance import _coordinates as coordinates
    return coordinates(latitude, longitude)


@frappe.whitelist(methods=["POST"])
def check_in(latitude, longitude, photo, work_order=None, project=None, at=None):
    """Check in at a job's or project's site, with a photo and GPS."""
    member = contractors.require_member()
    latitude, longitude = _coordinates(latitude, longitude)
    current = open_visit()
    if current:
        if current["work_order"] == (work_order or None) and (work_order or current["project"] == project):
            return current  # a retry after a lost response
        frappe.throw(_("Check out of {0} first.").format(current["subject"] or current["project_name"] or _("your last site")))
    work_order, project = _check_place(member, work_order, project)
    from projectit.attendance import _when
    last_out = frappe.db.sql("SELECT MAX(check_out_at) FROM `tabTechy Site Visit` WHERE user = %s",
        (frappe.session.user,)) if at else None
    when, offline = _when(at, last_out[0][0] if last_out and last_out[0] else None)
    spot = site_location(work_order, project)
    distance = round(_distance_m(latitude, longitude, *spot)) if spot else None
    doc = frappe.get_doc({"doctype": DOCTYPE, "user": frappe.session.user, "contractor": member.contractor,
        "work_order": work_order, "project": project, "status": "On site", "check_in_at": when,
        "in_latitude": latitude, "in_longitude": longitude, "distance_m": distance,
        "far": 1 if distance is not None and distance > _limit() else 0, "offline": 1 if offline else 0})
    doc.insert(ignore_permissions=True)
    ops.save_photo(DOCTYPE, doc.name, photo, "site-visit", ignore_permissions=True)
    if doc.far:
        from projectit.meters import _managers
        ops.notify(_managers(), _("{0} checked in {1} m from the site").format(frappe.utils.get_fullname(), distance),
            DOCTYPE, doc.name)
    return _row(doc)


@frappe.whitelist(methods=["POST"])
def check_out(visit, latitude, longitude, photo=None, at=None):
    member = contractors.require_member()
    latitude, longitude = _coordinates(latitude, longitude)
    doc = frappe.get_doc(DOCTYPE, visit, for_update=True)
    if doc.user != frappe.session.user:
        frappe.throw(_("You can only check out of your own visit."), frappe.PermissionError)
    if doc.status != "On site":
        return _row(doc)  # a retry after a lost response
    from projectit.attendance import _when
    when, offline = _when(at, doc.check_in_at)
    doc.update({"status": "Checked out", "check_out_at": when, "out_latitude": latitude, "out_longitude": longitude,
        "hours": round((get_datetime(when) - get_datetime(doc.check_in_at)).total_seconds() / 3600, 2), "confirmed": 1})
    if offline:
        doc.offline = 1
    doc.save(ignore_permissions=True)
    if photo:
        ops.save_photo(DOCTYPE, doc.name, photo, "site-visit", ignore_permissions=True)
    return _row(doc)


# Managers ------------------------------------------------------------------------------------------------------

@frappe.whitelist()
def on_site():
    """Who is on site now: staff checked in with the Techy App, and contractors."""
    ops.require_manager()
    staff = frappe.db.sql("""
        SELECT e.employee_name AS full_name, e.user_id AS user, t.parent_project AS project, MIN(c.time) AS since,
            MAX(tl.task) AS work_order, MAX(c.latitude) AS latitude, MAX(c.longitude) AS longitude
        FROM `tabTimesheet` t
        JOIN `tabEmployee Checkin` c ON c.custom_timesheet = t.name AND c.log_type = 'IN'
        JOIN `tabEmployee` e ON e.name = t.employee
        LEFT JOIN `tabTimesheet Detail` tl ON tl.parent = t.name
        WHERE t.docstatus = 0
        GROUP BY t.name, e.employee_name, e.user_id, t.parent_project""", as_dict=True)
    visits = frappe.get_all(DOCTYPE, filters={"status": "On site"}, fields=FIELDS, order_by="check_in_at asc",
        limit_page_length=0)
    names = {v.contractor for v in visits if v.contractor}
    contractor_names = dict(frappe.get_all("Techy Contractor", filters={"name": ["in", list(names) or [""]]},
        fields=["name", "contractor_name"], as_list=True))
    jobs = {v.work_order for v in visits if v.work_order} | {s.work_order for s in staff if s.work_order}
    projects = {v.project for v in visits if v.project} | {s.project for s in staff if s.project}
    subjects = dict(frappe.get_all("Task", filters={"name": ["in", list(jobs) or [""]]}, fields=["name", "subject"], as_list=True))
    project_names = dict(frappe.get_all("Project", filters={"name": ["in", list(projects) or [""]]},
        fields=["name", "project_name"], as_list=True))
    people = []
    for s in staff:
        people.append({"kind": "Staff", "full_name": s.full_name, "user": s.user, "since": s.since,
            "work_order": s.work_order, "subject": subjects.get(s.work_order), "project": s.project,
            "project_name": project_names.get(s.project), "far": 0, "distance_m": None, "contractor_name": None})
    for v in visits:
        people.append({"kind": "Contractor", "full_name": v.full_name, "user": v.user, "since": v.check_in_at,
            "work_order": v.work_order, "subject": subjects.get(v.work_order), "project": v.project,
            "project_name": project_names.get(v.project), "far": v.far, "distance_m": v.distance_m,
            "contractor_name": contractor_names.get(v.contractor), "visit": v.name})
    people.sort(key=lambda p: (p["project_name"] or p["subject"] or "", str(p["since"])))
    return {"people": people, "staff": len(staff), "contractors": len(visits), "distance": _limit()}


@frappe.whitelist()
def visits(start=None, end=None, contractor=None, work_order=None, review=0):
    """Contractors' visits for managers. `review=1`: only the ones to look at (far from site, or not confirmed)."""
    ops.require_manager()
    start = getdate(start or add_days(nowdate(), -13))
    end = getdate(end or nowdate())
    filters = {"check_in_at": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]}
    if contractor:
        filters["contractor"] = contractor
    if work_order:
        filters["work_order"] = work_order
    rows = frappe.get_all(DOCTYPE, filters=filters, fields=FIELDS, order_by="check_in_at desc", limit_page_length=500)
    if cint(review):
        rows = [r for r in rows if r.far or (r.status != "On site" and not r.confirmed)]
    names = dict(frappe.get_all("Techy Contractor", filters={"name": ["in", list({r.contractor for r in rows}) or [""]]},
        fields=["name", "contractor_name"], as_list=True))
    subjects = dict(frappe.get_all("Task", filters={"name": ["in", [r.work_order for r in rows if r.work_order] or [""]]},
        fields=["name", "subject"], as_list=True))
    for r in rows:
        r.contractor_name, r.subject = names.get(r.contractor), subjects.get(r.work_order)
        r.photos = [f.file_url for f in ops.files(DOCTYPE, r.name)]
    return {"visits": rows, "start": start, "end": end, "distance": _limit()}


@frappe.whitelist(methods=["POST"])
def confirm(name, hours, note=None):
    """A manager confirms (or corrects) a visit's hours, for example after a forgotten check-out."""
    ops.require_manager()
    doc = frappe.get_doc(DOCTYPE, name, for_update=True)
    if doc.status == "On site":
        frappe.throw(_("This person is still on site."))
    hours = flt(hours)
    if hours < 0 or hours > 24:
        frappe.throw(_("Enter between 0 and 24 hours."))
    from projectit import contractor_pay
    contractor_pay.check_hours_open(doc.work_order, doc.contractor)
    old = doc.hours
    doc.hours, doc.confirmed = round(hours, 2), 1
    note = ops.text(note, "the note", 1000, required=False)
    doc.manager_note = "\n".join(filter(None, [doc.manager_note, _("{0}: {1} h → {2} h. {3}").format(
        frappe.utils.get_fullname(), flt(old), doc.hours, note or "").strip()]))
    if doc.status == "Auto closed" and not doc.check_out_at:
        doc.check_out_at = doc.check_in_at
    doc.save(ignore_permissions=True)
    return _row(doc)


@frappe.whitelist(methods=["POST"])
def set_site_location(visit):
    """Use where this person checked in as the site's location: the job's machine, or else the project."""
    ops.require_manager()
    doc = frappe.get_doc(DOCTYPE, visit)
    equipment = frappe.db.get_value("Task", doc.work_order, "custom_equipment") if doc.work_order else None
    if equipment:
        frappe.db.set_value("Techy Equipment", equipment, {"latitude": doc.in_latitude, "longitude": doc.in_longitude})
        where = frappe.db.get_value("Techy Equipment", equipment, "equipment_name")
    elif doc.project:
        frappe.db.set_value("Project", doc.project, {"custom_site_latitude": doc.in_latitude,
            "custom_site_longitude": doc.in_longitude})
        where = frappe.db.get_value("Project", doc.project, "project_name")
    else:
        frappe.throw(_("This visit has no job or project."))
    frappe.db.set_value(DOCTYPE, doc.name, {"distance_m": 0, "far": 0})
    return {"where": where}


def auto_close():
    """Scheduled (daily, just after midnight): close yesterday's forgotten check-outs with no hours, to confirm."""
    cutoff = f"{nowdate()} 00:00:00"
    names = frappe.get_all(DOCTYPE, filters={"status": "On site", "check_in_at": ["<", cutoff]}, pluck="name")
    if not names:
        return
    from projectit.meters import _managers
    for name in names:
        doc = frappe.get_doc(DOCTYPE, name)
        doc.update({"status": "Auto closed", "hours": 0, "confirmed": 0})
        doc.save(ignore_permissions=True)
        ops.notify([doc.user], _("You did not check out yesterday. Ask your manager to confirm your hours."), DOCTYPE, name)
    ops.notify(_managers(), _("{0} contractor check-out(s) were forgotten: confirm their hours").format(len(names)),
        DOCTYPE, names[0])


def confirmed_hours(work_order, contractor):
    """{user: hours} from confirmed visits to a job by a contractor's people."""
    rows = frappe.get_all(DOCTYPE, filters={"work_order": work_order, "contractor": contractor, "confirmed": 1,
        "status": ["!=", "On site"]}, fields=["user", "hours"], limit_page_length=0)
    out = {}
    for r in rows:
        out[r.user] = out.get(r.user, 0) + flt(r.hours)
    return out
