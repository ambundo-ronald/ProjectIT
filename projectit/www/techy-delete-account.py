"""Asking for a Techy account to be deleted (/techy-delete-account): the Play Store listing links here."""
import frappe
from frappe.sessions import get_csrf_token

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.local.site
    # A signed-in visitor's request needs the session's CSRF token; a guest's does not.
    context.csrf = get_csrf_token() if frappe.session.user != "Guest" else ""
    return context
