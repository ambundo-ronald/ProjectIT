"""Service contracts for customer equipment, billed through ERPNext Subscriptions.

A Techy Service Contract lists a customer's machines, the visit frequency and procedure, and what is
covered (labour on visits, breakdown call-outs, parts included at no charge), since that varies per
customer. Billing stays on the linked Subscription. Saving a contract sets each machine's contract end
date (its coverage), and a daily job raises a service-visit job for each machine as its next visit
falls due, then moves the next visit on by the frequency.
"""
from html import escape

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate, nowdate

from projectit import ops

MONTHS = {"Monthly": 1, "Every 2 months": 2, "Quarterly": 3, "Every 4 months": 4, "Half-yearly": 6, "Yearly": 12}
PAYMENT_WARNING = ("Grace Period", "Unpaid", "Cancelled")
LIST_FIELDS = ["name", "title", "customer", "customer_name", "status", "subscription", "start_date", "end_date",
    "visit_frequency", "labour_included", "callouts_included", "modified"]


def state(row):
    """Display state: Active, Upcoming, Expired or Cancelled."""
    if row.get("status") == "Cancelled":
        return "Cancelled"
    today = getdate(nowdate())
    if row.get("start_date") and getdate(row.start_date) > today:
        return "Upcoming"
    if row.get("end_date") and getdate(row.end_date) < today:
        return "Expired"
    return "Active"


def _subscription(name):
    if not name:
        return None
    return frappe.db.get_value("Subscription", name, ["name", "status", "start_date", "end_date", "party"], as_dict=True)


def terms(name):
    """What a contract covers, for jobs and machine pages."""
    if not name:
        return None
    doc = frappe.db.get_value("Techy Service Contract", name, LIST_FIELDS, as_dict=True)
    if not doc:
        return None
    sub = _subscription(doc.subscription)
    items = frappe.get_all("Techy Contract Item", filters={"parent": name, "parenttype": "Techy Service Contract"},
        fields=["item_code", "item_name"], order_by="idx asc")
    return {"name": doc.name, "title": doc.title, "state": state(doc), "end_date": doc.end_date,
        "visit_frequency": doc.visit_frequency, "labour_included": doc.labour_included,
        "callouts_included": doc.callouts_included, "items": items,
        "subscription": sub.name if sub else None, "subscription_status": sub.status if sub else None,
        "payment_warning": bool(sub and sub.status in PAYMENT_WARNING)}


# Equipment coverage --------------------------------------------------------------------------------------------

def refresh_equipment(names):
    """Each machine's contract end date comes from its latest non-cancelled contract."""
    for name in {n for n in names if n}:
        rows = frappe.db.sql("""SELECT c.name, c.end_date FROM `tabTechy Service Contract` c
            JOIN `tabTechy Contract Equipment` m ON m.parent = c.name AND m.parenttype = 'Techy Service Contract'
            WHERE m.equipment = %s AND c.status != 'Cancelled' ORDER BY c.end_date DESC LIMIT 1""", (name,), as_dict=True)
        current = frappe.db.get_value("Techy Equipment", name, ["service_contract", "contract_until"], as_dict=True)
        if not current:
            continue
        if rows:
            values = {"service_contract": rows[0].name, "contract_until": rows[0].end_date}
        elif current.service_contract:
            values = {"service_contract": None, "contract_until": None}  # its contract was removed or cancelled
        else:
            continue  # a hand-entered contract date on a machine without a Techy contract
        frappe.db.set_value("Techy Equipment", name, values, update_modified=False)


def validate(doc, method=None):
    if doc.end_date and doc.start_date and getdate(doc.end_date) < getdate(doc.start_date):
        frappe.throw(_("The end date is before the start date."))
    if doc.visit_frequency and doc.visit_frequency not in MONTHS:
        frappe.throw(_("Invalid visit frequency."))
    if doc.subscription:
        sub = _subscription(doc.subscription)
        if not sub or sub.party != doc.customer:
            frappe.throw(_("Choose a Subscription for {0}.").format(doc.customer_name or doc.customer))
    seen = set()
    for row in doc.machines:
        machine = frappe.db.get_value("Techy Equipment", row.equipment, ["customer", "status"], as_dict=True)
        if not machine or machine.customer != doc.customer:
            frappe.throw(_("Equipment {0} does not belong to this customer.").format(row.equipment))
        if row.equipment in seen:
            frappe.throw(_("Equipment {0} is listed twice.").format(row.equipment))
        seen.add(row.equipment)
        if not row.next_visit and doc.visit_frequency:
            row.next_visit = add_months(doc.start_date, MONTHS[doc.visit_frequency])
    if not doc.title:
        doc.title = _("{0} – {1} service").format(doc.customer_name or doc.customer, (doc.visit_frequency or "").lower())[:140]


def on_update(doc, method=None):
    before = doc.get_doc_before_save()
    names = {r.equipment for r in doc.machines} | ({r.equipment for r in before.machines} if before else set())
    refresh_equipment(names)


