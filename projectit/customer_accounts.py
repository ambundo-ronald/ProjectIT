"""Customer accounts for the customer app (Techy Plant, at /techy-app/plant).

When we install a plant and register its machine, we invite the customer's people. Each gets a Website User (no
Desk), a Contact on the Customer, and a Techy Customer User record that says which customer they belong to and
what they may do:

- Customer admin: every machine of their customer; can invite and manage their own operators.
- Operator: only the machines listed on their record; logs readings and raises requests.

Customer accounts never get role rights on any DocType. Everything they see comes through projectit.plant, which
checks the account first. guard() (an auth hook) refuses every other API call from them, so a staff endpoint that
forgot a check still cannot leak to a customer.
"""
import frappe
from frappe import _
from frappe.utils import now_datetime, validate_email_address

from projectit import ops

ACCESS = {"Customer admin": "Techy Customer Admin", "Operator": "Techy Operator"}
CUSTOMER_ROLES = set(ACCESS.values())
HOME = "techy-app/plant"
DOCTYPE = "Techy Customer User"

# What a customer account may call besides projectit.plant.* and the account endpoints below.
ALLOWED = {"login", "logout", "frappe.handler.logout", "frappe.auth.get_logged_user", "projectit.api.get_modules_for_router",
    "projectit.api.my_apps", "projectit.api.get_header_info", "projectit.api.get_employee_id",
    # Phone notifications: their own subscriptions and what is new for them (see projectit.push).
    "projectit.push.public_key", "projectit.push.subscribe", "projectit.push.unsubscribe", "projectit.push.pending",
    "projectit.push.test"}
ALLOWED_PREFIXES = ("projectit.plant.", "projectit.customer_accounts.")


def is_customer(user=None):
    """A customer's account (whether or not it is still enabled)."""
    user = user or frappe.session.user
    if user in ("Guest", "Administrator"):
        return False
    return bool(set(frappe.get_roles(user)) & CUSTOMER_ROLES)


def account(user=None):
    """The signed-in person's enabled customer account, or None. A manager previewing the plant app (see
    preview()) gets a read-only stand-in for that customer's admin."""
    me = frappe.session.user
    user = user or me
    if user == "Guest":
        return None
    row = frappe.db.get_value(DOCTYPE, {"user": user, "enabled": 1}, ["name", "user", "customer", "customer_name",
        "access", "full_name"], as_dict=True) if user != "Administrator" else None
    if row:
        return row
    return preview() if user == me else None


PREVIEW_HEADER = "X-Techy-Preview"


def preview():
    """A manager seeing the plant app as a machine's customer does: the machine comes in a request header from the
    app, and only reading is allowed (writable() refuses everything else)."""
    request = getattr(frappe.local, "request", None)
    equipment = frappe.get_request_header(PREVIEW_HEADER) if request else None
    if not equipment or is_customer():
        return None
    if not set(frappe.get_roles()) & ops.MANAGER_ROLES:
        return None
    row = frappe.db.get_value("Techy Equipment", str(equipment)[:140], ["customer", "customer_name"], as_dict=True)
    if not row or not row.customer:
        return None
    return frappe._dict(name=None, user=frappe.session.user, customer=row.customer,
        customer_name=row.customer_name or row.customer, access="Customer admin",
        full_name=frappe.utils.get_fullname(), preview=True)


def writable(acc=None):
    """The account, unless this is a manager's preview (which only reads)."""
    acc = acc or require_account()
    if acc.get("preview"):
        frappe.throw(_("This is a preview of the customer's app: nothing can be saved."), frappe.PermissionError)
    return acc


def require_account():
    acc = account()
    if not acc:
        frappe.throw(_("This account has no access to a plant. Ask us to invite you."), frappe.PermissionError)
    return acc


def machines(acc):
    """The machines this account may see: all of the customer's for an admin, the listed ones for an operator."""
    filters = {"customer": acc.customer, "status": ["!=", "Cancelled"]}
    if acc.access != "Customer admin":
        listed = frappe.get_all("Techy Customer Machine", filters={"parent": acc.name, "parenttype": DOCTYPE},
            pluck="equipment")
        if not listed:
            return []
        filters["name"] = ["in", listed]
    return frappe.get_all("Techy Equipment", filters=filters, pluck="name", order_by="equipment_name asc")


def require_machine(equipment, acc=None):
    """The account, if it may see this machine; otherwise a permission error (never says whether it exists)."""
    acc = acc or require_account()
    if not equipment or equipment not in machines(acc):
        frappe.throw(_("This machine is not on your account."), frappe.PermissionError)
    return acc


# Every request -----------------------------------------------------------------------------------------------

def _method(path, form):
    if form.get("cmd"):
        return form.get("cmd")
    parts = [p for p in (path or "").split("/") if p]
    # /api/method/<m> or /api/v2/method/<m>
    if len(parts) >= 3 and parts[0] == "api" and "method" in parts[1:3]:
        return parts[parts.index("method") + 1]
    return None


