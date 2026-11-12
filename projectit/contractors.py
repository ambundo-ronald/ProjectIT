"""External technicians (contractors): individuals, and small companies with their own crews.

A Techy Contractor is linked to an ERPNext Supplier, which their bills go to (see contractor_pay and payouts). Its
people sign in to the Techy App with their own accounts:

- Owner: runs the contractor in the app. Accepts jobs, assigns crew, adds and removes their people, sees the pay.
- Lead: accepts jobs and assigns crew. Does not see pay.
- Crew: does the jobs given to them.

The accounts are Website Users (no Desk) with the Techy Contractor role. They get Task read and write through that
role (setup.ensure_task_permissions), narrowed by projectit.permissions to their own jobs, and guard() (an auth hook)
lets them call only the job screens' endpoints and their own (contractors, site_visits, contractor_pay). Customer
prices, invoices, chat and the rest of Techy Ops stay closed to them, even if an endpoint forgot a check.

A work order or project is given to a contractor, not just a person. A job is *Offered* until the owner or a lead
accepts it; only then can their crew work on it.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, validate_email_address

from projectit import ops

ROLE = "Techy Contractor"
HOME = "techy-app/contractor"
DOCTYPE = "Techy Contractor"
MEMBER = "Techy Contractor Member"
MEMBER_ROLES = ("Owner", "Lead", "Crew")
RUN_JOBS = ("Owner", "Lead")
STATES = ("Offered", "Accepted", "Declined")

# What a contractor's account may call besides its own endpoints (ALLOWED_PREFIXES): the work order screen.
ALLOWED = {"login", "logout", "frappe.handler.logout", "frappe.auth.get_logged_user", "projectit.api.get_modules_for_router",
    "projectit.api.my_apps", "projectit.api.get_header_info", "projectit.api.get_employee_id",
    "projectit.push.public_key", "projectit.push.subscribe", "projectit.push.unsubscribe", "projectit.push.pending",
    "projectit.push.test", "projectit.device_auth.my_devices", "projectit.device_auth.sign_out_device",
    # Their jobs: the same screen as our technicians (narrowed by projectit.permissions, redacted in work_orders.detail).
    "projectit.work_orders.get_work_order", "projectit.work_orders.update_work_order",
    "projectit.work_orders.toggle_step", "projectit.work_orders.add_comment", "projectit.work_orders.attach_photo",
    "projectit.work_orders.on_my_way",
    "projectit.procedures.answer", "projectit.procedures.get_procedure",
    "projectit.timer.start", "projectit.timer.stop", "projectit.timer.add_time", "projectit.timer.update_entry",
    "projectit.timer.delete_entry",
    "projectit.parts.search_parts", "projectit.parts.part_warehouses", "projectit.parts.add_part",
    "projectit.parts.remove_part", "projectit.parts.request_approval",
    "projectit.meters.record_reading", "projectit.meters.get_meter", "projectit.meters.list_meters",
    "projectit.failures.options", "projectit.failures.set_failure"}
ALLOWED_PREFIXES = ("projectit.contractors.", "projectit.site_visits.", "projectit.contractor_pay.")


# Who is who ----------------------------------------------------------------------------------------------------

def is_contractor(user=None):
    """A contractor's account (whether or not it is still active)."""
    user = user or frappe.session.user
    if user in ("Guest", "Administrator"):
        return False
    return ROLE in frappe.get_roles(user)


def membership(user=None):
    """The person's active place in an active contractor: contractor, contractor_name, contractor_type and
    member_role. None for everyone else. Cached for the request."""
    user = user or frappe.session.user
    if not is_contractor(user):
        return None
    cache = getattr(frappe.local, "techy_contractor_members", None)
    if cache is None:
        cache = frappe.local.techy_contractor_members = {}
    if user not in cache:
        rows = frappe.db.sql("""SELECT m.parent AS contractor, m.member_role, c.contractor_name, c.contractor_type,
                c.pay_cycle, c.purchases
            FROM `tabTechy Contractor Member` m JOIN `tabTechy Contractor` c ON c.name = m.parent
            WHERE m.parenttype = 'Techy Contractor' AND m.user = %s AND m.enabled = 1 AND c.enabled = 1
            LIMIT 1""", (user,), as_dict=True)
        cache[user] = frappe._dict(rows[0]) if rows else None
    return cache[user]


def runs_jobs(member):
    return bool(member) and member.member_role in RUN_JOBS


