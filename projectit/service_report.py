"""Customer service reports: a PDF of what was done on a job, for the customer.

The report shows the company letter head, the customer, site and machine, the job and its technicians, the
work done (custom_work_summary, written for the customer), checklist answers and readings, meter readings,
parts fitted with who pays (never prices; the invoice has those), labour hours, photos, the customer's
signature and when the next service is due.

Anyone who can see a job can preview its report. Sending is outward-facing: whoever can work on the job may
email it to the customer's own addresses on file; managers may add other recipients. Emails go through
ERPNext (a Communication on the Task), so they appear on the job's timeline in Desk. A setting can email
the report automatically when a customer job is completed. Invoicing attaches each job's report to the
draft Sales Invoice.
"""
import base64
import io
import re
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, flt, format_datetime, getdate, nowdate, validate_email_address

from projectit import ops

PHOTO_LIMIT = 8
PHOTO_SIZE = 900
BILLING_LABELS = {"Warranty": _("Covered by warranty"), "Contract": _("Covered by contract"),
    "Chargeable": _("Chargeable"), "Internal": _("Included")}
LABOUR_LABELS = {"Included": _("Included in cover"), "Chargeable": _("Chargeable"), "No charge": _("No charge")}


def _job(name):
    from projectit import work_orders
    return work_orders._work_order(name)


def can_send(doc):
    return ops.manager() or bool(frappe.has_permission("Task", "write", doc=doc))


def customer_emails(customer):
    """The customer's own email addresses: the customer record and its contacts."""
    if not customer:
        return []
    emails = [frappe.db.get_value("Customer", customer, "email_id")]
    contacts = frappe.get_all("Dynamic Link", filters={"link_doctype": "Customer", "link_name": customer,
        "parenttype": "Contact"}, pluck="parent")
    if contacts:
        emails += frappe.get_all("Contact Email", filters={"parent": ["in", contacts], "parenttype": "Contact"},
            pluck="email_id")
        emails += frappe.get_all("Contact", filters={"name": ["in", contacts]}, pluck="email_id")
    return list(dict.fromkeys(e.strip().lower() for e in emails if e and "@" in e))


def last_sent(name):
    return frappe.get_all("Communication", filters={"reference_doctype": "Task", "reference_name": name,
        "sent_or_received": "Sent", "communication_medium": "Email", "subject": ["like", "Service report%"]},
        fields=["name", "recipients", "creation", "sender_full_name"], order_by="creation desc", limit_page_length=1)


def summary(doc, can_write):
    """The job page's report card."""
    sent = last_sent(doc.name)
    customer = doc.get("custom_customer")
    allowed = bool(customer) and can_send(doc)
    return {"work_summary": doc.get("custom_work_summary") or "", "can_edit_summary": bool(can_write) or ops.manager(),
        "customer": customer, "can_email": allowed, "emails": customer_emails(customer) if allowed else [],
        "can_add_recipients": ops.manager(), "last_sent": sent[0] if sent else None}


# Content -------------------------------------------------------------------------------------------------------

def _image(url, size=PHOTO_SIZE):
    """A file as a data URI the PDF engine can embed (private files need no login this way)."""
    from PIL import Image, ImageOps
    name = frappe.db.get_value("File", {"file_url": url}, "name")
    if not name:
        return None
    try:
        content = frappe.get_doc("File", name).get_content()
        with Image.open(io.BytesIO(content)) as photo:
            photo = ImageOps.exif_transpose(photo)
            signature = photo.mode in ("RGBA", "LA", "P")
            photo.thumbnail((size, size))
            out = io.BytesIO()
            if signature:
                photo.convert("RGBA").save(out, format="PNG")
                kind = "png"
            else:
                photo.convert("RGB").save(out, format="JPEG", quality=72)
                kind = "jpeg"
        return f"data:image/{kind};base64,{base64.b64encode(out.getvalue()).decode()}"
    except Exception:
        return None


def _answer(step):
    value = step.get("value") or ""
    kind = step.get("field_type")
    if kind == "Checkbox":
        return _("Done") if value else "—"
    if kind == "Number" and value:
        return f"{value} {step.get('unit') or ''}".strip()
    return value or "—"


def _day(value):
    return getdate(value).strftime("%d %b %Y") if value else ""


