"""Work requests on native ERPNext Issues (custom_maintenance_request = 1).

Staff, and optionally guests scanning an asset QR code, report problems; managers approve
a request into a work order or decline it. Completing the work order resolves the Issue.
"""
from html import escape

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, validate_email_address

from projectit import equipment as installed, ops, work_orders

FIELDS = ["name", "subject", "status", "priority", "raised_by", "opening_date", "custom_asset", "custom_location",
    "custom_equipment", "custom_work_order", "owner", "creation", "modified"]


def _state(row):
    closed = row.get("status") in ("Resolved", "Closed")
    if row.get("custom_work_order"):
        return "Done" if closed else "Approved"
    return "Declined" if closed else "Pending"


def _issue(subject, description, asset, location, raised_by, priority=None, equipment=None):
    subject = ops.text(subject, "a title", 140)
    description = ops.text(description, "a description", 4000, required=False)
    if asset and not frappe.db.exists("Asset", asset):
        frappe.throw(_("Asset {0} was not found.").format(asset))
    if asset and not location:
        location = frappe.db.get_value("Asset", asset, "location")
    if location and not frappe.db.exists("Location", location):
        frappe.throw(_("Location {0} was not found.").format(location))
    customer = None
    if equipment:
        customer = frappe.db.get_value("Techy Equipment", {"name": equipment, "status": ["not in",
            list(installed.RETIRED)]}, "customer")
        if not customer:
            frappe.throw(_("Equipment {0} was not found.").format(equipment))
    doc = frappe.get_doc({"doctype": "Issue", "subject": subject, "description": escape(description),
        "raised_by": raised_by, "custom_maintenance_request": 1, "custom_asset": asset or None,
        "custom_location": location or None, "custom_equipment": equipment or None, "customer": customer,
        "priority": priority if priority and frappe.db.exists("Issue Priority", priority) else None})
    # Reporting a problem is open to all staff (and, when enabled, guests); Issue roles are not required.
    doc.insert(ignore_permissions=True)
    managers = frappe.get_all("Has Role", filters={"role": ["in", ["Maintenance Manager"]], "parenttype": "User"},
        pluck="parent", limit_page_length=50)
    ops.notify(managers, _("New work request: {0}").format(subject), "Issue", doc.name)
    return doc


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def submit_request(subject, description=None, asset=None, location=None, priority=None, photo=None, equipment=None):
    ops.system_user()
    doc = _issue(subject, description, asset, location, frappe.session.user, priority, equipment)
    if photo:
        ops.save_photo("Issue", doc.name, photo, "request")
    return {"name": doc.name}


@frappe.whitelist(allow_guest=True)
def request_context(asset=None, equipment=None):
    """What the public QR request page may show: an asset's display name, or a machine's model and site."""
    allowed = frappe.session.user != "Guest" or ops.settings().allow_guest_requests
    if not allowed or not (asset or equipment):
        return {"allowed": allowed, "asset": None, "equipment": None}
    row = machine = None
    if asset:
        row = frappe.db.get_value("Asset", {"name": asset, "docstatus": ["<", 2]}, ["name", "asset_name"], as_dict=True)
    if equipment:
        # The sticker sits on the machine at the customer's site, so its model and site label are not secret.
        machine = frappe.db.get_value("Techy Equipment", {"name": equipment, "status": ["not in",
            list(installed.RETIRED)]}, ["name", "equipment_name", "site"], as_dict=True)
    return {"allowed": True, "asset": row, "equipment": machine}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=3600)
def submit_guest_request(subject, email, description=None, asset=None, full_name=None, equipment=None):
    if not ops.settings().allow_guest_requests:
        frappe.throw(_("Public work requests are disabled."), frappe.PermissionError)
    email = validate_email_address(ops.text(email, "an email address", 140), throw=True)
    name = ops.text(full_name, "your name", 140, required=False)
    details = ops.text(description, "a description", 3800, required=False)
    if name:
        details = f"{details}\n\n{_('Reported by')}: {name}".strip()
    doc = _issue(subject, details, asset, None, email, equipment=equipment)
    return {"name": doc.name}


