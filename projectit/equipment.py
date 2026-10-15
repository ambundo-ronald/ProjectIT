"""Customer equipment: machines we deliver and service at customer sites (the installed base).

ERPNext Assets are company-owned; equipment sold to customers is tracked here instead. Items flagged
"Track Installs in Techy Ops" create one Techy Equipment per unit when their Delivery Note is submitted,
with an Installation job. Completing that job marks the machine Active and records an ERPNext
Installation Note. Older machines are registered by hand. Coverage (warranty, contract or chargeable)
comes from the equipment's warranty and contract end dates.

Warranty: when we supply and install, it starts at commissioning (the installation job's completion);
when the Delivery Note is ticked "Supply only", the machine is Active at once and the warranty starts on
the delivery date. Each machine also keeps what it was built from (its manufacturing Work Order's
materials, or the item's BOM) and gets the item's standard meters.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from projectit import contracts, meters, ops, parts

FIELDS = ["name", "equipment_name", "item_code", "serial_no", "tag", "status", "customer", "customer_name",
    "site_address", "site", "project", "delivery_note", "delivered_on", "installed_on", "installation_note",
    "warranty_until", "contract_until", "service_contract", "notes", "built_from_work_order", "built_from_bom", "modified"]
STATUSES = ("Awaiting installation", "Active", "Out of service", "Decommissioned", "Cancelled")
RETIRED = ("Decommissioned", "Cancelled")
EDITABLE = ("equipment_name", "item_code", "serial_no", "tag", "status", "customer", "site_address", "project",
    "delivered_on", "installed_on", "warranty_until", "contract_until", "notes")


def coverage(row):
    """{'kind': 'Warranty' | 'Contract' | 'Chargeable' | 'Pending' | None, 'until': date} for an equipment row.

    Pending: awaiting installation, with the warranty starting at commissioning."""
    if not row or row.get("status") in RETIRED:
        return {"kind": None, "until": None}
    if row.get("status") == "Awaiting installation" and not row.get("warranty_until"):
        return {"kind": "Pending", "until": None}
    today = getdate(nowdate())
    warranty = row.get("warranty_until") and getdate(row.get("warranty_until")) >= today
    contract = row.get("contract_until") and getdate(row.get("contract_until")) >= today
    if warranty:
        return {"kind": "Warranty", "until": row.get("warranty_until"), "contract": row.get("contract_until") if contract else None}
    if contract:
        return {"kind": "Contract", "until": row.get("contract_until")}
    return {"kind": "Chargeable", "until": None}


def site_label(address):
    if not address:
        return ""
    row = frappe.db.get_value("Address", address, ["address_title", "address_line1", "city"], as_dict=True)
    if not row:
        return ""
    return ", ".join(dict.fromkeys(v for v in (row.address_title, row.city or row.address_line1) if v))[:140]


def labels(names):
    """Display fields for equipment the caller already returns (work order and request lists)."""
    names = list({n for n in names if n})
    rows = frappe.get_all("Techy Equipment", filters={"name": ["in", names]}, fields=["name", "equipment_name",
        "customer_name", "site", "warranty_until", "contract_until", "status"]) if names else []
    return {r.name: {"equipment_name": r.equipment_name, "customer_name": r.customer_name, "site": r.site,
        "coverage": coverage(r)["kind"]} for r in rows}


def _contact(customer):
    row = frappe.db.get_value("Customer", customer, ["customer_name", "mobile_no", "email_id",
        "customer_primary_contact"], as_dict=True) or {}
    name = None
    if row.get("customer_primary_contact"):
        name = frappe.db.get_value("Contact", row.customer_primary_contact, ["first_name", "last_name"], as_dict=True)
        name = " ".join(filter(None, [name.first_name, name.last_name])) if name else None
    return {"name": name, "phone": row.get("mobile_no"), "email": row.get("email_id")}


def _address(address):
    if not address:
        return None
    row = frappe.db.get_value("Address", address, ["name", "address_title", "address_line1", "address_line2",
        "city", "state", "country", "phone"], as_dict=True)
    if row:
        row.lines = [l for l in (row.address_line1, row.address_line2, ", ".join(filter(None, [row.city, row.state])),
            row.country) if l]
    return row


def summary(name):
    """Equipment block for a work order or request: what the technician needs on site."""
    if not name:
        return None
    row = frappe.db.get_value("Techy Equipment", name, FIELDS, as_dict=True)
    if not row:
        return None
    return {"name": row.name, "equipment_name": row.equipment_name, "tag": row.tag, "serial_no": row.serial_no,
        "status": row.status, "customer": row.customer, "customer_name": row.customer_name, "site": row.site,
        "address": _address(row.site_address), "contact": _contact(row.customer), "coverage": coverage(row),
        "contract": contracts.terms(row.service_contract),
        "warranty_until": row.warranty_until, "contract_until": row.contract_until, "installed_on": row.installed_on}


# Screens -----------------------------------------------------------------------------------------------------

@frappe.whitelist()
def list_equipment(search=None, customer=None, status=None, cover=None, start=0, page_length=None):
    ops.system_user()
    filters = {}
    if status in STATUSES:
        filters["status"] = status
    else:
        filters["status"] = ["not in", list(RETIRED)]
    if customer:
        filters["customer"] = customer
    today = nowdate()
    if cover == "Warranty":
        filters["warranty_until"] = [">=", today]
    elif cover == "Contract":
        filters["contract_until"] = [">=", today]
    or_filters = None
    if search:
        like = f"%{str(search).strip()[:80]}%"
        or_filters = {"name": ["like", like], "equipment_name": ["like", like], "customer_name": ["like", like],
            "tag": ["like", like], "site": ["like", like], "serial_no": ["like", like]}
    start, size = max(0, cint(start)), ops.page_size(page_length, 100)
    # All staff may look up customer equipment (field work starts from a customer call); edits are manager-only.
    rows, total = ops.paged("Techy Equipment", filters, or_filters, "customer_name asc, equipment_name asc", start, size,
        FIELDS, keep=(lambda r: coverage(r)["kind"] == "Chargeable") if cover == "Chargeable" else None)
    counts = {}
    if rows:
        counts = dict(frappe.db.sql("""SELECT custom_equipment, COUNT(*) FROM `tabTask`
            WHERE custom_work_order = 1 AND custom_equipment IN %(names)s AND status NOT IN ('Completed', 'Cancelled')
            GROUP BY custom_equipment""", {"names": tuple(r.name for r in rows)}))
    for row in rows:
        row.coverage = coverage(row)
        row.open_work_orders = counts.get(row.name, 0)
    return {"equipment": rows, "total": total, "start": start, "page_length": size,
        "has_more": start + len(rows) < total, "manager": ops.manager()}


@frappe.whitelist()
def get_equipment(name):
    ops.system_user()
    row = frappe.db.get_value("Techy Equipment", name, FIELDS, as_dict=True)
    if not row:
        frappe.throw(_("Equipment {0} was not found.").format(name), frappe.DoesNotExistError)
    jobs = frappe.get_all("Task", filters={"custom_work_order": 1, "custom_equipment": row.name},
        fields=["name", "subject", "status", "priority", "exp_end_date", "custom_work_category", "modified"],
        order_by="modified desc", limit_page_length=50)
    requests = frappe.get_all("Issue", filters={"custom_maintenance_request": 1, "custom_equipment": row.name},
        fields=["name", "subject", "status", "opening_date", "custom_work_order"], order_by="creation desc",
        limit_page_length=20)
    project_name = frappe.db.get_value("Project", row.project, "project_name") if row.project else None
    next_visit = frappe.db.get_value("Techy Contract Equipment", {"parent": row.service_contract,
        "parenttype": "Techy Service Contract", "equipment": row.name}, "next_visit") if row.service_contract else None
    return {"equipment": row, "coverage": coverage(row), "address": _address(row.site_address),
        "contract": contracts.terms(row.service_contract), "next_visit": next_visit, "parts": parts.history(row.name),
        "meters": meters.for_machine(equipment=row.name, include_inactive=ops.manager()),
        "components": component_rows(row.name), "missing_meters": meters.missing_templates(row.name, row.item_code),
        "contact": _contact(row.customer), "project_name": project_name, "work_orders": jobs, "requests": requests,
        "can_create": bool(frappe.has_permission("Task", "create")), "manager": ops.manager()}


@frappe.whitelist()
def customer_sites(customer):
    ops.system_user()
    ops.require_manager()
    names = frappe.get_all("Dynamic Link", filters={"link_doctype": "Customer", "link_name": customer,
        "parenttype": "Address"}, pluck="parent")
    rows = frappe.get_all("Address", filters={"name": ["in", names or [""]], "disabled": 0},
        fields=["name", "address_title", "address_line1", "city"], order_by="address_title asc")
    for row in rows:
        row.label = site_label(row.name)
    return rows


@frappe.whitelist()
def register_options(txt=None):
    """Customers and trackable items for the register form (managers only)."""
    ops.system_user()
    ops.require_manager()
    like = f"%{str(txt or '').strip()[:80]}%"
    customers = frappe.get_all("Customer", filters={"disabled": 0}, or_filters={"name": ["like", like],
        "customer_name": ["like", like]}, fields=["name", "customer_name"], order_by="customer_name asc",
        limit_page_length=20)
    items = frappe.get_all("Item", filters={"disabled": 0, "custom_track_installed": 1},
        fields=["name", "item_name", "warranty_period"], order_by="item_name asc", limit_page_length=100)
    return {"customers": customers, "items": items}


def _date(value):
    return getdate(value) if value else None


@frappe.whitelist(methods=["POST"])
def save_equipment(data, name=None):
    """Register existing equipment or correct a record (managers)."""
    ops.system_user()
    ops.require_manager()
    data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
    doc = frappe.get_doc("Techy Equipment", name, for_update=True) if name else frappe.new_doc("Techy Equipment")
    values = {k: data.get(k) for k in EDITABLE if k in data}
    if not frappe.db.exists("Customer", values.get("customer") or doc.customer or ""):
        frappe.throw(_("Choose a customer."))
    customer = values.get("customer") or doc.customer
    if values.get("site_address") and not frappe.db.exists("Dynamic Link", {"parenttype": "Address",
            "parent": values["site_address"], "link_doctype": "Customer", "link_name": customer}):
        frappe.throw(_("Choose one of the customer's addresses."))
    for field, doctype in (("item_code", "Item"), ("serial_no", "Serial No"), ("project", "Project")):
        if values.get(field) and not frappe.db.exists(doctype, values[field]):
            frappe.throw(_("{0} {1} was not found.").format(_(doctype), values[field]))
    if "status" in values and values["status"] not in STATUSES:
        frappe.throw(_("Invalid status."))
    if not (values.get("equipment_name") or doc.equipment_name) and values.get("item_code"):
        values["equipment_name"] = frappe.db.get_value("Item", values["item_code"], "item_name")
    values["equipment_name"] = ops.text(values.get("equipment_name") or doc.equipment_name, "a name", 140)
    for field in ("tag",):
        if field in values:
            values[field] = ops.text(values[field], "a tag", 60, required=False)
    if "notes" in values:
        values["notes"] = ops.text(values["notes"], "notes", 2000, required=False)
    for field in ("delivered_on", "installed_on", "warranty_until", "contract_until"):
        if field in values:
            values[field] = _date(values[field])
    doc.update({k: (v or None) if k not in ("equipment_name", "status") else v for k, v in values.items()})
    if not doc.status:
        doc.status = "Active"
    doc.site = site_label(doc.site_address)
    new = doc.is_new()
    if new and doc.item_code:
        set_components(doc)
    # Managers are authorised above; Desk keeps the role grid for direct editing.
    doc.save(ignore_permissions=True)
    if new:
        meters.apply_templates(doc)
    return get_equipment(doc.name)


# Built with --------------------------------------------------------------------------------------------------

def build_source(item_code, project=None):
    """(work order, bom, rows) the unit was built from: the project's manufacturing Work Order for the item,
    with what it actually used, or else the item's default BOM. Rows are per unit."""
    if not item_code:
        return None, None, []
    if project:
        orders = frappe.get_all("Work Order", filters={"production_item": item_code, "project": project,
            "docstatus": 1}, fields=["name", "qty", "bom_no", "status"], order_by="modified desc")
        orders.sort(key=lambda o: o.status != "Completed")
        if orders:
            order = orders[0]
            per = max(flt(order.qty), 1)
            rows = frappe.get_all("Work Order Item", filters={"parent": order.name, "parenttype": "Work Order"},
                fields=["item_code", "item_name", "required_qty", "consumed_qty", "stock_uom"], order_by="idx asc")
            return order.name, order.bom_no, [{"item_code": r.item_code, "item_name": r.item_name,
                "qty": round((flt(r.consumed_qty) or flt(r.required_qty)) / per, 6), "uom": r.stock_uom} for r in rows]
    bom = frappe.db.get_value("BOM", {"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
        ["name", "quantity"], as_dict=True)
    if not bom:
        return None, None, []
    per = max(flt(bom.quantity), 1)
    rows = frappe.get_all("BOM Item", filters={"parent": bom.name, "parenttype": "BOM"},
        fields=["item_code", "item_name", "stock_qty", "stock_uom"], order_by="idx asc")
    return None, bom.name, [{"item_code": r.item_code, "item_name": r.item_name,
        "qty": round(flt(r.stock_qty) / per, 6), "uom": r.stock_uom} for r in rows]


def set_components(doc):
    """Snapshot what the unit was built from, so later BOM changes do not rewrite it."""
    order, bom, rows = build_source(doc.item_code, doc.project)
    doc.built_from_work_order, doc.built_from_bom = order, bom
    doc.set("components", rows)
    return bool(rows)


def component_rows(name):
    return frappe.get_all("Techy Equipment Component", filters={"parent": name, "parenttype": "Techy Equipment"},
        fields=["item_code", "item_name", "qty", "uom"], order_by="idx asc") if name else []


@frappe.whitelist(methods=["POST"])
def refresh_components(name):
    """Managers: copy the build list again, e.g. for machines delivered before it was recorded."""
    ops.system_user()
    ops.require_manager()
    doc = frappe.get_doc("Techy Equipment", name, for_update=True)
    if not set_components(doc):
        frappe.throw(_("No manufacturing Work Order or default BOM was found for {0}.").format(doc.item_code or doc.name))
    doc.save(ignore_permissions=True)
    return get_equipment(doc.name)


# Delivery and installation -----------------------------------------------------------------------------------

def _serials(row):
    try:
        if row.get("serial_and_batch_bundle"):
            from erpnext.stock.serial_batch_bundle import get_serial_nos
            return list(get_serial_nos(row.serial_and_batch_bundle))
        return [s.strip() for s in (row.get("serial_no") or "").splitlines() if s.strip()]
    except Exception:
        return []


def on_delivery_note_submit(doc, method=None):
    """One Techy Equipment and Installation job per delivered unit of a tracked item."""
    if doc.get("is_return"):
        return
    items = {r.item_code for r in doc.items}
    tracked = {i.name: i for i in frappe.get_all("Item", filters={"name": ["in", list(items)],
        "custom_track_installed": 1}, fields=["name", "item_name", "warranty_period"])}
    if not tracked:
        return
    site = doc.get("shipping_address_name") or doc.get("customer_address")
    label = site_label(site)
    supply_only = bool(cint(doc.get("custom_supply_only")))
    for row in doc.items:
        item = tracked.get(row.item_code)
        if not item:
            continue
        serials = _serials(row)
        for i in range(max(1, cint(abs(row.stock_qty or row.qty)))):
            frappe.db.savepoint("techy_equipment")
            try:
                eq = frappe.get_doc({"doctype": "Techy Equipment", "equipment_name": row.item_name or item.item_name,
                    "item_code": row.item_code, "serial_no": serials[i] if i < len(serials) else None,
                    "status": "Active" if supply_only else "Awaiting installation", "customer": doc.customer,
                    "site_address": site, "site": label, "project": doc.get("project"), "delivery_note": doc.name,
                    "delivery_note_item": row.name, "delivered_on": doc.posting_date,
                    # Supply only: warranty from delivery. Supply and install: from commissioning.
                    "warranty_until": add_days(doc.posting_date, cint(item.warranty_period))
                        if supply_only and cint(item.warranty_period) else None})
                set_components(eq)
                eq.insert(ignore_permissions=True)
                meters.apply_templates(eq)
                if not supply_only:
                    _installation_job(eq)
            except Exception:
                frappe.db.rollback(save_point="techy_equipment")
                frappe.log_error(title=f"Techy Ops: equipment for {doc.name} / {row.item_code} failed")


def _installation_job(eq):
    from projectit import work_orders
    settings = frappe.get_cached_doc("Techy Ops Settings")
    procedure = settings.get("installation_procedure")
    if procedure and frappe.db.get_value("Techy Procedure", procedure, "disabled"):
        procedure = None
    project = eq.project if eq.project and frappe.db.get_value("Project", eq.project, "status") == "Open" else None
    description = _("Install and commission {0} for {1}{2}. Delivered on {3} ({4}).").format(eq.equipment_name,
        eq.customer_name or eq.customer, f" at {eq.site}" if eq.site else "", eq.delivered_on, eq.delivery_note)
    # Raised by the Delivery Note (stock staff may not have Task create); managers schedule and assign it.
    job = work_orders.create(_("Install {0} – {1}").format(eq.equipment_name, eq.customer_name or eq.customer)[:140],
        description, "Medium", "Installation", project=project, equipment=eq.name, procedure=procedure,
        ignore_permissions=True)
    managers = frappe.get_all("Has Role", filters={"role": ["in", ["Maintenance Manager", "Projects Manager"]],
        "parenttype": "User"}, pluck="parent")
    ops.notify(managers, _("Installation to schedule: {0}").format(job.subject), "Task", job.name, "Assignment")
    return job


def on_delivery_note_cancel(doc, method=None):
    supply_only = bool(cint(doc.get("custom_supply_only")))
    for eq in frappe.get_all("Techy Equipment", filters={"delivery_note": doc.name}, fields=["name", "status"]):
        if eq.status != "Awaiting installation" and not (supply_only and eq.status == "Active"):
            frappe.get_doc("Techy Equipment", eq.name).add_comment("Info", escape(
                _("Delivery Note {0} was cancelled after installation.").format(doc.name)))
            continue
        for job in frappe.get_all("Task", filters={"custom_equipment": eq.name, "custom_work_category": "Installation",
                "status": ["not in", ["Completed", "Cancelled"]]}, pluck="name"):
            task = frappe.get_doc("Task", job)
            task.status = "Cancelled"
            task.flags.ignore_permissions = True
            task.save()
        frappe.db.set_value("Techy Equipment", eq.name, "status", "Cancelled")


def complete_installation(task):
    """Installation job completed: the machine is live; record the ERPNext Installation Note."""
    eq = frappe.get_doc("Techy Equipment", task.custom_equipment)
    if eq.status not in ("Awaiting installation", "Active") or eq.installation_note:
        return
    eq.status = "Active"
    eq.installed_on = eq.installed_on or nowdate()
    if not eq.warranty_until and eq.item_code:
        days = cint(frappe.db.get_value("Item", eq.item_code, "warranty_period"))
        if days:
            # Supplied and installed by us: the warranty runs from commissioning.
            eq.warranty_until = add_days(eq.installed_on, days)
    if eq.delivery_note and eq.delivery_note_item:
        frappe.db.savepoint("techy_installation_note")
        try:
            dn = frappe.get_doc("Delivery Note", eq.delivery_note)
            note = frappe.get_doc({"doctype": "Installation Note", "customer": eq.customer,
                "customer_address": eq.site_address, "company": dn.company, "project": eq.project,
                "territory": dn.territory, "inst_date": eq.installed_on,
                "remarks": _("Installed through Techy Ops job {0}.").format(task.name),
                "items": [{"item_code": eq.item_code, "qty": 1, "serial_no": eq.serial_no,
                    "prevdoc_doctype": "Delivery Note", "prevdoc_docname": dn.name,
                    "prevdoc_detail_docname": eq.delivery_note_item}]})
            # The technician completed the permitted job; the note is its system-owned record.
            note.flags.ignore_permissions = True
            note.insert()
            note.submit()
            eq.installation_note = note.name
        except Exception as e:
            frappe.db.rollback(save_point="techy_installation_note")
            frappe.log_error(title=f"Techy Ops: Installation Note for {eq.name} failed")
            task.add_comment("Info", escape(_("The ERPNext Installation Note could not be created: {0}").format(
                frappe.utils.strip_html(str(e))[:200])))
    eq.save(ignore_permissions=True)