def _company(job=None, title=None):
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults",
        "default_company")
    row = frappe.db.get_value("Company", company, ["name", "company_logo", "phone_no", "email", "website"],
        as_dict=True) if company else None
    head = frappe.db.get_value("Letter Head", {"is_default": 1, "disabled": 0}, ["content", "footer"], as_dict=True)
    logo = row.company_logo if row else None
    return {"name": company, "logo": logo, "phone": row.phone_no if row else None,
        "email": row.email if row else None, "website": row.website if row else None,
        "letter_head": _letter_head(head.content if head else None, company, logo, job, title),
        "letter_foot": _letter_head(head.footer if head else None, company, logo, job, title)}


def _letter_head(html, company, logo, job=None, title=None):
    """A letter head is a Jinja template (ERPNext fills in the company and its logo when printing)."""
    if not html:
        return None
    try:
        return frappe.render_template(html, {"company": company, "company_logo": logo or "",
            "doc": frappe._dict(company=company, doctype=title or _("Service report"), name=job or "")})
    except Exception:
        frappe.log_error(title="Techy Ops: service report letter head could not be rendered")
        return None


LOCAL_IMAGE = re.compile(r'src="((?:https?://[^"/]+)?/(?:private/)?files/[^"]+)"')


def _inline_images(html):
    """Embed the site's own images, so the PDF engine never has to fetch them over the network."""
    def swap(match):
        url = match.group(1)
        path = url[url.index("/files/") - (8 if "/private/files/" in url else 0):] if "/files/" in url else url
        data = _image(path, 600)
        return f'src="{data}"' if data else 'src=""'
    return LOCAL_IMAGE.sub(swap, html)


def _next_service(equipment, meters):
    rows = []
    if equipment and equipment.get("contract"):
        visit = frappe.db.get_value("Techy Contract Equipment", {"parent": equipment["contract"]["name"],
            "parenttype": "Techy Service Contract", "equipment": equipment["name"]}, "next_visit")
        if visit and getdate(visit) >= getdate(nowdate()):
            rows.append(_("Next contract visit: {0}").format(_day(visit)))
    for meter in meters:
        for trigger in meter["triggers"]:
            if trigger["trigger_type"] == "Every" and trigger.get("next_due") is not None:
                when = _(" (about {0})").format(_day(trigger["due_on"])) if trigger.get("due_on") else ""
                rows.append(_("{0} service due at {1} {2}{3}").format(meter["meter_name"], _number(trigger["next_due"]),
                    meter["unit"], when))
    return rows


def _number(value):
    value = flt(value)
    return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}".rstrip("0").rstrip(".")