def sees_pay(member):
    return bool(member) and member.member_role == "Owner"


def require_member(roles=None):
    """The signed-in contractor's membership, optionally only for some member roles."""
    ops.login()
    member = membership()
    if not member:
        frappe.throw(_("This account is not part of an active contractor. Ask us to check it."), frappe.PermissionError)
    if roles and member.member_role not in roles:
        frappe.throw(_("Ask your {0} to do this.").format(_("owner") if roles == ("Owner",) else _("owner or lead")),
            frappe.PermissionError)
    return member


def members(contractor, enabled_only=True):
    filters = {"parent": contractor, "parenttype": DOCTYPE}
    if enabled_only:
        filters["enabled"] = 1
    return frappe.get_all(MEMBER, filters=filters, fields=["user", "full_name", "member_role", "enabled", "phone",
        "invited_on"], order_by="idx asc")


def job_runners(contractor):
    """The owner and leads: who is told about new jobs."""
    return [m.user for m in members(contractor) if m.member_role in RUN_JOBS]


# Every request -------------------------------------------------------------------------------------------------

def guard():
    """auth_hooks: a contractor's account reaches only its own endpoints and the job screen's."""
    request = getattr(frappe.local, "request", None)
    if not request or not is_contractor():
        return
    from projectit.customer_accounts import _method
    path = request.path or ""
    method = _method(path, frappe.local.form_dict or {})
    if method is None and not path.startswith("/api/"):
        return  # pages: the app itself, /update-password, assets (Desk is closed to Website Users anyway)
    if method in ("logout", "frappe.handler.logout", "projectit.device_auth.sign_out"):
        return
    allowed = method and (method in ALLOWED or method.startswith(ALLOWED_PREFIXES))
    if not allowed or not membership():
        frappe.throw(_("Not permitted."), frappe.PermissionError)


# Jobs a contractor may see (used by projectit.permissions) -----------------------------------------------------

def sees_job(doc, user=None):
    """A contractor's person sees a job assigned to them, and the owner and leads see all their contractor's jobs."""
    member = membership(user)
    if not member:
        return False
    from projectit.permissions import assigned_to
    user = user or frappe.session.user
    if assigned_to(doc.name, user):
        return True
    contractor = doc.get("custom_contractor")
    parent = doc.get("parent_task")
    if parent:
        if assigned_to(parent, user):
            return True
        contractor = contractor or frappe.db.get_value("Task", parent, "custom_contractor")
    return runs_jobs(member) and contractor == member.contractor


def job_query(user):
    """SQL for the Task list: the same rule as sees_job."""
    member = membership(user)
    if not member:
        return "1 = 0"
    me = frappe.db.escape(user)
    todo = lambda field: (f"exists (select 1 from `tabToDo` td where td.reference_type = 'Task' "
        f"and td.reference_name = {field} and td.allocated_to = {me} and td.status != 'Cancelled')")
    rule = f"({todo('`tabTask`.name')} or (ifnull(`tabTask`.parent_task, '') != '' and {todo('`tabTask`.parent_task')}))"
    if runs_jobs(member):
        mine = frappe.db.escape(member.contractor)
        rule = (f"({rule} or `tabTask`.custom_contractor = {mine} or exists (select 1 from `tabTask` pt "
            f"where pt.name = `tabTask`.parent_task and pt.custom_contractor = {mine}))")
    return rule


def allocated_projects(contractor):
    """Projects their contractor was given in Techy Manage."""
    return set(frappe.db.sql_list("""SELECT p.project FROM `tabProject Allocation and Instrucions` p
        JOIN `tabTechy Contractor Allocation` a ON a.parent = p.name AND a.parenttype = 'Project Allocation and Instrucions'
        WHERE a.contractor = %s""", (contractor,)))


def projects_for(user):
    """Projects a contractor's person may read: given to their contractor, or of jobs they can see."""
    member = membership(user)
    if not member:
        return set()
    jobs = frappe.db.sql_list(f"SELECT DISTINCT project FROM `tabTask` WHERE ifnull(project, '') != '' AND {job_query(user)}")
    return allocated_projects(member.contractor) | set(jobs)


def check_can_work(doc):
    """Contractors work on a job only once it is accepted (work_orders._work_order calls this for writes)."""
    if not is_contractor():
        return
    if doc.get("custom_contractor_state") != "Accepted":
        frappe.throw(_("Accept this job first.") if doc.get("custom_contractor_state") == "Offered"
            else _("This job is not open to you."), frappe.PermissionError)