def after_delete(doc, method=None):
    # Runs once the contract's machine rows are gone, so coverage falls back to any other contract.
    refresh_equipment([r.equipment for r in doc.machines])


# Screens -----------------------------------------------------------------------------------------------------

@frappe.whitelist()
def list_contracts(view=None, search=None):
    ops.system_user()
    filters = {}
    today = nowdate()
    if view == "Cancelled":
        filters["status"] = "Cancelled"
    else:
        filters["status"] = "Active"
        if view == "Expiring":
            filters["end_date"] = ["between", [today, add_days(today, 60)]]
        elif view == "Expired":
            filters["end_date"] = ["<", today]
        elif view != "All":
            filters["end_date"] = [">=", today]
    or_filters = None
    if search:
        like = f"%{str(search).strip()[:80]}%"
        or_filters = {"name": ["like", like], "customer_name": ["like", like], "title": ["like", like],
            "subscription": ["like", like]}
    rows = frappe.get_all("Techy Service Contract", filters=filters, or_filters=or_filters, fields=LIST_FIELDS,
        order_by="end_date asc", limit_page_length=200)
    if rows:
        names = tuple(r.name for r in rows)
        machines = {}
        for m in frappe.get_all("Techy Contract Equipment", filters={"parent": ["in", names],
                "parenttype": "Techy Service Contract"}, fields=["parent", "next_visit"]):
            machines.setdefault(m.parent, []).append(m.next_visit)
        subs = dict(frappe.get_all("Subscription", filters={"name": ["in", [r.subscription for r in rows if r.subscription] or [""]]},
            fields=["name", "status"], as_list=True))
        for row in rows:
            visits = [v for v in machines.get(row.name, []) if v]
            row.machines = len(machines.get(row.name, []))
            row.next_visit = min(visits) if visits else None
            row.state = state(row)
            row.subscription_status = subs.get(row.subscription)
            row.payment_warning = row.subscription_status in PAYMENT_WARNING
    return {"contracts": rows, "manager": ops.manager()}


@frappe.whitelist()
def get_contract(name):
    ops.system_user()
    doc = frappe.get_doc("Techy Service Contract", name)
    machines = []
    for row in doc.machines:
        eq = frappe.db.get_value("Techy Equipment", row.equipment, ["name", "equipment_name", "site", "tag", "status"],
            as_dict=True) or {}
        machines.append({"equipment": row.equipment, "equipment_name": eq.get("equipment_name"), "site": eq.get("site"),
            "tag": eq.get("tag"), "status": eq.get("status"), "next_visit": row.next_visit,
            "last_visit_job": row.last_visit_job})
    visits = frappe.get_all("Task", filters={"custom_service_contract": doc.name, "custom_work_order": 1},
        fields=["name", "subject", "status", "exp_end_date", "custom_equipment", "modified"], order_by="exp_end_date desc",
        limit_page_length=100)
    return {"contract": {f: doc.get(f) for f in LIST_FIELDS + ["contract", "visit_procedure", "notes"]},
        "state": state(doc), "items": [{"item_code": r.item_code, "item_name": r.item_name} for r in doc.included_items],
        "machines": machines, "visits": visits, "subscription": _subscription(doc.subscription),
        "payment_warning": bool(doc.subscription and (_subscription(doc.subscription) or {}).get("status") in PAYMENT_WARNING),
        "manager": ops.manager()}


@frappe.whitelist()
def contract_options(customer=None, txt=None):
    """Customers, then that customer's machines and Subscriptions, for the contract form (managers)."""
    ops.system_user()
    ops.require_manager()
    if not customer:
        like = f"%{str(txt or '').strip()[:80]}%"
        return {"customers": frappe.get_all("Customer", filters={"disabled": 0}, or_filters={"name": ["like", like],
            "customer_name": ["like", like]}, fields=["name", "customer_name"], order_by="customer_name asc",
            limit_page_length=20)}
    from projectit.equipment import RETIRED
    return {"equipment": frappe.get_all("Techy Equipment", filters={"customer": customer, "status": ["not in", list(RETIRED)]},
            fields=["name", "equipment_name", "site", "tag", "service_contract"], order_by="site asc"),
        "subscriptions": frappe.get_all("Subscription", filters={"party_type": "Customer", "party": customer},
            fields=["name", "status", "start_date", "end_date"], order_by="start_date desc")}


@frappe.whitelist()
def search_items(txt=None):
    ops.system_user()
    ops.require_manager()
    like = f"%{str(txt or '').strip()[:80]}%"
    return frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1}, or_filters={"name": ["like", like],
        "item_name": ["like", like]}, fields=["name", "item_name"], order_by="item_name asc", limit_page_length=20)


