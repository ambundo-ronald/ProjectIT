"""Parts used on jobs: recorded by technicians, issued from stock when the job is completed.

Each line is a Techy Part Usage with the warehouse it came from (main store, a technician's van) and
how it is billed. The billing default follows the machine's cover: work on our own assets is Internal,
a machine under warranty gets parts free (Warranty), parts on the service contract's included list are
free (Contract), anything else is Chargeable at the selling price. Managers can override a line.
Completing the job posts one ERPNext Stock Entry (Material Issue) for its recorded lines; completion is
blocked when a warehouse does not hold enough stock.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from projectit import ops

BILLING = ("Chargeable", "Contract", "Warranty", "Internal", "No charge")
FIELDS = ["name", "work_order", "equipment", "item_code", "item_name", "qty", "uom", "warehouse", "billing",
    "billing_set_by_manager", "rate", "amount", "valuation_rate", "status", "stock_entry", "owner", "creation"]


def _setting(field):
    return frappe.get_cached_doc("Techy Ops Settings").get(field)


def available(item_code, warehouse):
    return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def selling_rate(item_code):
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    # The price list is the selling one; customer- or batch-specific prices are left to invoicing.
    rate = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": price_list,
        "customer": ["is", "not set"], "batch_no": ["is", "not set"]}, "price_list_rate") if price_list else None
    return flt(rate if rate is not None else frappe.db.get_value("Item", item_code, "standard_rate"))


def default_billing(task, item_code):
    """Who pays for this part on this job, from the machine's warranty and contract."""
    if not task.get("custom_equipment"):
        return "Internal"
    from projectit.equipment import coverage
    eq = frappe.db.get_value("Techy Equipment", task.custom_equipment, ["status", "warranty_until", "contract_until",
        "service_contract"], as_dict=True)
    kind = coverage(eq)["kind"] if eq else None
    if kind == "Warranty":
        return "Warranty"
    if eq and eq.service_contract and eq.contract_until and getdate(eq.contract_until) >= getdate(nowdate()) \
            and frappe.db.exists("Techy Contract Item", {"parent": eq.service_contract,
                "parenttype": "Techy Service Contract", "item_code": item_code}):
        return "Contract"
    return "Chargeable"


def _amount(row):
    return flt(row.qty) * flt(row.rate) if row.billing == "Chargeable" else 0


def summary(task_name, can_edit=False):
    rows = frappe.get_all("Techy Part Usage", filters={"work_order": task_name}, fields=FIELDS, order_by="creation asc")
    return {"rows": rows, "chargeable_total": sum(flt(r.amount) for r in rows),
        "cost_total": sum(flt(r.qty) * flt(r.valuation_rate) for r in rows), "can_edit": bool(can_edit),
        "default_warehouse": _setting("default_parts_warehouse"), "manager": ops.manager(),
        "currency": frappe.db.get_default("currency")}


def history(equipment):
    """Every part fitted to a machine, newest first."""
    return frappe.get_all("Techy Part Usage", filters={"equipment": equipment}, fields=["name", "work_order",
        "item_code", "item_name", "qty", "uom", "billing", "status", "creation"], order_by="creation desc",
        limit_page_length=100)


# Picking parts -----------------------------------------------------------------------------------------------

@frappe.whitelist()
def search_parts(txt=None, warehouse=None):
    ops.system_user()
    like = f"%{str(txt or '').strip()[:80]}%"
    items = frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1, "has_variants": 0},
        or_filters={"name": ["like", like], "item_name": ["like", like]}, fields=["name", "item_name", "stock_uom"],
        order_by="item_name asc", limit_page_length=40)
    stock = {}
    if items:
        for b in frappe.get_all("Bin", filters={"item_code": ["in", [i.name for i in items]], "actual_qty": [">", 0]},
                fields=["item_code", "warehouse", "actual_qty"]):
            entry = stock.setdefault(b.item_code, {"total": 0, "here": 0})
            entry["total"] += flt(b.actual_qty)
            if b.warehouse == warehouse:
                entry["here"] = flt(b.actual_qty)
    for item in items:
        item.in_stock = stock.get(item.name, {}).get("total", 0)
        item.here = stock.get(item.name, {}).get("here", 0)
    items.sort(key=lambda i: (-(i.here > 0), -(i.in_stock > 0), i.item_name or ""))
    return items[:20]


@frappe.whitelist()
def part_warehouses(item_code):
    """Warehouses holding the item, plus the default parts warehouse."""
    ops.system_user()
    rows = frappe.get_all("Bin", filters={"item_code": item_code, "actual_qty": [">", 0]},
        fields=["warehouse", "actual_qty"], order_by="actual_qty desc")
    default = _setting("default_parts_warehouse")
    if default and not any(r.warehouse == default for r in rows):
        rows.insert(0, frappe._dict(warehouse=default, actual_qty=0))
    return {"warehouses": rows, "default": default}


def _job(work_order):
    from projectit import work_orders
    doc = work_orders._work_order(work_order, write=True)
    if doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("Reopen the job to change its parts."))
    return doc


def _result(doc):
    from projectit import procedures
    return procedures._result(doc)