# Accounts ------------------------------------------------------------------------------------------------------

def _contractor_doc(name, write=False):
    if not name or not frappe.db.exists(DOCTYPE, name):
        frappe.throw(_("Choose a contractor."))
    return frappe.get_doc(DOCTYPE, name, for_update=write)


def _scope(contractor=None, roles=("Owner",)):
    """(contractor, staff?) the caller may manage: managers any; a contractor's owner only their own."""
    member = membership()
    if member:
        if member.member_role not in roles:
            frappe.throw(_("Ask your owner to change your crew."), frappe.PermissionError)
        return member.contractor, False
    ops.require_manager()
    _contractor_doc(contractor)
    return contractor, True


def _member_row(doc, row):
    user = frappe.db.get_value("User", row.user, ["last_login", "enabled"], as_dict=True) or {}
    return {"user": row.user, "full_name": row.full_name or frappe.utils.get_fullname(row.user),
        "member_role": row.member_role, "enabled": bool(row.enabled and user.get("enabled")), "phone": row.phone,
        "invited_on": row.invited_on, "last_login": user.get("last_login"), "joined": bool(user.get("last_login")),
        "me": row.user == frappe.session.user}


def _email(user, full_name, link, contractor_name):
    company = frappe.db.get_single_value("Global Defaults", "default_company") or _("us")
    from projectit.customer_accounts import _app_note
    try:
        frappe.sendmail(recipients=[user], subject=_("Your {0} jobs app account").format(company),
            message=_("<p>Hello {0},</p><p>{1} has given you access to the Techy App for <b>{2}</b>: the jobs we give "
                "you, checking in at sites, and your pay.</p><p><a href=\"{3}\">Set your password and sign in</a></p>"
                "<p>The link works once. If it has expired, ask us for a new one.</p>").format(
                frappe.utils.escape_html(full_name), frappe.utils.escape_html(company),
                frappe.utils.escape_html(contractor_name or ""), link) + _app_note(),
            now=True)
        return True
    except Exception:
        frappe.log_error(title="Contractor invitation email could not be sent")
        return False


@frappe.whitelist(methods=["POST"])
def invite_member(contractor=None, full_name=None, email=None, member_role="Crew", phone=None):
    """Give someone an account for this contractor and email them a link to set their password (the link is also
    returned, to share another way). Managers add anyone; an owner adds their own leads and crew."""
    contractor, staff = _scope(contractor)
    full_name = ops.text(full_name, "the person's name", 140)
    email = str(email or "").strip().lower()
    if not validate_email_address(email):
        frappe.throw(_("Enter a valid email address."))
    if member_role not in MEMBER_ROLES:
        frappe.throw(_("Choose Owner, Lead or Crew."))
    if member_role == "Owner" and not staff:
        frappe.throw(_("Only we can add another owner. Ask us."), frappe.PermissionError)
    existing = frappe.db.get_value("User", email, ["name", "user_type"], as_dict=True)
    if existing and existing.user_type == "System User":
        frappe.throw(_("{0} is a staff account. Use a different email for a contractor.").format(email))
    from projectit.customer_accounts import is_customer
    if existing and is_customer(email):
        frappe.throw(_("{0} is a customer's account. Use a different email.").format(email))
    other = frappe.db.get_value(MEMBER, {"user": email, "parenttype": DOCTYPE}, "parent")
    if other:
        frappe.throw(_("{0} already belongs to a contractor.").format(email) if other != contractor
            else _("{0} is already in this contractor's people.").format(email))
    if existing:
        user = frappe.get_doc("User", email)
    else:
        first, _sep, last = full_name.partition(" ")
        user = frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "last_name": last,
            "user_type": "Website User", "send_welcome_email": 0, "enabled": 1, "mobile_no": phone or None})
        user.flags.ignore_permissions = True
        user.insert()
    user.flags.ignore_permissions = True
    user.add_roles(ROLE)
    frappe.db.set_value("User", email, "enabled", 1)
    doc = _contractor_doc(contractor, write=True)
    doc.append("members", {"user": email, "full_name": full_name, "member_role": member_role, "enabled": 1,
        "phone": phone, "invited_on": now_datetime()})
    doc.save(ignore_permissions=True)
    from projectit.customer_accounts import _invite_link
    link = _invite_link(email)
    row = next(r for r in doc.members if r.user == email)
    return {"member": _member_row(doc, row), "link": link, "emailed": _email(email, full_name, link, doc.contractor_name)}


