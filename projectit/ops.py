"""Shared helpers for Techy Ops: work orders, requests, assets/PM and team chat."""
import base64
import binascii
import io
import re
from html import escape, unescape

import frappe
from frappe import _
from frappe.utils import cint, strip_html

MANAGER_ROLES = {"System Manager", "Projects Manager", "Maintenance Manager"}
MENTION = re.compile(r"(?<![\w.])@([\w.+-]+@[\w-]+(?:\.[\w-]+)+)")


def login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please sign in."), frappe.PermissionError)


def system_user():
    """Chat and work orders are for staff (System Users), not website/portal users."""
    login()
    if frappe.get_cached_value("User", frappe.session.user, "user_type") != "System User":
        frappe.throw(_("Techy Ops is available to staff accounts only."), frappe.PermissionError)


def manager():
    return frappe.session.user != "Guest" and bool(set(frappe.get_roles()) & MANAGER_ROLES)


def require_manager():
    login()
    if not manager():
        frappe.throw(_("Maintenance or project manager access is required."), frappe.PermissionError)


def require_asset_access():
    """Asset/PM screens: managers, Maintenance Users, or anyone with native Asset read.

    ERPNext gives the maintenance roles no Asset access, so Ops serves a read-only,
    non-financial projection (see maintenance.ASSET_FIELDS) instead of the full documents.
    """
    system_user()
    if not (manager() or "Maintenance User" in frappe.get_roles() or frappe.has_permission("Asset", "read")):
        frappe.throw(_("Ask an administrator for the Maintenance User role to view assets."), frappe.PermissionError)


PAGE_SIZES = (25, 50, 100)


def page_size(page_length, default):
    """The requested rows per page (one of PAGE_SIZES), or the endpoint's old default for older callers."""
    size = cint(page_length)
    return size if size in PAGE_SIZES else default


def paged(doctype, filters=None, or_filters=None, order_by="modified desc", start=0, page_length=25, fields=None,
        reader=None, keep=None):
    """One page of rows plus the total that match, for numbered pages.

    `reader` is frappe.get_list (permission-aware) or frappe.get_all; both queries go through it. `keep`,
    when given, filters candidate rows in Python (e.g. a computed coverage) before counting; it receives
    rows with the `fields` it needs, so pass those fields as fields too."""
    reader = reader or frappe.get_all
    start = max(0, cint(start))
    if keep:
        rows = [r for r in reader(doctype, filters=filters, or_filters=or_filters, fields=fields, order_by=order_by,
            limit_page_length=0) if keep(r)]
        return rows[start:start + page_length], len(rows)
    names = reader(doctype, filters=filters, or_filters=or_filters, pluck="name", order_by=order_by, limit_page_length=0)
    page = names[start:start + page_length]
    rows = reader(doctype, filters={"name": ["in", page]}, fields=fields, limit_page_length=0) if page else []
    order = {name: i for i, name in enumerate(page)}
    rows.sort(key=lambda r: order.get(r.name, 0))
    return rows, len(names)


def settings():
    doc = frappe.get_cached_doc("Techy Ops Settings")
    lead = 3 if doc.pm_lead_days is None else int(doc.pm_lead_days)
    return frappe._dict(allow_guest_requests=bool(doc.allow_guest_requests), pm_lead_days=max(0, lead))


def text(value, label, maximum, required=True):
    value = str(value or "").strip()
    if (required and not value) or len(value) > maximum:
        frappe.throw(_("Enter {0} of up to {1} characters.").format(_(label), maximum))
    return value


def plain(html):
    """Comments are stored escaped; return them as plain text for Vue to escape again."""
    return unescape(strip_html(html or ""))


def active_users(users):
    users = frappe.parse_json(users) if isinstance(users, str) else (users or [])
    if not isinstance(users, list) or len(users) > 20:
        frappe.throw(_("Choose at most 20 people."))
    users = list(dict.fromkeys(str(u) for u in users if u))
    if users:
        found = frappe.get_all("User", filters={"name": ["in", users], "enabled": 1,
            "user_type": "System User"}, pluck="name")
        if len(found) != len(users):
            frappe.throw(_("Choose active staff users only."))
    return users


