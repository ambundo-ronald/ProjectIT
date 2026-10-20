"""Who may open which Techy app.

Techy Ops, Techy Work and Techy Manage are ticked per person on their Employee (Techy App Access). ERPNext roles
add to that: maintenance staff and project managers always get Techy Ops, and System Managers get Techy Manage, and
Techy Work when they have an Employee (checking in needs one). apps_for() is the one place this is decided; the app's
pages, its routes and the server's Work and Manage endpoints all ask it.
"""
import frappe

APPS = ("Ops", "WorkIT", "ManageIT", "Plant")
OPS_ROLES = {"Maintenance User", "Maintenance Manager", "Projects Manager", "System Manager"}


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


def apps_for(user=None):
    """The Techy apps a user may open, in menu order (see the top of this file)."""
    user = user or frappe.session.user
    if user == "Guest":
        return []
    from projectit import customer_accounts
    if customer_accounts.is_customer(user):
        # Customers have the plant app only (and nothing once their account is switched off).
        return ["Plant"] if customer_accounts.account(user) else []
    employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
    apps = set(frappe.get_all("Mobile Module", filters={"parent": employee, "parenttype": "Employee",
        "parentfield": "custom_mobile_module"}, pluck="module_name")) if employee else set()
    roles = set(frappe.get_roles(user))
    if roles & OPS_ROLES:
        apps.add("Ops")
    if "System Manager" in roles:
        apps.add("ManageIT")
        if employee:
            apps.add("WorkIT")
    return [app for app in APPS if app in apps]


def has_app(app, user=None):
    return app in apps_for(user)


@frappe.whitelist()
def get_modules_for_router(user_id=None):
    """Route prefixes the signed-in user may open. `user_id` is ignored and kept only for older clients.

    Home is always open. Some Ops pages need more than the Ops app; the app marks those routes and they open only
    when listed here, so approvers and accounts staff reach their queues even without Ops (e.g. stock keepers).
    """
    from projectit import billing, customer_accounts, ops, parts
    if customer_accounts.is_customer():
        return [app.lower() for app in apps_for()]  # no Home: the plant app is all they have
    modules = ["home"] + [app.lower() for app in apps_for()]
    if parts.can_approve():
        modules.append("ops/parts-requests")
    if billing.can_invoice():
        modules.append("ops/billing")
    if ops.manager():
        modules += ["ops/reports", "ops/dispatch"]
    return modules


@frappe.whitelist()
def my_apps():
    """The Techy apps the signed-in user may open (never another user's)."""
    return apps_for()