@frappe.whitelist(methods=["POST"])
def update_member(user, contractor=None, member_role=None, enabled=None):
    """Change someone's role, or switch their account off (it is never deleted: their work stays theirs)."""
    contractor, staff = _scope(contractor)
    doc = _contractor_doc(contractor, write=True)
    row = next((r for r in doc.members if r.user == user), None)
    if not row:
        frappe.throw(_("This person is not one of this contractor's people."))
    if not staff and (row.member_role == "Owner" or row.user == frappe.session.user):
        frappe.throw(_("Ask us to change an owner's account."), frappe.PermissionError)
    if member_role is not None and member_role != row.member_role:
        if member_role not in MEMBER_ROLES or (member_role == "Owner" and not staff):
            frappe.throw(_("Only we can make someone an owner."), frappe.PermissionError)
        row.member_role = member_role
    if enabled is not None:
        row.enabled = 1 if cint(enabled) else 0
        frappe.db.set_value("User", row.user, "enabled", row.enabled)
        if not row.enabled:
            _drop_jobs(row.user, contractor)
    doc.save(ignore_permissions=True)
    return _member_row(doc, row)


def _drop_jobs(user, contractor):
    """Someone switched off is taken off their contractor's open jobs (the owner reassigns them)."""
    from frappe.desk.form.assign_to import remove
    jobs = frappe.get_all("Task", filters={"custom_contractor": contractor, "status": ["not in", ["Completed", "Cancelled"]]},
        pluck="name")
    for name in jobs:
        if frappe.db.exists("ToDo", {"reference_type": "Task", "reference_name": name, "allocated_to": user,
                "status": "Open"}):
            remove("Task", name, user, ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def resend_invite(user, contractor=None):
    contractor, staff = _scope(contractor)
    doc = _contractor_doc(contractor)
    row = next((r for r in doc.members if r.user == user), None)
    if not row or not row.enabled:
        frappe.throw(_("Switch the account on first."))
    if not staff and row.member_role == "Owner":
        frappe.throw(_("Ask us to send an owner a new link."), frappe.PermissionError)
    from projectit.customer_accounts import _invite_link
    link = _invite_link(user)
    return {"link": link, "emailed": _email(user, row.full_name or user, link, doc.contractor_name)}


# Managers: the contractors -------------------------------------------------------------------------------------

RATE_UNITS = ("Job", "Hour", "Day", "Piece", "Metre", "Square metre", "Visit", "Other")
PAY_CYCLES = ("Per job", "Weekly", "Monthly")
PURCHASES = ("Reimbursed", "Included in price")


@frappe.whitelist()
def list_contractors(search=None, include_disabled=0):
    ops.require_manager()
    filters = {} if cint(include_disabled) else {"enabled": 1}
    or_filters = None
    if search:
        q = f"%{str(search).strip()[:80]}%"
        or_filters = {"contractor_name": ["like", q], "trades": ["like", q], "supplier": ["like", q]}
    rows = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, fields=["name", "contractor_name",
        "contractor_type", "supplier", "enabled", "phone", "pay_cycle", "trades"], order_by="contractor_name asc",
        limit_page_length=0)
    names = [r.name for r in rows] or [""]
    people = {}
    for m in frappe.get_all(MEMBER, filters={"parent": ["in", names], "parenttype": DOCTYPE, "enabled": 1},
            fields=["parent", "user", "full_name", "member_role"], order_by="idx asc"):
        people.setdefault(m.parent, []).append(m)
    open_jobs = dict(frappe.db.sql("""SELECT custom_contractor, COUNT(*) FROM `tabTask` WHERE custom_contractor IN %s
        AND status NOT IN ('Completed', 'Cancelled') GROUP BY custom_contractor""", (tuple(names),)))
    from projectit import contractor_pay
    owed = contractor_pay.owed_by_contractor(names)
    for r in rows:
        r.people = people.get(r.name, [])
        r.open_jobs = open_jobs.get(r.name, 0)
        r.owed = owed.get(r.name, {"approved": 0, "billed": 0})
    return {"contractors": rows, "units": RATE_UNITS, "pay_cycles": PAY_CYCLES, "purchases": PURCHASES}


