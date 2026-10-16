"""Customer ratings: after a customer job is completed, the customer rates the visit (1 to 5 stars and a comment).

Each completed customer job gets a private link (a random key on the job), sent with the service report email
and shown on the job page so staff can share it (WhatsApp, SMS). The link opens a public page that needs no
sign-in; the key is what lets the customer rate that one job. A rating can be changed for 30 days after the job
was completed. Each rating is noted on the job's timeline and told to the technicians; a low one (1 or 2 stars)
is also told to the managers. Ratings feed the technician scorecard.
"""
import hmac
from html import escape

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, get_datetime, now_datetime

from projectit import ops

OPEN_DAYS = 30
LOW = 2


def _key(doc):
    """The job's rating key, made the first time it is needed."""
    key = doc.get("custom_rating_key")
    if not key:
        key = frappe.generate_hash(length=24)
        frappe.db.set_value("Task", doc.name, "custom_rating_key", key, update_modified=False)
        doc.custom_rating_key = key
    return key


def link(doc):
    return f"{frappe.utils.get_url()}/techy-app/rate?job={doc.name}&key={_key(doc)}"


def rateable(doc):
    return bool(doc.get("custom_work_order") and doc.get("custom_customer") and doc.status == "Completed")


def still_open(doc):
    done = doc.get("custom_completed_at") or doc.get("modified")
    return (now_datetime() - get_datetime(done)).days < OPEN_DAYS


def summary(doc):
    """The job page's rating card."""
    if not doc.get("custom_customer"):
        return None
    shareable = rateable(doc) and still_open(doc)
    return {"rating": cint(doc.get("custom_rating")) or None, "comment": doc.get("custom_rating_comment") or "",
        "rated_on": doc.get("custom_rated_on"), "can_share": shareable, "completed": doc.status == "Completed"}


def on_completed(doc):
    """Give a completed customer job its rating key, so the report email can carry the link."""
    if rateable(doc):
        _key(doc)


@frappe.whitelist(methods=["POST"])
def share_link(name):
    """Staff on the job copy the customer's rating link."""
    ops.system_user()
    from projectit import work_orders
    doc = work_orders._work_order(name)
    if not rateable(doc):
        frappe.throw(_("Customers rate a job once it is completed."))
    if not still_open(doc):
        frappe.throw(_("Ratings close {0} days after the job is completed.").format(OPEN_DAYS))
    return {"link": link(doc)}


def _job(job, key):
    """The job a customer's link points to; the same answer for a wrong key and a missing job."""
    row = frappe.db.get_value("Task", str(job or "")[:140], ["name", "subject", "status", "custom_work_order",
        "custom_customer", "custom_rating_key", "custom_completed_at", "modified", "custom_equipment", "custom_rating",
        "custom_rating_comment", "custom_rated_on", "company"], as_dict=True) if job else None
    if not row or not row.custom_rating_key or not key or not hmac.compare_digest(str(row.custom_rating_key), str(key)) \
            or not rateable(row):
        frappe.throw(_("This rating link is not valid. Ask us for a new one."), frappe.PermissionError)
    return row


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=3600)
def info(job, key):
    """What the rating page shows the customer."""
    row = _job(job, key)
    from projectit.work_orders import _assignees
    people = [frappe.utils.get_fullname(u).split(" ")[0] for u in _assignees([row.name])[row.name]]
    machine = frappe.db.get_value("Techy Equipment", row.custom_equipment, ["equipment_name", "site"], as_dict=True) \
        if row.custom_equipment else None
    company = row.company or frappe.db.get_single_value("Global Defaults", "default_company")
    return {"job": row.name, "subject": row.subject, "completed": row.custom_completed_at or row.modified,
        "company": company, "technicians": people, "machine": machine, "rating": cint(row.custom_rating) or None,
        "comment": row.custom_rating_comment or "", "open": still_open(row)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def submit(job, key, rating, comment=None):
    row = _job(job, key)
    if not still_open(row):
        frappe.throw(_("Ratings for this visit have closed. Thank you."))
    stars = cint(rating)
    if not 1 <= stars <= 5:
        frappe.throw(_("Choose from 1 to 5 stars."))
    comment = ops.text(comment, "a comment", 1000, required=False)
    changed = bool(row.custom_rating)
    frappe.db.set_value("Task", row.name, {"custom_rating": stars, "custom_rating_comment": comment or None,
        "custom_rated_on": now_datetime()}, update_modified=False)
    note = _("The customer {0} the visit {1} out of 5.").format(_("changed their rating to") if changed else _("rated"), stars)
    if comment:
        note += " " + _("Comment: {0}").format(comment)
    frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Task", "reference_name": row.name,
        "content": escape(note), "comment_email": "Guest", "comment_by": _("Customer")}).insert(ignore_permissions=True)
    from projectit.work_orders import _assignees
    people = _assignees([row.name])[row.name]
    if stars <= LOW:
        from projectit.meters import _managers
        people = list(people) + _managers()
    ops.notify(people, _("Customer rating {0}/5: {1}").format(stars, row.subject), "Task", row.name)
    return {"rating": stars, "comment": comment}
