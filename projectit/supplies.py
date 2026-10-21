"""Filters and chemicals at a customer's machine: when they are due for a change, what is left on site, and
ordering more.

Each machine lists its supplies (Techy Equipment Supply): how often a filter is changed or a chemical topped up,
how much each change uses, how much is on site and when to reorder. The customer's operator (plant app) or our
technician records each change, refill or delivery (Techy Supply Change); the stock follows. A change that is due
or stock at its reorder level shows on the customer's Home and in the plant's status. Order more makes a draft
Quotation for the customer with the supply's item (or a work request when it has no item) and tells our managers.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from projectit import ops

ACTIONS = ("Changed", "Refilled", "Received", "Counted")
KINDS = ("Filter", "Chemical", "Salt", "Other")
SOON_DAYS = 3
CHANGE = "Techy Supply Change"


def state(row, today=None):
    """A supply as the screens show it: due date, whether a change is due or soon, and whether stock is low."""
    today = today or getdate(nowdate())
    every = cint(row.change_every_days)
    due_on = getdate(add_days(getdate(row.last_changed_on), every)) if row.last_changed_on and every else None
    days_left = (due_on - today).days if due_on else None
    reorder = flt(row.reorder_at)
    return {"name": row.name, "supply_name": row.supply_name, "kind": row.kind or "Other", "item_code": row.item_code,
        "unit": row.unit or "", "change_every_days": every or None, "per_change": flt(row.per_change) or None,
        "stock": flt(row.stock), "reorder_at": reorder or None, "order_qty": flt(row.order_qty) or None,
        "last_changed_on": row.last_changed_on, "due_on": due_on, "days_left": days_left,
        "due": days_left is not None and days_left <= 0, "soon": days_left is not None and 0 < days_left <= SOON_DAYS,
        "low": reorder > 0 and flt(row.stock) <= reorder, "ordered_on": row.ordered_on}


def rows(equipment):
    if not equipment:
        return []
    return [state(r) for r in frappe.get_all("Techy Equipment Supply", filters={"parent": equipment,
        "parenttype": "Techy Equipment"}, fields=["*"], order_by="idx asc")]


def reasons(equipment):
    """What the plant's status should say about its supplies."""
    out = []
    for s in rows(equipment):
        if s["due"]:
            out.append(_("{0}: due for a change.").format(s["supply_name"]))
        if s["low"] and not s["ordered_on"]:
            out.append(_("{0}: running low ({1} {2} left).").format(s["supply_name"], ops_num(s["stock"]), s["unit"]))
    return out


def ops_num(value):
    from projectit.meters import fmt
    return fmt(value)


def history(equipment, limit=20):
    return frappe.get_all(CHANGE, filters={"equipment": equipment}, fields=["supply_name", "action", "qty", "stock_after",
        "changed_on", "by", "source", "note"], order_by="changed_on desc", limit_page_length=limit)


def _row(equipment, supply):
    row = frappe.db.get_value("Techy Equipment Supply", {"name": supply, "parent": equipment,
        "parenttype": "Techy Equipment"}, ["*"], as_dict=True) if supply else None
    if not row:
        frappe.throw(_("This supply is not on the machine."))
    return row


def record(equipment, supply, action, qty=None, note=None, source=None):
    """A change, refill, delivery or count; the stock follows. Returns the supply's new state."""
    if action not in ACTIONS:
        frappe.throw(_("Choose what was done."))
    frappe.db.get_value("Techy Equipment", equipment, "name", for_update=True)  # one change at a time per machine
    row = _row(equipment, supply)
    given = qty not in (None, "")
    qty = flt(qty) if given else (flt(row.per_change) or 1 if action == "Changed" else None)
    if action in ("Refilled", "Received") and not (qty and qty > 0):
        frappe.throw(_("Enter how much."))
    if action == "Counted" and (qty is None or qty < 0):
        frappe.throw(_("Enter how many are on site."))
    if qty is not None and qty > 1e6:
        frappe.throw(_("Enter a sensible quantity."))
    values, stock = {}, flt(row.stock)
    if action == "Counted":
        stock = qty
    elif action == "Received":
        stock += qty
        values.update(ordered_on=None, order_ref=None, order_doctype=None)  # the order arrived
    else:
        stock = max(0.0, stock - qty)
        values["last_changed_on"] = now_datetime()
    values["stock"] = stock
    frappe.db.set_value("Techy Equipment Supply", row.name, values)
    frappe.get_doc({"doctype": CHANGE, "equipment": equipment, "supply": row.name, "supply_name": row.supply_name,
        "action": action, "qty": qty, "stock_after": stock, "changed_on": now_datetime(), "by": frappe.session.user,
        "source": source or "", "note": ops.text(note, "a note", 300, required=False) or None}).insert(ignore_permissions=True)
    from projectit import plant
    plant.queue_status(equipment)
    return state(frappe.db.get_value("Techy Equipment Supply", row.name, ["*"], as_dict=True))


def order(equipment, supply, qty=None):
    """Ask us for more: a draft Quotation with the supply's item (or a work request), and our managers are told."""
    row = _row(equipment, supply)
    if row.ordered_on:
        frappe.throw(_("Already ordered on {0}. We will be in touch.").format(frappe.utils.format_date(row.ordered_on)))
    qty = flt(qty) or flt(row.order_qty) or max(flt(row.per_change), 1)
    customer = frappe.db.get_value("Techy Equipment", equipment, "customer")
    frappe.db.set_value("Techy Equipment Supply", row.name, {"ordered_on": now_datetime(), "order_doctype": None, "order_ref": None})
    if row.item_code and customer:
        # ERPNext reads the item, price list and taxes with the user's own rights, and a customer has none. The draft
        # is made in the background as the system (switching user inside a web request would break the session).
        frappe.enqueue("projectit.supplies.place_order", queue="short", enqueue_after_commit=True, equipment=equipment,
            supply=row.name, qty=qty, asked_by=frappe.session.user)
    else:
        _ordered(equipment, row, qty, _request(equipment, row, qty, frappe.session.user))
    from projectit import plant
    plant.queue_status(equipment)
    return state(frappe.db.get_value("Techy Equipment Supply", row.name, ["*"], as_dict=True))