@frappe.whitelist()
def get_contractor(name):
    ops.require_manager()
    doc = _contractor_doc(name)
    jobs = frappe.get_all("Task", filters={"custom_contractor": name, "custom_work_order": 1}, fields=["name", "subject",
        "status", "custom_contractor_state", "exp_end_date", "custom_completed_at", "project"], order_by="modified desc",
        limit_page_length=30)
    projects = frappe.db.sql("""SELECT p.project, pr.project_name, a.instructions
        FROM `tabProject Allocation and Instrucions` p
        JOIN `tabTechy Contractor Allocation` a ON a.parent = p.name AND a.parenttype = 'Project Allocation and Instrucions'
        LEFT JOIN `tabProject` pr ON pr.name = p.project WHERE a.contractor = %s""", (name,), as_dict=True)
    from projectit import contractor_pay
    return {"contractor": {f: doc.get(f) for f in ("name", "contractor_name", "contractor_type", "supplier", "enabled",
            "phone", "email", "pay_cycle", "purchases", "trades", "notes", "modified")},
        "supplier_name": frappe.db.get_value("Supplier", doc.supplier, "supplier_name") if doc.supplier else None,
        "members": [_member_row(doc, r) for r in doc.members],
        "rates": [{"name": r.name, "activity": r.activity, "unit": r.unit, "rate": r.rate, "item_code": r.item_code,
            "valid_from": r.valid_from} for r in doc.rates],
        "jobs": jobs, "projects": projects, "owed": contractor_pay.owed_by_contractor([name]).get(name),
        "units": RATE_UNITS, "pay_cycles": PAY_CYCLES, "purchases": PURCHASES}


def _supplier_for(name, kind, supplier=None):
    if supplier:
        if not frappe.db.exists("Supplier", supplier):
            frappe.throw(_("Supplier {0} was not found.").format(supplier))
        return supplier
    found = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    if found:
        return found
    group = frappe.db.get_single_value("Buying Settings", "supplier_group") or frappe.db.get_value("Supplier Group",
        {"is_group": 0}, "name")
    doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": group,
        "supplier_type": "Individual" if kind == "Individual" else "Company"})
    doc.insert()  # the manager's own Supplier rights apply
    return doc.name


def _rates(values):
    values = frappe.parse_json(values) if isinstance(values, str) else (values or [])
    rows = []
    for v in values:
        activity = ops.text(v.get("activity"), "the activity", 140)
        unit = v.get("unit") or "Job"
        if unit not in RATE_UNITS:
            frappe.throw(_("Choose a unit for {0}.").format(activity))
        rate = frappe.utils.flt(v.get("rate"))
        if rate <= 0:
            frappe.throw(_("Enter a rate above zero for {0}.").format(activity))
        rows.append({"activity": activity, "unit": unit, "rate": rate, "item_code": v.get("item_code") or None,
            "valid_from": v.get("valid_from") or None})
    return rows


@frappe.whitelist(methods=["POST"])
def save_contractor(data, name=None):
    """Create or change a contractor. Without a Supplier, one with the contractor's name is found or created."""
    ops.require_manager()
    data = frappe.parse_json(data) if isinstance(data, str) else frappe._dict(data or {})
    data = frappe._dict(data)
    title = ops.text(data.contractor_name, "the contractor's name", 140)
    kind = data.contractor_type or "Individual"
    if kind not in ("Individual", "Company"):
        frappe.throw(_("Choose Individual or Company."))
    doc = _contractor_doc(name, write=True) if name else frappe.new_doc(DOCTYPE)
    if name and data.modified and str(doc.modified) != str(data.modified):
        frappe.throw(_("This contractor changed. Refresh it before saving."))
    if data.pay_cycle and data.pay_cycle not in PAY_CYCLES:
        frappe.throw(_("Choose the pay cycle."))
    if data.purchases and data.purchases not in PURCHASES:
        frappe.throw(_("Choose how materials bought on site are paid."))
    doc.update({"contractor_name": title, "contractor_type": kind,
        "supplier": _supplier_for(title, kind, data.supplier or doc.get("supplier")),
        "phone": ops.text(data.phone, "the phone number", 40, required=False),
        "email": str(data.email or "").strip() or None, "pay_cycle": data.pay_cycle or doc.get("pay_cycle") or "Monthly",
        "purchases": data.purchases or doc.get("purchases") or "Reimbursed",
        "trades": ops.text(data.trades, "skills or trades", 1000, required=False),
        "notes": ops.text(data.notes, "notes", 4000, required=False),
        "enabled": 1 if data.get("enabled", 1) in (1, "1", True, None) else 0})
    if data.get("rates") is not None:
        doc.set("rates", _rates(data.rates))
    doc.flags.ignore_permissions = True  # managers (checked above)
    doc.save() if name else doc.insert()
    return get_contractor(doc.name)