@frappe.whitelist()
def list_requests(state=None, start=0):
    ops.system_user()
    filters = {"custom_maintenance_request": 1}
    if state == "Pending":
        filters.update({"custom_work_order": ["is", "not set"], "status": ["not in", ["Resolved", "Closed"]]})
    elif state == "Approved":
        filters.update({"custom_work_order": ["is", "set"], "status": ["not in", ["Resolved", "Closed"]]})
    elif state == "Declined":
        filters.update({"custom_work_order": ["is", "not set"], "status": ["in", ["Resolved", "Closed"]]})
    elif state == "Done":
        filters.update({"custom_work_order": ["is", "set"], "status": ["in", ["Resolved", "Closed"]]})
    if not ops.manager():
        filters["raised_by"] = frappe.session.user
    start = max(0, cint(start))
    # Managers review every request; staff see only requests they raised.
    rows = frappe.get_all("Issue", filters=filters, fields=FIELDS, order_by="creation desc",
        limit_start=start, limit_page_length=51)
    labels = ops.asset_names(row.custom_asset for row in rows)
    machines = installed.labels(row.custom_equipment for row in rows)
    for row in rows:
        row.state = _state(row)
        row.equipment = machines.get(row.custom_equipment)
        row.raised_by_name = frappe.utils.get_fullname(row.raised_by) if row.raised_by else ""
        row.asset_name = labels.get(row.custom_asset)
    return {"requests": rows[:50], "has_more": len(rows) > 50, "manager": ops.manager()}


def _request(name, manage=False):
    ops.system_user()
    if manage:
        ops.require_manager()
    doc = frappe.get_doc("Issue", name)
    if not doc.custom_maintenance_request:
        frappe.throw(_("{0} is not a work request.").format(name))
    if not ops.manager() and doc.raised_by != frappe.session.user:
        frappe.throw(_("You can only view requests you raised."), frappe.PermissionError)
    return doc


@frappe.whitelist()
def get_request(name):
    doc = _request(name)
    comments = frappe.get_all("Comment", filters={"reference_doctype": "Issue", "reference_name": doc.name,
        "comment_type": ["in", ["Comment", "Info"]]}, fields=["name", "content", "comment_by", "creation"],
        order_by="creation asc", limit_page_length=100)
    for comment in comments:
        comment.content = ops.plain(comment.content)
    row = {field: doc.get(field) for field in FIELDS}
    row["state"] = _state(row)
    row["raised_by_name"] = frappe.utils.get_fullname(doc.raised_by) if doc.raised_by else ""
    asset_name = frappe.db.get_value("Asset", doc.custom_asset, "asset_name") if doc.custom_asset else None
    return {"request": row, "description": ops.plain(doc.description), "asset_name": asset_name,
        "equipment": installed.summary(doc.get("custom_equipment")), "comments": comments, "files": ops.files("Issue", doc.name), "manager": ops.manager()}


@frappe.whitelist(methods=["POST"])
def approve_request(name, assignees=None, priority="Medium", category="Corrective", due_date=None, steps=None,
        project=None, procedure=None):
    doc = _request(name, manage=True)
    if doc.custom_work_order or doc.status in ("Resolved", "Closed"):
        frappe.throw(_("This request has already been handled."))
    work_order = work_orders.create(doc.subject, ops.plain(doc.description), priority, category, doc.custom_asset,
        doc.custom_location, assignees, due_date, steps, project, request=doc.name, procedure=procedure,
        equipment=doc.get("custom_equipment"))
    for file in ops.files("Issue", doc.name):
        # Copy the bytes: reusing a private file_url would require read access to the source Issue.
        frappe.get_doc({"doctype": "File", "file_name": file.file_name, "is_private": 1,
            "content": frappe.get_doc("File", file.name).get_content(), "attached_to_doctype": "Task",
            "attached_to_name": work_order.name}).insert(ignore_permissions=True)
    doc.custom_work_order = work_order.name
    doc.flags.ignore_permissions = True
    doc.save()
    doc.add_comment("Info", escape(_("Approved as work order {0}.").format(work_order.name)))
    requester = frappe.db.get_value("User", {"name": doc.raised_by, "enabled": 1})
    ops.notify([requester], _("Your request was approved: {0}").format(doc.subject), "Issue", doc.name)
    return {"name": doc.name, "work_order": work_order.name}


@frappe.whitelist(methods=["POST"])
def decline_request(name, reason):
    doc = _request(name, manage=True)
    if doc.custom_work_order or doc.status in ("Resolved", "Closed"):
        frappe.throw(_("This request has already been handled."))
    reason = ops.text(reason, "a reason", 1000)
    doc.status = "Closed"
    doc.flags.ignore_permissions = True
    doc.save()
    doc.add_comment("Comment", escape(_("Declined: {0}").format(reason)))
    requester = frappe.db.get_value("User", {"name": doc.raised_by, "enabled": 1})
    ops.notify([requester], _("Your request was declined: {0}").format(doc.subject), "Issue", doc.name)
    return {"name": doc.name}
