"""Fill the Desk map field on existing Techy App check-ins that only stored latitude/longitude."""
import frappe

from projectit.attendance import _geolocation


def execute():
    rows = frappe.get_all("Employee Checkin", filters={"custom_timesheet": ["is", "set"],
        "latitude": ["is", "set"], "longitude": ["is", "set"], "geolocation": ["is", "not set"]},
        fields=["name", "latitude", "longitude"], limit_page_length=0)
    for row in rows:
        frappe.db.set_value("Employee Checkin", row.name, "geolocation",
            _geolocation(row.latitude, row.longitude), update_modified=False)