@frappe.whitelist()
def options():
    """Active contractors for the pickers on a job or project: their people and rate card."""
    ops.require_manager()
    rows = frappe.get_all(DOCTYPE, filters={"enabled": 1}, fields=["name", "contractor_name", "contractor_type",
        "purchases", "trades"], order_by="contractor_name asc", limit_page_length=0)
    names = [r.name for r in rows] or [""]
    people, rates = {}, {}
    for m in frappe.get_all(MEMBER, filters={"parent": ["in", names], "parenttype": DOCTYPE, "enabled": 1},
            fields=["parent", "user", "full_name", "member_role"], order_by="idx asc"):
        people.setdefault(m.parent, []).append(m)
    for r in frappe.get_all("Techy Contractor Rate", filters={"parent": ["in", names], "parenttype": DOCTYPE},
            fields=["parent", "activity", "unit", "rate", "item_code"], order_by="idx asc"):
        rates.setdefault(r.parent, []).append(r)
    for r in rows:
        r.people, r.rates = people.get(r.name, []), rates.get(r.name, [])
    return rows


# Managers: giving a job to a contractor ------------------------------------------------------------------------

def _job(name, for_update=True):
    doc = frappe.get_doc("Task", name, for_update=for_update)
    if not doc.get("custom_work_order") or doc.get("parent_task"):
        frappe.throw(_("{0} is not a work order.").format(name))
    return doc


def _assignees(name):
    from projectit.work_orders import _assignees as assignees
    return assignees([name])[name]


def _set_crew(doc, contractor, users):
    """Make the job's crew exactly `users` (people of this contractor); staff assignees are left alone."""
    from frappe.desk.form.assign_to import remove
    from projectit.work_orders import _assign
    people = {m.user for m in members(contractor)}
    users = frappe.parse_json(users) if isinstance(users, str) else (users or [])
    if not isinstance(users, list) or len(users) > 20:
        frappe.throw(_("Choose at most 20 people."))
    users = {str(u) for u in users if u}
    if users - people:
        frappe.throw(_("Choose people of this contractor only."))
    current = set(_assignees(doc.name))
    crew_now = {u for u in current if u in {m.user for m in members(contractor, enabled_only=False)}}
    added = sorted(users - crew_now)
    if added:
        _assign(doc, added)
        ops.notify(added, _("New job: {0}").format(doc.subject), "Task", doc.name, "Assignment")
    for user in crew_now - users:
        remove("Task", doc.name, user, ignore_permissions=True)
    return added


@frappe.whitelist(methods=["POST"])
def give_job(work_order, contractor=None, crew=None, purchases=None):
    """Offer a job to a contractor (or take it back with no contractor). Its pay is set in contractor_pay."""
    ops.require_manager()
    doc = _job(work_order)
    if doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("This job is closed."))
    before = doc.get("custom_contractor")
    if before and before != contractor:
        # Taking it back: their crew comes off the job and agreed pay that was never earned is cancelled.
        _set_crew(doc, before, [])
        from projectit import contractor_pay
        contractor_pay.cancel_draft(doc.name)
        doc.add_comment("Info", escape(_("Taken back from {0}.").format(
            frappe.db.get_value(DOCTYPE, before, "contractor_name"))))
    if not contractor:
        frappe.db.set_value("Task", doc.name, {"custom_contractor": None, "custom_contractor_state": None,
            "custom_contractor_note": None, "custom_contractor_purchases": None})
        return job_contractor(doc.name)
    con = _contractor_doc(contractor)
    if not con.enabled:
        frappe.throw(_("{0} is not active.").format(con.contractor_name))
    if purchases and purchases not in PURCHASES:
        frappe.throw(_("Choose how materials bought on site are paid."))
    if before != contractor:
        frappe.db.set_value("Task", doc.name, {"custom_contractor": contractor, "custom_contractor_state": "Offered",
            "custom_contractor_note": None, "custom_contractor_purchases": purchases or con.purchases or "Reimbursed"})
        doc.add_comment("Info", escape(_("Offered to {0}.").format(con.contractor_name)))
        ops.notify(job_runners(contractor), _("Job offered: {0}").format(doc.subject), "Task", doc.name, "Assignment")
    elif purchases:
        frappe.db.set_value("Task", doc.name, "custom_contractor_purchases", purchases)
    if crew is not None:
        _set_crew(doc, contractor, crew)
    return job_contractor(doc.name)