def guard():
    """auth_hooks: a customer account reaches only the customer app's endpoints, and nothing through /api/resource."""
    request = getattr(frappe.local, "request", None)
    if not request or not is_customer():
        return
    path = request.path or ""
    method = _method(path, frappe.local.form_dict or {})
    if method is None and not path.startswith("/api/"):
        return  # pages (the app itself, /update-password, assets); Desk is closed to Website Users anyway
    if method in ("logout", "frappe.handler.logout"):
        return
    allowed = method and (method in ALLOWED or method.startswith(ALLOWED_PREFIXES))
    if not allowed or not account():
        frappe.throw(_("Not permitted."), frappe.PermissionError)


# Who may manage accounts ---------------------------------------------------------------------------------------

def _scope(customer=None, equipment=None, write=True):
    """(customer, staff?) the caller may manage. Staff managers choose; a customer admin always gets their own."""
    acc = account()
    if acc and acc.get("preview") and not write:
        return acc.customer, False
    if acc and acc.get("preview"):
        writable(acc)
    if acc:
        if acc.access != "Customer admin":
            frappe.throw(_("Only the customer's admin can manage accounts."), frappe.PermissionError)
        return acc.customer, False
    ops.require_manager()
    if equipment and not customer:
        customer = frappe.db.get_value("Techy Equipment", equipment, "customer")
        if not customer:
            frappe.throw(_("Set the machine's customer first."))
    if not customer or not frappe.db.exists("Customer", customer):
        frappe.throw(_("Choose the customer."))
    return customer, True


def _record(user, customer):
    name = frappe.db.get_value(DOCTYPE, {"user": user, "customer": customer}, "name")
    if not name:
        frappe.throw(_("This person has no account with this customer."), frappe.PermissionError)
    return frappe.get_doc(DOCTYPE, name)


def _machines_for(customer, values):
    values = frappe.parse_json(values) if isinstance(values, str) else (values or [])
    owned = set(frappe.get_all("Techy Equipment", filters={"customer": customer, "status": ["!=", "Cancelled"]}, pluck="name"))
    wrong = [v for v in values if v not in owned]
    if wrong:
        frappe.throw(_("These machines are not this customer's: {0}").format(", ".join(wrong)))
    return list(dict.fromkeys(values))


def _row(doc):
    user = frappe.db.get_value("User", doc.user, ["last_login", "last_active", "enabled"], as_dict=True) or {}
    return {"user": doc.user, "full_name": doc.full_name or doc.user, "access": doc.access,
        "enabled": bool(doc.enabled and user.get("enabled")), "machines": [m.equipment for m in doc.machines],
        "machine_names": [m.equipment_name or m.equipment for m in doc.machines], "invited_on": doc.invited_on,
        "last_login": user.get("last_login"), "joined": bool(user.get("last_login")), "me": doc.user == frappe.session.user}


@frappe.whitelist()
def list_accounts(customer=None, equipment=None):
    """People with access to this customer's plant (staff: any customer; a customer admin: their own)."""
    customer, staff = _scope(customer, equipment, write=False)
    names = frappe.get_all(DOCTYPE, filters={"customer": customer}, pluck="name", order_by="access asc, full_name asc")
    rows = [_row(frappe.get_doc(DOCTYPE, n)) for n in names]
    if equipment:
        # On a machine's page: who can see this machine.
        rows = [r for r in rows if r["access"] == "Customer admin" or equipment in r["machines"]]
    options = frappe.get_all("Techy Equipment", filters={"customer": customer, "status": ["!=", "Cancelled"]},
        fields=["name", "equipment_name", "site"], order_by="equipment_name asc")
    return {"customer": customer, "customer_name": frappe.db.get_value("Customer", customer, "customer_name"),
        "accounts": rows, "machines": options, "staff": staff}


def _contact(user, full_name, email, customer, phone=None):
    name = frappe.db.get_value("Contact", {"email_id": email}, "name")
    contact = frappe.get_doc("Contact", name) if name else frappe.new_doc("Contact")
    if not name:
        first, _sep, last = full_name.partition(" ")
        contact.update({"first_name": first, "last_name": last})
        contact.append("email_ids", {"email_id": email, "is_primary": 1})
        if phone:
            contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
    contact.user = user
    if not any(l.link_doctype == "Customer" and l.link_name == customer for l in contact.links):
        contact.append("links", {"link_doctype": "Customer", "link_name": customer})
    contact.flags.ignore_permissions = True
    contact.save() if name else contact.insert()
    return contact.name


def _invite_link(user):
    return frappe.get_doc("User", user)._reset_password(send_email=False)