def _what(row, qty):
    return _("{0} {1} of {2}").format(ops_num(qty), row.unit or "", row.supply_name)


def _request(equipment, row, qty, asked_by):
    """A work request in our inbox for the order (no item to quote)."""
    from projectit import work_requests
    name = frappe.db.get_value("Techy Equipment", equipment, "equipment_name")
    issue = work_requests._issue(_("Order: {0}").format(_what(row, qty))[:140], _("Please send {0} for {1}.").format(
        _what(row, qty), name), None, None, asked_by, equipment=equipment)
    return ("Issue", issue.name)


def _ordered(equipment, row, qty, ref):
    frappe.db.set_value("Techy Equipment Supply", row.name, {"order_doctype": ref[0], "order_ref": ref[1]})
    from projectit.meters import _managers
    machine = frappe.db.get_value("Techy Equipment", equipment, ["equipment_name", "customer_name"], as_dict=True)
    ops.notify(_managers(), _("Supplies ordered for {0} ({1}): {2}.").format(machine.equipment_name, machine.customer_name,
        _what(row, qty)), ref[0], ref[1])


def place_order(equipment, supply, qty, asked_by):
    """Background job: a draft Quotation for the customer (our sales staff price and send it); a work request if the
    quotation cannot be made."""
    row = _row(equipment, supply)
    machine = frappe.db.get_value("Techy Equipment", equipment, ["equipment_name", "customer"], as_dict=True)
    frappe.set_user("Administrator")
    ref = None
    frappe.db.savepoint("techy_supply_order")
    try:
        quote = frappe.get_doc({"doctype": "Quotation", "quotation_to": "Customer", "party_name": machine.customer,
            "company": frappe.db.get_single_value("Global Defaults", "default_company"), "transaction_date": nowdate(),
            "order_type": "Sales", "items": [{"item_code": row.item_code, "qty": qty}]})
        quote.insert(ignore_permissions=True)
        quote.add_comment("Info", escape(_("Asked for in the plant app by {0} ({1}) for {2}.").format(
            frappe.utils.get_fullname(asked_by), asked_by, machine.equipment_name)))
        ref = ("Quotation", quote.name)
    except Exception:
        frappe.db.rollback(save_point="techy_supply_order")
        frappe.log_error(title=f"Techy Plant: quotation for {row.supply_name} failed")
        ref = _request(equipment, row, qty, asked_by)
    _ordered(equipment, row, qty, ref)


# Staff (the machine page) ------------------------------------------------------------------------------------------

def _machine(equipment):
    ops.system_user()
    if not equipment or not frappe.db.exists("Techy Equipment", equipment):
        frappe.throw(_("Equipment {0} was not found.").format(equipment), frappe.DoesNotExistError)
    return equipment


@frappe.whitelist()
def list_supplies(equipment):
    _machine(equipment)
    return {"supplies": rows(equipment), "history": history(equipment), "manager": ops.manager(),
        "kinds": KINDS}


@frappe.whitelist(methods=["POST"])
def save_supplies(equipment, supplies):
    """Managers set which supplies a machine has (stock and dates of existing ones are kept unless changed)."""
    _machine(equipment)
    ops.require_manager()
    items = frappe.parse_json(supplies) if isinstance(supplies, str) else (supplies or [])
    if not isinstance(items, list) or len(items) > 20:
        frappe.throw(_("Add at most 20 supplies."))
    doc = frappe.get_doc("Techy Equipment", equipment, for_update=True)
    old = {r.name: r for r in doc.supplies}
    doc.set("supplies", [])
    for item in items:
        kind = item.get("kind") or "Other"
        if kind not in KINDS:
            frappe.throw(_("Invalid kind."))
        if item.get("item_code") and not frappe.db.exists("Item", item["item_code"]):
            frappe.throw(_("Item {0} was not found.").format(item["item_code"]))
        previous = old.get(item.get("name"))
        doc.append("supplies", {"supply_name": ops.text(item.get("supply_name"), "the supply's name", 80), "kind": kind,
            "item_code": item.get("item_code") or None, "unit": ops.text(item.get("unit"), "the unit", 20, required=False) or "pcs",
            "change_every_days": max(0, cint(item.get("change_every_days"))) or None,
            "per_change": max(0.0, flt(item.get("per_change"))) or None, "stock": max(0.0, flt(item.get("stock"))),
            "reorder_at": max(0.0, flt(item.get("reorder_at"))) or None, "order_qty": max(0.0, flt(item.get("order_qty"))) or None,
            "last_changed_on": previous.last_changed_on if previous else None,
            "ordered_on": previous.ordered_on if previous else None, "order_doctype": previous.order_doctype if previous else None,
            "order_ref": previous.order_ref if previous else None})
    doc.flags.ignore_permissions = True
    doc.save()
    from projectit import plant
    plant.queue_status(equipment)
    return list_supplies(equipment)


@frappe.whitelist(methods=["POST"])
def record_change(equipment, supply, action, qty=None, note=None):
    """Our technician records a change, refill, delivery or count."""
    _machine(equipment)
    record(equipment, supply, action, qty, note)
    return list_supplies(equipment)
