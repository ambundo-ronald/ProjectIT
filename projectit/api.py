import frappe


def _own_employee():
    """The signed-in user's Employee, if any. Callers never choose whose record they get."""
    if frappe.session.user == "Guest":
        return None
    return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


@frappe.whitelist()
def get_employee_id(user_id=None):
    """The signed-in user's Employee ID. `user_id` is ignored and kept only for older clients."""
    return _own_employee()


@frappe.whitelist()
def get_header_info():
    app_logo = frappe.get_single("Navbar Settings").app_logo
    company = frappe.get_single("Global Defaults").default_company
    return app_logo, company


@frappe.whitelist()
def get_modules_for_router(user_id=None):
    """Route prefixes the signed-in user may open. `user_id` is ignored and kept only for older clients."""
    employee_id = _own_employee()
    modules = frappe.get_all("Mobile Module", filters={"parent": employee_id, "parenttype": "Employee"},
        pluck="module_name") if employee_id else []
    modules.append('home')
    modules = [m.lower() for m in modules]
    # Approvers and accounts staff reach their Ops queues without the Ops module (e.g. stock keepers).
    from projectit import billing, ops, parts
    if parts.can_approve():
        modules.append('ops/parts-requests')
    if billing.can_invoice():
        modules.append('ops/billing')
    if ops.manager():
        modules.append('ops/reports')
    return modules


@frappe.whitelist()
def my_apps():
    """Techy App modules enabled for the signed-in user's own Employee (never another user's)."""
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
    if not employee:
        return []
    return frappe.get_all("Mobile Module", filters={"parent": employee, "parenttype": "Employee",
        "parentfield": "custom_mobile_module"}, pluck="module_name", order_by="idx asc")