def asset_names(names):
    """Display names for Asset IDs (a read-only label lookup for rows the caller already returns)."""
    names = list({n for n in names if n})
    return dict(frappe.get_all("Asset", filters={"name": ["in", names]}, fields=["name", "asset_name"],
        as_list=True)) if names else {}


def people(users):
    return [{"user": u, "full_name": frappe.utils.get_fullname(u),
        "image": frappe.get_cached_value("User", u, "user_image")} for u in users]


def mentions(content, allowed=None):
    """Users @mentioned by email in content: limited to `allowed`, else to active staff."""
    found = [u for u in dict.fromkeys(MENTION.findall(content)) if u != frappe.session.user]
    if allowed is not None:
        return [u for u in found if u in allowed]
    return frappe.get_all("User", filters={"name": ["in", found], "enabled": 1, "user_type": "System User"},
        pluck="name") if found else []


def notify(users, subject, doctype, name, kind="Alert"):
    from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
    users = [u for u in dict.fromkeys(users or []) if u and u not in ("Guest", frappe.session.user)]
    if users:
        enqueue_create_notification(users, {"type": kind, "document_type": doctype,
            "document_name": name, "subject": escape(subject), "from_user": frappe.session.user})


def push(users, event, message):
    """Realtime fan-out to each user's private socket.io room once the transaction commits."""
    for user in dict.fromkeys(users or []):
        if user and user != "Guest":
            frappe.publish_realtime(event, message, user=user, after_commit=True)


def save_photo(doctype, name, content, prefix):
    from PIL import Image
    if not isinstance(content, str) or len(content) > 14000000:
        frappe.throw(_("Choose a photo smaller than 10 MB."))
    try:
        data = base64.b64decode(content, validate=True)
        with Image.open(io.BytesIO(data)) as photo:
            if photo.format not in ("JPEG", "PNG"):
                raise ValueError
            extension = "jpg" if photo.format == "JPEG" else "png"
            photo.verify()
    except (ValueError, SyntaxError, binascii.Error, OSError):  # Pillow raises SyntaxError for corrupt images.
        frappe.throw(_("Choose a valid JPEG or PNG photo."))
    return frappe.get_doc({"doctype": "File", "file_name": f"{prefix}-{frappe.generate_hash(length=12)}.{extension}",
        "content": data, "is_private": 1, "attached_to_doctype": doctype, "attached_to_name": name}).insert()


def files(doctype, name):
    return frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": name},
        fields=["name", "file_name", "file_url", "creation"], order_by="creation desc", limit_page_length=50)


@frappe.whitelist()
def bootstrap():
    """Session details for the Ops shell: identity, role, unread chat and socket.io endpoint."""
    system_user()
    from projectit.chat import unread_total
    from projectit.work_orders import summary
    from projectit import billing, parts
    from projectit.api import my_apps
    user = frappe.session.user
    pending = frappe.db.count("Issue", {"custom_maintenance_request": 1, "custom_work_order": ["is", "not set"],
        "status": ["not in", ["Resolved", "Closed"]]}) if manager() else 0
    return {"user": user, "full_name": frappe.utils.get_fullname(user),
        "image": frappe.get_cached_value("User", user, "user_image"), "manager": manager(),
        "sitename": frappe.local.site, "socketio_port": frappe.conf.socketio_port or 9000,
        "unread": unread_total(), "guest_requests": settings().allow_guest_requests,
        "counts": {"work_orders": summary()["open"] if frappe.has_permission("Task", "read") else 0,
            "pending_requests": pending, "pending_parts": parts.pending_count()},
        "can_approve_parts": parts.can_approve(), "can_invoice": billing.can_invoice(),
        "ops_access": "Ops" in my_apps()}


@frappe.whitelist()
def search_users(txt=""):
    system_user()
    txt = str(txt or "").strip()[:60]
    or_filters = {"full_name": ["like", f"%{txt}%"], "name": ["like", f"%{txt}%"]} if txt else None
    return frappe.get_all("User", filters={"enabled": 1, "user_type": "System User",
        "name": ["not in", ["Administrator", "Guest"]]}, or_filters=or_filters,
        fields=["name as user", "full_name", "user_image as image"], order_by="full_name asc", limit_page_length=20)
