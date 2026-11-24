"""The Android app's side of the website: updates, links that open the app, and Play Store pages.

- **Updates.** Play updates the app on its own (and the app asks for an update through Play's in-app update screen,
  see mobile/src/data/updates.js). MIN_APP_VERSION is the oldest app this server still works with: raise it when a
  server change needs a newer app, and phones older than that are asked to update before they carry on.
- **Links open the app.** Android opens links to this site's /techy-app in the installed app instead of the browser
  once it has checked /.well-known/assetlinks.json (Android App Links). That file lists the app and the SHA-256
  fingerprints of its signing keys, set in Techy Ops Settings → Android App Fingerprints. Other links (and typing
  the address in Chrome) show an *Open in the app* bar instead (mobile/src/components/OpenInApp.vue).
- **Play Store pages.** /techy-privacy (the privacy policy) and /techy-delete-account (asking for an account to be
  deleted, also from inside the app) are plain pages Play's reviewers and users can open without signing in.
"""
import json

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, validate_email_address
from werkzeug.wrappers import Response

ANDROID_PACKAGE = "com.techyapp.field"
# The oldest phone app this server works with. Raise it (and say why) when the server needs a newer app.
MIN_APP_VERSION = "1.0.0"
PLAY_URL = f"https://play.google.com/store/apps/details?id={ANDROID_PACKAGE}"
ASSET_LINKS = ".well-known/assetlinks.json"


def _setting(field):
    return frappe.db.get_single_value("Techy Ops Settings", field)


def app_info():
    """What hello() tells the phone app and the website about the Android app."""
    url = _setting("android_app_url")
    return {"android_package": ANDROID_PACKAGE, "min_app_version": MIN_APP_VERSION, "play_url": url or PLAY_URL,
        # The website offers "Open in the app" only once the company has set its Android App Link.
        "android_app": bool(url)}


def fingerprints():
    """SHA-256 signing-key fingerprints from Techy Ops Settings, as AA:BB:… (one per line, spaces and case ignored)."""
    out = []
    for line in str(_setting("android_app_fingerprints") or "").replace(",", "\n").splitlines():
        value = line.strip().upper().replace(" ", "")
        if len(value.replace(":", "")) == 64 and all(c in "0123456789ABCDEF:" for c in value):
            if ":" not in value:
                value = ":".join(value[i:i + 2] for i in range(0, 64, 2))
            out.append(value)
    return out


def asset_links():
    keys = fingerprints()
    if not keys:
        return []
    return [{"relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": ANDROID_PACKAGE, "sha256_cert_fingerprints": keys}}]


def serve_asset_links():
    """before_request hook: answer /.well-known/assetlinks.json. Frappe sends every other /.well-known/ request to its
    own OAuth handler before page renderers run, so this cannot be a page; raising an HTTPException that carries the
    response is how a hook answers a request early."""
    request = getattr(frappe.local, "request", None)
    if not request or request.method not in ("GET", "HEAD") or request.path.strip("/") != ASSET_LINKS:
        return
    from werkzeug.exceptions import HTTPException
    response = Response(json.dumps(asset_links(), indent=2), mimetype="application/json")
    response.headers["Cache-Control"] = "public, max-age=3600"
    raise HTTPException(response=response)


# Deleting an account ------------------------------------------------------------------------------------------

def _admins():
    return [u for u in frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"},
        pluck="parent", distinct=True) if u not in ("Administrator", "Guest")
        and frappe.db.get_value("User", u, "enabled")]


def _tell_admins(email, note, signed_in):
    company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.local.site
    subject = _("Account deletion request: {0}").format(email)
    body = _("<p>{0} asked for their Techy account and its personal data to be deleted ({1}).</p><p>{2}</p>"
        "<p>Disable the user in Desk, then delete or anonymise their personal data within 30 days. Records the law "
        "or the company must keep (invoices, attendance, work done) can be kept, without the person's contact "
        "details where possible.</p>").format(escape_html(email), _("signed in") if signed_in else _("from the website"),
        escape_html(note or _("No reason given.")))
    from projectit import ops
    ops.notify(_admins(), subject, "User", email)
    to = list(dict.fromkeys([_setting("support_email"), *_admins()]))
    to = [t for t in to if t]
    if to:
        try:
            frappe.sendmail(recipients=to, subject=f"{subject} – {company}", message=body, now=True)
        except Exception:
            frappe.log_error(title="Account deletion request email could not be sent")
    frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "User",
        "reference_name": email if frappe.db.exists("User", email) else "Administrator",
        "content": body}).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=3, seconds=3600)
def request_deletion(reason=None):
    """The signed-in person asks for their account to be deleted (Settings → Delete my account in the app)."""
    if frappe.session.user in ("Guest", "Administrator"):
        frappe.throw(_("Please sign in."), frappe.PermissionError)
    _tell_admins(frappe.session.user, str(reason or "")[:1000], True)
    return {"ok": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=3600)
def request_deletion_by_email(email, reason=None):
    """The same from /techy-delete-account, for someone who no longer has the app. The company confirms it is them."""
    email = str(email or "").strip().lower()
    if not validate_email_address(email):
        frappe.throw(_("Enter the email address you sign in with."))
    _tell_admins(email, str(reason or "")[:1000], False)
    # The same answer whether or not the account exists, so this cannot be used to find out who has one.
    return {"ok": True}