@frappe.whitelist(methods=["POST"])
def add_part(work_order, item_code, qty, warehouse):
    doc = _job(work_order)
    item = frappe.db.get_value("Item", item_code, ["name", "item_name", "stock_uom", "is_stock_item", "disabled"],
        as_dict=True)
    if not item or not item.is_stock_item or item.disabled:
        frappe.throw(_("Choose an active stock item."))
    qty = flt(qty)
    if qty <= 0 or qty > 10000:
        frappe.throw(_("Enter a quantity above zero."))
    if not frappe.db.get_value("Warehouse", {"name": warehouse, "is_group": 0, "disabled": 0}):
        frappe.throw(_("Choose a warehouse."))
    recorded = sum(flt(r.qty) for r in frappe.get_all("Techy Part Usage", filters={"work_order": doc.name,
        "item_code": item_code, "warehouse": warehouse, "status": "Recorded"}, fields=["qty"]))
    have = available(item_code, warehouse)
    if recorded + qty > have:
        frappe.throw(_("Only {0} {1} of {2} in {3}.").format(frappe.format(have), item.stock_uom, item.item_name,
            warehouse))
    row = frappe.get_doc({"doctype": "Techy Part Usage", "work_order": doc.name, "equipment": doc.get("custom_equipment"),
        "item_code": item_code, "qty": qty, "uom": item.stock_uom, "warehouse": warehouse,
        "billing": default_billing(doc, item_code), "rate": selling_rate(item_code),
        "valuation_rate": flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate")),
        "status": "Recorded"})
    row.amount = _amount(row)
    # Anyone who may work the job may record its parts; stock moves only when the job is completed.
    row.insert(ignore_permissions=True)
    return _result(doc)


@frappe.whitelist(methods=["POST"])
def remove_part(work_order, name):
    doc = _job(work_order)
    row = frappe.get_doc("Techy Part Usage", name)
    if row.work_order != doc.name:
        frappe.throw(_("This part is not on the job."))
    if row.status != "Recorded":
        frappe.throw(_("This part has already left stock. Cancel its Stock Entry in ERPNext to undo it."))
    frappe.delete_doc("Techy Part Usage", row.name, ignore_permissions=True)
    return _result(doc)


@frappe.whitelist(methods=["POST"])
def set_billing(work_order, name, billing):
    """Managers decide the billing for a line, before or after the job is completed."""
    from projectit import work_orders
    ops.require_manager()
    doc = work_orders._work_order(work_order)
    if billing not in BILLING:
        frappe.throw(_("Invalid billing."))
    row = frappe.get_doc("Techy Part Usage", name)
    if row.work_order != doc.name:
        frappe.throw(_("This part is not on the job."))
    row.billing = billing
    row.billing_set_by_manager = 1
    row.amount = _amount(row)
    row.save(ignore_permissions=True)
    return _result(doc)


# Completion --------------------------------------------------------------------------------------------------

def check_stock(task_name):
    """Before completing: every recorded line must be in stock (validate_task)."""
    need = {}
    for row in frappe.get_all("Techy Part Usage", filters={"work_order": task_name, "status": "Recorded"},
            fields=["item_code", "item_name", "warehouse", "qty", "uom"]):
        key = (row.item_code, row.warehouse)
        need.setdefault(key, [0, row])[0] += flt(row.qty)
    short = [_("{0} {1} of {2} in {3} (have {4})").format(frappe.format(qty), row.uom, row.item_name, row.warehouse,
        frappe.format(available(*key))) for key, (qty, row) in need.items() if available(*key) < qty]
    if short:
        frappe.throw(_("Not enough stock to complete this job: {0}. Restock or change the warehouse first.").format(
            "; ".join(short)))


def issue(task):
    """On completion: one Material Issue for the job's recorded parts. Failures leave the lines for a retry."""
    rows = frappe.get_all("Techy Part Usage", filters={"work_order": task.name, "status": "Recorded"},
        fields=["name", "item_code", "qty", "warehouse"])
    if not rows:
        return None
    company = frappe.db.get_value("Warehouse", rows[0].warehouse, "company")
    account = _setting("parts_expense_account")
    frappe.db.savepoint("techy_parts")
    try:
        entry = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Issue", "company": company,
            "project": task.project, "remarks": _("Parts used on job {0}: {1}").format(task.name, task.subject),
            "items": [{"item_code": r.item_code, "qty": r.qty, "s_warehouse": r.warehouse, "project": task.project,
                **({"expense_account": account} if account else {})} for r in rows]})
        # The technician completed the permitted job; the stock movement is its system-owned record.
        entry.flags.ignore_permissions = True
        entry.insert()
        entry.submit()
    except Exception as e:
        frappe.db.rollback(save_point="techy_parts")
        frappe.log_error(title=f"Techy Ops: parts for {task.name} were not issued")
        task.add_comment("Info", escape(_("Parts could not be taken out of stock: {0}. A manager can retry from the job.")
            .format(frappe.utils.strip_html(str(e))[:200])))
        return None
    for r in rows:
        frappe.db.set_value("Techy Part Usage", r.name, {"status": "Issued", "stock_entry": entry.name})
    task.add_comment("Info", escape(_("Parts taken out of stock with {0}.").format(entry.name)))
    return entry.name


@frappe.whitelist(methods=["POST"])
def retry_issue(work_order):
    from projectit import work_orders
    ops.require_manager()
    doc = work_orders._work_order(work_order)
    if doc.status != "Completed":
        frappe.throw(_("Parts leave stock when the job is completed."))
    check_stock(doc.name)
    if not issue(doc):
        frappe.throw(_("The parts could not be issued. See the job's activity for the reason."))
    return work_orders.get_work_order(doc.name)