@frappe.whitelist(methods=["POST"])
def save_contract(data, name=None):
    ops.system_user()
    ops.require_manager()
    data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
    doc = frappe.get_doc("Techy Service Contract", name, for_update=True) if name else frappe.new_doc("Techy Service Contract")
    if data.get("modified") and name and str(doc.modified) != str(data["modified"]):
        frappe.throw(_("Someone else changed this contract. Reload it before saving."))
    if not frappe.db.exists("Customer", data.get("customer") or doc.customer or ""):
        frappe.throw(_("Choose a customer."))
    doc.customer = data.get("customer") or doc.customer
    doc.title = ops.text(data.get("title"), "a title", 140, required=False)
    doc.status = "Cancelled" if data.get("status") == "Cancelled" else "Active"
    doc.subscription = data.get("subscription") or None
    doc.start_date = getdate(data.get("start_date")) if data.get("start_date") else None
    doc.end_date = getdate(data.get("end_date")) if data.get("end_date") else None
    if not (doc.start_date and doc.end_date):
        frappe.throw(_("Enter the start and end dates."))
    doc.visit_frequency = data.get("visit_frequency") or "Quarterly"
    procedure = data.get("visit_procedure")
    if procedure and not frappe.db.exists("Techy Procedure", {"name": procedure, "disabled": 0}):
        frappe.throw(_("Choose an active procedure."))
    doc.visit_procedure = procedure or None
    doc.labour_included = int(bool(cint(data.get("labour_included"))))
    doc.callouts_included = int(bool(cint(data.get("callouts_included"))))
    doc.notes = ops.text(data.get("notes"), "notes", 2000, required=False)
    items = list(dict.fromkeys(i for i in (data.get("items") or []) if i))
    for item in items:
        if not frappe.db.exists("Item", item):
            frappe.throw(_("Item {0} was not found.").format(item))
    doc.set("included_items", [{"item_code": i} for i in items[:100]])
    keep = {r.equipment: r for r in doc.machines}
    machines = data.get("machines") or []
    if len(machines) > 200:
        frappe.throw(_("A contract can cover at most 200 machines."))
    rows = []
    for m in machines:
        old = keep.get(m.get("equipment"))
        rows.append({"equipment": m.get("equipment"),
            "next_visit": getdate(m["next_visit"]) if m.get("next_visit") else None,
            "last_visit_job": old.last_visit_job if old else None})
    doc.set("machines", rows)
    # Managers are authorised above; Desk keeps the role grid for direct editing.
    doc.save(ignore_permissions=True)
    return get_contract(doc.name)


# Visits ------------------------------------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def run_due_visits():
    ops.system_user()
    ops.require_manager()
    return {"created": generate_visits()}


def generate_visits():
    """Daily: a service-visit job for each covered machine whose next visit is within the lead time."""
    from projectit import work_orders
    from projectit.equipment import RETIRED
    today = getdate(nowdate())
    until = getdate(add_days(today, ops.settings().pm_lead_days))
    created = []
    for name in frappe.get_all("Techy Service Contract", filters={"status": "Active", "end_date": [">=", today],
            "start_date": ["<=", until]}, pluck="name"):
        doc = frappe.get_doc("Techy Service Contract", name)
        months = MONTHS.get(doc.visit_frequency) or 3
        changed = False
        for row in doc.machines:
            if not row.next_visit or getdate(row.next_visit) > until or getdate(row.next_visit) > getdate(doc.end_date):
                continue
            machine = frappe.db.get_value("Techy Equipment", row.equipment, ["equipment_name", "customer_name",
                "status"], as_dict=True)
            if not machine or machine.status in RETIRED:
                continue
            frappe.db.savepoint("techy_visit")
            try:
                cover = [_("Labour included") if doc.labour_included else _("Labour chargeable")]
                if doc.included_items:
                    cover.append(_("Parts included: {0}").format(", ".join(i.item_name or i.item_code for i in doc.included_items)))
                job = work_orders.create(_("Service visit: {0} – {1}").format(machine.equipment_name,
                        machine.customer_name)[:140],
                    _("Scheduled visit under contract {0} ({1}). {2}.").format(doc.name, doc.visit_frequency, ". ".join(cover)),
                    "Medium", "Preventive", equipment=row.equipment, procedure=doc.visit_procedure,
                    due_date=row.next_visit, service_contract=doc.name, ignore_permissions=True)
                row.last_visit_job = job.name
                row.next_visit = add_months(row.next_visit, months)
                changed = True
                created.append(job.name)
            except Exception:
                frappe.db.rollback(save_point="techy_visit")
                frappe.log_error(title=f"Techy Ops: service visit for {doc.name} / {row.equipment} failed")
        if changed:
            doc.flags.ignore_permissions = True
            doc.save()
    if created:
        managers = frappe.get_all("Has Role", filters={"role": ["in", ["Maintenance Manager"]], "parenttype": "User"},
            pluck="parent")
        ops.notify(managers, _("{0} service visit(s) are ready to schedule").format(len(created)), "Task", created[0],
            "Assignment")
    return created