def job_contractor(work_order):
    """The contractor part of a job, for its page (managers, and the contractor's owner and leads)."""
    row = frappe.db.get_value("Task", work_order, ["name", "custom_contractor", "custom_contractor_state",
        "custom_contractor_note", "custom_contractor_purchases", "status"], as_dict=True)
    if not row or not row.custom_contractor:
        return {"contractor": None}
    con = frappe.db.get_value(DOCTYPE, row.custom_contractor, ["name", "contractor_name", "contractor_type"], as_dict=True)
    people = members(row.custom_contractor)
    on_job = set(_assignees(work_order))
    return {"contractor": con, "state": row.custom_contractor_state, "note": row.custom_contractor_note,
        "purchases": row.custom_contractor_purchases or "Reimbursed",
        "people": [{"user": m.user, "full_name": m.full_name, "member_role": m.member_role, "on_job": m.user in on_job}
            for m in people]}


# The contractor's app ------------------------------------------------------------------------------------------

JOB_FIELDS = ["name", "subject", "status", "priority", "exp_end_date", "custom_work_category", "custom_equipment",
    "custom_customer", "project", "custom_contractor", "custom_contractor_state", "custom_started_at",
    "custom_completed_at", "custom_review_requested", "modified"]


@frappe.whitelist()
def me():
    """Who I am in the contractor app, and what needs me."""
    member = require_member()
    jobs = _my_jobs(member)
    from projectit import site_visits
    return {"user": frappe.session.user, "full_name": frappe.utils.get_fullname(), "contractor": member.contractor,
        "contractor_name": member.contractor_name, "contractor_type": member.contractor_type,
        "member_role": member.member_role, "runs_jobs": runs_jobs(member), "sees_pay": sees_pay(member),
        "counts": {"offered": sum(1 for j in jobs if j.custom_contractor_state == "Offered"),
            "active": sum(1 for j in jobs if j.custom_contractor_state == "Accepted" and j.status not in ("Completed", "Cancelled"))},
        "visit": site_visits.open_visit(), "support_phone": frappe.db.get_single_value("Techy Ops Settings", "support_phone")}


def _my_jobs(member, limit=0):
    return frappe.get_list("Task", filters={"custom_work_order": 1, "is_template": 0, "parent_task": ["is", "not set"],
        "custom_contractor": member.contractor}, fields=JOB_FIELDS, order_by="modified desc", limit_page_length=limit)


@frappe.whitelist()
def jobs(view="active"):
    """My jobs: offered (waiting for an answer), active, or done. The list is narrowed by permissions: crew see the
    jobs they are on, the owner and leads see all their contractor's jobs."""
    member = require_member()
    rows = _my_jobs(member)
    if view == "offered":
        rows = [r for r in rows if r.custom_contractor_state == "Offered"]
    elif view == "done":
        rows = [r for r in rows if r.custom_contractor_state == "Accepted" and r.status in ("Completed", "Cancelled")
            or r.custom_contractor_state == "Declined"][:100]
    else:
        rows = [r for r in rows if r.custom_contractor_state == "Accepted" and r.status not in ("Completed", "Cancelled")]
    from projectit import equipment as installed
    from projectit.work_orders import _assignees as assignees
    people = assignees([r.name for r in rows])
    machines = installed.labels(r.custom_equipment for r in rows)
    customers = dict(frappe.get_all("Customer", filters={"name": ["in", [r.custom_customer for r in rows if r.custom_customer] or [""]]},
        fields=["name", "customer_name"], as_list=True))
    projects = dict(frappe.get_all("Project", filters={"name": ["in", [r.project for r in rows if r.project] or [""]]},
        fields=["name", "project_name"], as_list=True))
    from projectit import contractor_pay
    pay = contractor_pay.job_totals([r.name for r in rows]) if sees_pay(member) else {}
    for r in rows:
        r.assignees = ops.people(people[r.name])
        r.equipment = machines.get(r.custom_equipment)
        r.customer_name = customers.get(r.custom_customer)
        r.project_name = projects.get(r.project)
        r.mine = frappe.session.user in people[r.name]
        if sees_pay(member):
            r.pay = pay.get(r.name)
    return {"jobs": rows, "member_role": member.member_role}


