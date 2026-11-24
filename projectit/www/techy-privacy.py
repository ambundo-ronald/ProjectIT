"""The Techy App privacy policy (/techy-privacy): the Play Store listing links here."""
import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.local.site
    context.contact = frappe.db.get_single_value("Techy Ops Settings", "support_email") or ""
    context.updated = "24 November 2026"
    return context