def _send(user, full_name, link, customer_name):
    """Email the invitation. Returns False when the site cannot send email (the link is shown instead)."""
    company = frappe.db.get_single_value("Global Defaults", "default_company") or _("us")
    try:
        frappe.sendmail(recipients=[user], subject=_("Your {0} plant app account").format(company),
            message=_("<p>Hello {0},</p><p>{1} has given you access to the plant app for <b>{2}</b>: log your plant "
                "readings, follow how it is running and ask us for service.</p><p><a href=\"{3}\">Set your password and "
                "sign in</a></p><p>The link works once. If it has expired, ask us for a new one.</p>").format(
                frappe.utils.escape_html(full_name), frappe.utils.escape_html(company),
                frappe.utils.escape_html(customer_name or ""), link),
            now=True)
        return True
    except Exception:
        frappe.log_error(title="Customer invitation email could not be sent")
        return False


@frappe.whitelist(methods=["POST"])
def invite(full_name, email, access="Operator", customer=None, equipment=None, machines=None, phone=None):
    """Create a customer account and invite the person by email. Also returns the link, to share another way."""
    customer, staff = _scope(customer, equipment)
    full_name = ops.text(full_name, "the person's name", 140)
    email = str(email or "").strip().lower()
    if not validate_email_address(email):
        frappe.throw(_("Enter a valid email address."))
    if access not in ACCESS:
        frappe.throw(_("Choose Customer admin or Operator."))
    if access == "Customer admin" and not staff:
        frappe.throw(_("Only we can add another customer admin. Ask us."), frappe.PermissionError)
    chosen = _machines_for(customer, machines if machines is not None else ([equipment] if equipment else []))

    existing = frappe.db.get_value("User", email, ["name", "user_type"], as_dict=True)
    if existing and existing.user_type == "System User":
        frappe.throw(_("{0} is a staff account. Use a different email for the customer app.").format(email))
    other = frappe.db.get_value(DOCTYPE, {"user": email}, ["name", "customer"], as_dict=True)
    if other and other.customer != customer:
        frappe.throw(_("{0} already has an account with another customer.").format(email))
    if other:
        frappe.throw(_("{0} already has an account. Change it in the list instead.").format(email))

    if existing:
        user = frappe.get_doc("User", email)
    else:
        first, _sep, last = full_name.partition(" ")
        user = frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "last_name": last,
            "user_type": "Website User", "send_welcome_email": 0, "enabled": 1})
        user.flags.ignore_permissions = True
        user.insert()
    user.flags.ignore_permissions = True
    user.add_roles(ACCESS[access])
    frappe.db.set_value("User", email, "enabled", 1)

    doc = frappe.get_doc({"doctype": DOCTYPE, "user": email, "customer": customer, "access": access, "enabled": 1,
        "invited_by": frappe.session.user, "invited_on": now_datetime(),
        "contact": _contact(email, full_name, email, customer, phone),
        "machines": [{"equipment": m} for m in chosen] if access == "Operator" else []})
    doc.insert(ignore_permissions=True)
    link = _invite_link(email)
    customer_name = frappe.db.get_value("Customer", customer, "customer_name")
    return {"account": _row(doc), "link": link, "emailed": _send(email, full_name, link, customer_name)}


@frappe.whitelist(methods=["POST"])
def update_account(user, access=None, enabled=None, machines=None, customer=None, equipment=None):
    """Change someone's access, machines, or switch the account off (it is never deleted: their logs stay theirs)."""
    customer, staff = _scope(customer, equipment)
    doc = _record(user, customer)
    if not staff and (doc.access == "Customer admin" or doc.user == frappe.session.user):
        frappe.throw(_("Ask us to change a customer admin's account."), frappe.PermissionError)
    if access is not None and access != doc.access:
        if access not in ACCESS or (access == "Customer admin" and not staff):
            frappe.throw(_("Only we can make someone a customer admin."), frappe.PermissionError)
        target = frappe.get_doc("User", doc.user)
        target.flags.ignore_permissions = True
        target.remove_roles(ACCESS[doc.access])
        target.add_roles(ACCESS[access])
        doc.access = access
    if machines is not None:
        doc.set("machines", [{"equipment": m} for m in _machines_for(customer, machines)])
    if doc.access == "Customer admin":
        doc.set("machines", [])
    if enabled is not None:
        doc.enabled = 1 if frappe.utils.cint(enabled) else 0
        # Switching the account off also stops the person signing in.
        frappe.db.set_value("User", doc.user, "enabled", doc.enabled)
    doc.save(ignore_permissions=True)
    return _row(doc)


@frappe.whitelist(methods=["POST"])
def resend_invite(user, customer=None, equipment=None):
    """A fresh set-password link (the old one stops working), emailed again and returned to share another way."""
    customer, staff = _scope(customer, equipment)
    doc = _record(user, customer)
    if not doc.enabled:
        frappe.throw(_("Switch the account on first."))
    if not staff and doc.access == "Customer admin":
        frappe.throw(_("Ask us to send a customer admin a new link."), frappe.PermissionError)
    link = _invite_link(doc.user)
    return {"link": link, "emailed": _send(doc.user, doc.full_name or doc.user, link, doc.customer_name)}