@frappe.whitelist(methods=["POST"])
def respond(work_order, accept, note=None):
    """The owner or a lead accepts or declines a job offered to them."""
    member = require_member(RUN_JOBS)
    doc = _job(work_order)
    if doc.get("custom_contractor") != member.contractor:
        frappe.throw(_("This job is not offered to you."), frappe.PermissionError)
    if doc.get("custom_contractor_state") != "Offered":
        frappe.throw(_("This job was already answered."))
    note = ops.text(note, "the reason", 1000, required=not cint(accept))
    from projectit.meters import _managers
    if cint(accept):
        frappe.db.set_value("Task", doc.name, {"custom_contractor_state": "Accepted", "custom_contractor_note": note or None})
        doc.add_comment("Info", escape(_("{0} accepted the job for {1}.").format(frappe.utils.get_fullname(),
            member.contractor_name)))
        if member.contractor_type == "Individual" and not _assignees(doc.name):
            _set_crew(doc, member.contractor, [frappe.session.user])
        ops.notify(_managers(), _("Accepted: {0}").format(doc.subject), "Task", doc.name)
    else:
        frappe.db.set_value("Task", doc.name, {"custom_contractor_state": "Declined", "custom_contractor_note": note})
        _set_crew(doc, member.contractor, [])
        doc.add_comment("Info", escape(_("{0} declined the job for {1}: {2}").format(frappe.utils.get_fullname(),
            member.contractor_name, note)))
        ops.notify(_managers(), _("Declined: {0}").format(doc.subject), "Task", doc.name)
    return job_contractor(doc.name)


@frappe.whitelist(methods=["POST"])
def assign_crew(work_order, users):
    """The owner or a lead chooses which of their people do an accepted job."""
    member = require_member(RUN_JOBS)
    doc = _job(work_order)
    if doc.get("custom_contractor") != member.contractor:
        frappe.throw(_("This job is not yours."), frappe.PermissionError)
    if doc.get("custom_contractor_state") != "Accepted":
        frappe.throw(_("Accept the job first."))
    if doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("This job is closed."))
    _set_crew(doc, member.contractor, users)
    return job_contractor(doc.name)


@frappe.whitelist()
def job_people(work_order):
    """The contractor part of a job, for its page: managers, and the job's own contractor's people."""
    member = membership()
    if member:
        doc = _job(work_order, for_update=False)
        if not sees_job(doc):
            frappe.throw(_("This job is not yours."), frappe.PermissionError)
        info = job_contractor(work_order)
        if not runs_jobs(member):
            info["people"] = [p for p in info["people"] if p["on_job"]]
        return info
    ops.require_manager()
    return job_contractor(work_order)


@frappe.whitelist()
def crew():
    """My contractor's people (owner and leads)."""
    member = require_member(RUN_JOBS)
    doc = _contractor_doc(member.contractor)
    return {"members": [_member_row(doc, r) for r in doc.members], "can_manage": sees_pay(member)}


@frappe.whitelist()
def my_projects():
    """Projects given to my contractor, with the site instructions (owner and leads), or that my jobs belong to."""
    member = require_member()
    names = sorted(projects_for(frappe.session.user))
    if not names:
        return []
    rows = frappe.get_all("Project", filters={"name": ["in", names]}, fields=["name", "project_name", "status",
        "expected_end_date", "customer"], order_by="project_name asc")
    notes = {r.project: r for r in frappe.db.sql("""SELECT p.project, p.work_instruction, a.instructions
        FROM `tabProject Allocation and Instrucions` p
        LEFT JOIN `tabTechy Contractor Allocation` a ON a.parent = p.name AND a.contractor = %s
            AND a.parenttype = 'Project Allocation and Instrucions'
        WHERE p.project IN %s""", (member.contractor, tuple(names)), as_dict=True)}
    from frappe.utils import strip_html
    for r in rows:
        n = notes.get(r.name) or {}
        r.work_instruction = strip_html(n.get("work_instruction") or "")
        r.instructions = strip_html(n.get("instructions") or "")
        r.customer_name = frappe.db.get_value("Customer", r.customer, "customer_name") if r.customer else None
    return rows