def context(name, trusted=False):
    """Everything the report template needs. The caller's access to the job is checked here, unless the
    report was already authorised (`trusted`: invoicing the job, or the automatic email after completion)."""
    from projectit import meters, work_orders
    doc = frappe.get_doc("Task", name) if trusted else _job(name)
    wo = work_orders.detail(doc)
    equipment = wo.get("equipment")
    steps, photos, signature = [], [], None
    procedure = wo.get("procedure")
    for step in (procedure or {}).get("steps", []):
        kind = step["field_type"]
        if kind == "Photo" and step.get("value"):
            photos.append({"url": step["value"], "caption": step["label"]})
        elif kind == "Signature" and step.get("value"):
            signature = {"image": _image(step["value"], 600), "label": step["label"],
                "by": step.get("answered_by"), "on": step.get("answered_on")}
        elif kind == "Number" and step.get("meter_reading"):
            continue  # shown with the meter readings
        elif kind != "Photo" and kind != "Signature":
            steps.append({"heading": kind == "Heading", "label": step["label"], "answer": _answer(step),
                "failed": bool(step.get("failed"))})
    seen = {p["url"] for p in photos}
    for f in wo.get("files") or []:
        if f.file_url not in seen:  # checklist photos are also attached to the job
            photos.append({"url": f.file_url, "caption": ""})
    shown = []
    for p in photos[:PHOTO_LIMIT]:
        image = _image(p["url"])
        if image:
            shown.append({"image": image, "caption": p["caption"]})
    readings = frappe.get_all("Techy Meter Reading", filters={"work_order": doc.name},
        fields=["meter", "value", "reading_on"], order_by="reading_on asc")
    names = {m.name: m for m in frappe.get_all("Techy Meter", filters={"name": ["in", [r.meter for r in readings] or [""]]},
        fields=["name", "meter_name", "unit"])}
    readings = [{"meter": names[r.meter].meter_name, "value": f"{_number(r.value)} {names[r.meter].unit}",
        "on": format_datetime(r.reading_on, "dd MMM yyyy HH:mm")} for r in readings if r.meter in names]
    machine_meters = meters.for_machine(doc.custom_equipment, None if doc.custom_equipment else doc.custom_asset)
    parts = [{"item": r.item_name or r.item_code, "code": r.item_code, "qty": f"{_number(r.qty)} {r.uom or ''}".strip(),
        "cover": BILLING_LABELS.get(r.billing, r.billing)} for r in (wo.get("parts") or {}).get("rows", [])
        if r.status in ("Approved", "Issued")]
    billing = wo.get("billing") or {}
    labour = None
    if doc.get("custom_customer") and billing:
        if billing.get("mode") == "Hourly" and flt(billing.get("hours")):
            labour = _("{0} h on site · {1}").format(_number(billing["hours"]), LABOUR_LABELS.get(billing["billing"], billing["billing"]))
        elif billing.get("mode") == "Flat fee":
            labour = _("Fixed-price visit · {0}").format(LABOUR_LABELS.get(billing["billing"], billing["billing"]))
    customer = None
    if doc.get("custom_customer"):
        customer = {"name": frappe.db.get_value("Customer", doc.custom_customer, "customer_name") or doc.custom_customer,
            "contact": (equipment or {}).get("contact") or {}}
    settings = frappe.get_cached_doc("Techy Ops Settings")
    return {
        "company": _company(doc.name), "job": wo["work_order"],
        "cover_until": _day((equipment or {}).get("coverage", {}).get("until")), "doc": doc, "customer": customer, "equipment": equipment,
        "asset": wo.get("asset"), "technicians": [p["full_name"] for p in wo.get("assignees") or []],
        "problem": wo.get("description") or "", "work_summary": doc.get("custom_work_summary") or "",
        "checklist": [{"label": s.subject, "done": s.status == "Completed"} for s in wo.get("steps") or []],
        "procedure_title": (procedure or {}).get("title"), "steps": steps, "readings": readings, "parts": parts,
        "labour": labour, "photos": shown, "more_photos": max(0, len(photos) - PHOTO_LIMIT), "signature": signature,
        "next_service": _next_service(equipment, machine_meters),
        "opened": format_datetime(doc.creation, "dd MMM yyyy HH:mm"),
        "started": format_datetime(doc.custom_started_at, "dd MMM yyyy HH:mm") if doc.get("custom_started_at") else None,
        "completed": format_datetime(doc.custom_completed_at, "dd MMM yyyy HH:mm") if doc.get("custom_completed_at") else None,
        "footer": settings.get("service_report_footer") or "", "rating_link": _rating_link(doc), "printed": format_datetime(frappe.utils.now_datetime(), "dd MMM yyyy HH:mm"),
    }


def _rating_link(doc):
    from projectit import ratings
    return ratings.link(doc) if ratings.rateable(doc) and ratings.still_open(doc) else None


def render(name, trusted=False):
    html = _inline_images(frappe.render_template("projectit/templates/service_report.html", context(name, trusted)))
    return frappe.utils.scrub_urls(html) if hasattr(frappe.utils, "scrub_urls") else html


def build(name, trusted=False):
    """(pdf bytes, file name) for the job's report."""
    from frappe.utils.pdf import get_pdf
    html = render(name, trusted)
    # A missing or unreachable image is left out rather than failing the whole report.
    pdf = get_pdf(html, {"page-size": "A4", "margin-top": "12mm", "margin-bottom": "14mm", "margin-left": "12mm",
        "margin-right": "12mm", "encoding": "UTF-8", "load-error-handling": "ignore", "load-media-error-handling": "ignore"})
    return pdf, f"Service report {name}.pdf"


# Endpoints -----------------------------------------------------------------------------------------------------

@frappe.whitelist()
def download(name):
    """The PDF, shown in the browser."""
    ops.system_user()
    pdf, filename = build(name)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def set_summary(name, summary):
    """Technicians on the job (and managers) write the customer-facing summary, even after completion."""
    ops.system_user()
    doc = _job(name)
    if not (frappe.has_permission("Task", "write", doc=doc) or ops.manager()):
        frappe.throw(_("You cannot change this job's report."), frappe.PermissionError)
    # The summary only; saving the Task would re-run status validation on a completed job.
    frappe.db.set_value("Task", doc.name, "custom_work_summary", ops.text(summary, "the work done", 4000, required=False))
    from projectit import work_orders
    return work_orders.get_work_order(doc.name)


