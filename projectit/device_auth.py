"""Signing in from the Techy phone app (Play Store), which talks to whichever company's site the person typed in.

A browser keeps a Frappe session cookie; the app cannot, because one app serves many companies' sites. Instead:

- **Sign in** (`sign_in`) checks the email and password the way Frappe's own login does (lockouts after failed tries,
  disabled users) and returns a long random token for this phone. Only its SHA-256 is stored, in a Techy Device row.
- **Each request** carries the token in the `X-Techy-Device` header. `authenticate` (an auth hook, run before
  customer_accounts.guard) signs the request in as the device's user. A revoked device or a disabled user gets a
  401, and the app asks the person to sign in again.
- **Images and PDFs** cannot send a header from an <img> or the phone's browser, so the app signs those links itself:
  `?_td=<device>&_te=<expiry>&_ts=<HMAC-SHA256(key=sha256(token), "<path?query>|<expiry>")>`. The server knows the
  key (the stored hash), so it can check the signature without ever having the token. Signed links work only for
  GET, only for private files and the download methods in SIGNED_METHODS, and expire after SIGNED_HOURS.
- **Signing out**: the app calls `sign_out`; a manager ticks Signed Out on the Techy Device in Desk (a lost phone).
"""
import hashlib
import hmac
import time

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, time_diff_in_seconds

DOCTYPE = "Techy Device"
HEADER = "X-Techy-Device"
SIGNED_HOURS = 24
SEEN_EVERY = 600  # seconds between Last Seen updates
SIGNED_METHODS = {
    "projectit.service_report.download",
    "projectit.investigations.download",
    "projectit.monthly_report.download",
    "projectit.reports.export",
    "projectit.customer_reports.export",
    "projectit.plant.report",
    "projectit.plant.monthly_report",
}


def _hash(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def _signature(key, path, expires):
    return hmac.new(str(key).encode(), f"{path}|{expires}".encode(), hashlib.sha256).hexdigest()


def _active(filters):
    row = frappe.db.get_value(DOCTYPE, {**filters, "revoked": 0}, ["name", "user", "token_hash", "last_seen"], as_dict=True)
    if row and frappe.db.get_value("User", row.user, "enabled"):
        return row


def _signed_in_as(device):
    frappe.set_user(device.user)
    frappe.local.techy_device = device.name


def _refused():
    raise frappe.AuthenticationError(_("You were signed out on this phone. Sign in again."))


def authenticate():
    """auth_hooks: a request from the phone app, by its device token or a signed link (see the module docstring)."""
    request = getattr(frappe.local, "request", None)
    if not request or (frappe.session.user or "Guest") != "Guest":
        return
    token = request.headers.get(HEADER)
    if token:
        device = _active({"token_hash": _hash(token)})
        if not device:
            _refused()
        _signed_in_as(device)
        if request.method == "POST" and (not device.last_seen
                or time_diff_in_seconds(now_datetime(), device.last_seen) > SEEN_EVERY):
            frappe.db.set_value(DOCTYPE, device.name, "last_seen", now_datetime(), update_modified=False)
        return
    if request.args.get("_td"):
        _check_signed(request)


def _check_signed(request):
    args = request.args
    path = request.path or ""
    method = path[len("/api/method/"):] if path.startswith("/api/method/") else None
    if request.method != "GET" or not (path.startswith("/private/files/") or method in SIGNED_METHODS):
        _refused()
    try:
        expires = int(args.get("_te") or 0)
    except ValueError:
        expires = 0
    now = int(time.time())
    if not now < expires <= now + SIGNED_HOURS * 3600 + 300:
        raise frappe.AuthenticationError(_("This link has expired. Open it again from the app."))
    device = _active({"name": args.get("_td")})
    if not device:
        _refused()
    query = (request.query_string or b"").decode()
    query = query[:query.find("_td=")].rstrip("&") if "_td=" in query else query
    signed = path + (f"?{query}" if query else "")
    if not hmac.compare_digest(_signature(device.token_hash, signed, expires), str(args.get("_ts") or "")):
        _refused()
    _signed_in_as(device)


# Endpoints -----------------------------------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def hello():
    """What the app shows after someone types the company's address: proof it is a Techy site, and whose."""
    from projectit import __version__
    logo = frappe.db.get_single_value("Navbar Settings", "app_logo") or ""
    return {
        "app": "techy",
        "version": __version__,
        "company": frappe.db.get_single_value("Global Defaults", "default_company") or frappe.local.site,
        "logo": frappe.utils.get_url(logo) if logo else "",
    }


def _check_password(usr, pwd):
    """The user's name if the password is right, with Frappe's lockout after repeated failures."""
    from frappe.core.doctype.user.user import User
    tracker = None
    try:
        from frappe.auth import get_login_attempt_tracker
        tracker = get_login_attempt_tracker(usr)
    except ImportError:
        pass
    if tracker and not tracker.is_user_allowed():
        frappe.throw(_("Too many failed sign-ins. Try again later."), frappe.AuthenticationError)
    user = User.find_by_credentials(usr, pwd)
    if not user or not user.get("is_authenticated"):
        if tracker:
            tracker.add_failure_attempt()
        frappe.throw(_("Incorrect email or password."), frappe.AuthenticationError)
    if tracker:
        tracker.add_success_attempt()
    return user["name"]


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=300)
def sign_in(usr, pwd, device_name=None, platform=None, app_version=None):
    """Sign this phone in; returns its token (shown once, never stored here in plain)."""
    user = _check_password(str(usr or "").strip(), str(pwd or ""))
    try:
        from frappe.twofactor import should_run_2fa
        if should_run_2fa(user):
            frappe.throw(_("Two-factor sign-in is not available in the phone app yet. Ask your manager to turn it off for you."))
    except ImportError:
        pass
    token = frappe.generate_hash(length=48)
    doc = frappe.get_doc({
        "doctype": DOCTYPE, "user": user, "token_hash": _hash(token),
        "device_name": str(device_name or "Phone")[:140], "platform": str(platform or "")[:40],
        "app_version": str(app_version or "")[:40], "signed_in": now_datetime(), "last_seen": now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    info = frappe.db.get_value("User", user, ["full_name", "user_type"], as_dict=True)
    return {"token": token, "device": doc.name, "user": user, "full_name": info.full_name, "user_type": info.user_type}


@frappe.whitelist(methods=["POST"])
def sign_out():
    """Sign this phone out (the app forgets its token too)."""
    name = getattr(frappe.local, "techy_device", None)
    if name:
        frappe.db.set_value(DOCTYPE, name, "revoked", 1)
    return {"ok": True}


@frappe.whitelist()
def my_devices():
    """The phones signed in as me, newest first."""
    current = getattr(frappe.local, "techy_device", None)
    rows = frappe.get_all(DOCTYPE, filters={"user": frappe.session.user, "revoked": 0},
        fields=["name", "device_name", "platform", "signed_in", "last_seen"], order_by="last_seen desc",
        limit_page_length=50)
    for row in rows:
        row["current"] = row.name == current
    return rows


@frappe.whitelist(methods=["POST"])
def sign_out_device(name):
    """Sign out one of my own phones (one I lost, say)."""
    if frappe.db.get_value(DOCTYPE, name, "user") != frappe.session.user:
        frappe.throw(_("That is not one of your devices."), frappe.PermissionError)
    frappe.db.set_value(DOCTYPE, name, "revoked", 1)
    return my_devices()


def on_user_update(doc, method=None):
    """A disabled user is signed out of every phone (requests are refused anyway; this keeps Desk honest)."""
    if not doc.enabled and doc.has_value_changed("enabled"):
        frappe.db.set_value(DOCTYPE, {"user": doc.name, "revoked": 0}, "revoked", 1)