def _recipients(doc, recipients):
    known = customer_emails(doc.get("custom_customer"))
    if isinstance(recipients, str):
        recipients = frappe.parse_json(recipients) if recipients.strip().startswith("[") else recipients.split(",")
    chosen = list(dict.fromkeys(str(r).strip().lower() for r in (recipients or []) if str(r).strip()))
    if not chosen:
        chosen = known[:1]
    if not chosen:
        frappe.throw(_("{0} has no email address. Add one to the customer in ERPNext first.").format(doc.custom_customer))
    if len(chosen) > 10:
        frappe.throw(_("Send to at most 10 addresses."))
    for email in chosen:
        if not validate_email_address(email):
            frappe.throw(_("{0} is not a valid email address.").format(email))
    unknown = [e for e in chosen if e not in known]
    if unknown and not ops.manager():
        frappe.throw(_("You can send reports only to the customer's addresses on file. Ask a manager to send to {0}.")
            .format(", ".join(unknown)), frappe.PermissionError)
    return chosen


def send(doc, recipients, message=None, auto=False):
    """Email the report through ERPNext (callers have authorised the send and the recipients)."""
    from frappe.core.doctype.communication.email import _make
    pdf, filename = build(doc.name, trusted=auto)
    customer = frappe.db.get_value("Customer", doc.custom_customer, "customer_name") or doc.custom_customer
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
    body = message.strip() if message and message.strip() else _("Dear {0},\n\nPlease find attached the service report for {1}.\n\nThank you,\n{2}").format(
        customer, doc.subject, company or "")
    from projectit import ratings
    if ratings.rateable(doc) and ratings.still_open(doc):
        body += "\n\n" + _("How did we do? Rate this visit: {0}").format(ratings.link(doc))
    comm = _make(doctype="Task", name=doc.name, subject=_("Service report: {0}").format(doc.subject)[:140],
        content=escape(body).replace("\n", "<br>"), recipients=", ".join(recipients), send_email=True,
        attachments=[{"fname": filename, "fcontent": pdf}], print_letterhead=False)
    note = _("The service report was emailed automatically to {0}.") if auto else _("{1} emailed the service report to {0}.")
    frappe.get_doc("Task", doc.name).add_comment("Info", escape(note.format(", ".join(recipients), frappe.utils.get_fullname())))
    return comm


@frappe.whitelist(methods=["POST"])
def email_report(name, recipients=None, message=None):
    ops.system_user()
    doc = _job(name)
    if not doc.get("custom_customer"):
        frappe.throw(_("Only customer jobs have service reports to send."))
    if not can_send(doc):
        frappe.throw(_("You cannot send this job's report."), frappe.PermissionError)
    chosen = _recipients(doc, recipients)
    send(doc, chosen, ops.text(message, "the message", 2000, required=False))
    from projectit import work_orders
    return work_orders.get_work_order(doc.name)


def auto_email(name):
    """Background job after a customer job is completed (Techy Ops Settings › auto email)."""
    doc = frappe.get_doc("Task", name)
    emails = customer_emails(doc.get("custom_customer"))
    if not emails:
        doc.add_comment("Info", escape(_("The service report was not emailed: the customer has no email address.")))
        return
    send(doc, emails[:1], auto=True)


def on_completed(doc):
    """Called from the Task hook when a customer job is completed."""
    if doc.get("custom_customer") and cint(frappe.db.get_single_value("Techy Ops Settings", "service_report_auto_email")):
        frappe.enqueue("projectit.service_report.auto_email", name=doc.name, enqueue_after_commit=True)


def attach_to_invoice(invoice, task_name):
    """A copy of the job's report on its draft Sales Invoice (invoicing never fails because of it)."""
    try:
        # The invoicer is authorised to bill the job, even an Accounts User who cannot open it.
        pdf, filename = build(task_name, trusted=True)
        frappe.get_doc({"doctype": "File", "file_name": filename, "content": pdf, "is_private": 1,
            "attached_to_doctype": "Sales Invoice", "attached_to_name": invoice}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title=f"Techy Ops: service report for {task_name} on {invoice} failed")
