"""Idempotent setup of app-owned access fields; preserves employee assignments."""
import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Exact legacy export only: never remove a site's independently customized layout.
LEGACY_EMPLOYEE_ORDER = ['basic_details_tab', 'basic_information', 'employee', 'naming_series', 'first_name', 'middle_name', 'last_name', 'employee_name', 'column_break_9', 'gender', 'date_of_birth', 'salutation', 'column_break1', 'date_of_joining', 'image', 'status', 'erpnext_user', 'user_id', 'create_user', 'create_user_permission', 'company_details_section', 'company', 'department', 'employment_type', 'employee_number', 'column_break_25', 'designation', 'reports_to', 'column_break_18', 'branch', 'grade', 'section_break_dtuf', 'mobile_module', 'employment_details', 'job_applicant', 'scheduled_confirmation_date', 'column_break_32', 'final_confirmation_date', 'contract_end_date', 'col_break_22', 'notice_number_of_days', 'date_of_retirement', 'contact_details', 'cell_number', 'column_break_40', 'personal_email', 'company_email', 'column_break4', 'prefered_contact_email', 'prefered_email', 'unsubscribed', 'address_section', 'current_address', 'current_accommodation_type', 'column_break_46', 'permanent_address', 'permanent_accommodation_type', 'emergency_contact_details', 'person_to_be_contacted', 'column_break_55', 'emergency_phone_number', 'column_break_19', 'relation', 'attendance_and_leave_details', 'attendance_device_id', 'column_break_44', 'holiday_list', 'default_shift', 'approvers_section', 'expense_approver', 'leave_approver', 'column_break_45', 'shift_request_approver', 'salary_information', 'ctc', 'salary_currency', 'salary_mode', 'salary_cb', 'payroll_cost_center', 'pan_number', 'provident_fund_account', 'bank_details_section', 'bank_name', 'column_break_heye', 'bank_ac_no', 'bank_cb', 'ifsc_code', 'micr_code', 'iban', 'personal_details', 'marital_status', 'family_background', 'column_break6', 'blood_group', 'health_details', 'health_insurance_section', 'health_insurance_provider', 'health_insurance_no', 'passport_details_section', 'passport_number', 'valid_upto', 'column_break_73', 'date_of_issue', 'place_of_issue', 'profile_tab', 'bio', 'educational_qualification', 'education', 'previous_work_experience', 'external_work_history', 'history_in_company', 'internal_work_history', 'exit', 'resignation_letter_date', 'relieving_date', 'exit_interview_details', 'held_on', 'new_workplace', 'column_break_99', 'leave_encashed', 'encashment_date', 'feedback_section', 'reason_for_leaving', 'column_break_104', 'feedback', 'lft', 'rgt', 'old_parent', 'connections_tab']


def ensure_access_fields():
    """Run on installation/migration, or via bench execute for an existing site."""
    if "projectit" not in frappe.get_installed_apps():
        frappe.throw("Install Techy App (projectit) on this site before repairing its fields.")
    for doctype in ("Mobile Module", "Mobile Module Item"):
        if not frappe.db.exists("DocType", doctype):
            frappe.throw("Techy App DocTypes are missing. Run bench migrate before repairing access fields.")

    # The old v15 full-form export referenced field names that never matched the
    # installed custom fields. Let v16's native layout and insert_after place them.
    name = "Employee-main-field_order"
    if frappe.db.exists("Property Setter", name):
        setter = frappe.get_doc("Property Setter", name)
        try:
            old_order = json.loads(setter.value)
        except (TypeError, ValueError):
            old_order = None
        if setter.module == "Projectit" and old_order == LEGACY_EMPLOYEE_ORDER:
            frappe.delete_doc("Property Setter", name, ignore_permissions=True)

    fixture = Path(__file__).parent / "fixtures" / "custom_field.json"
    definitions = json.loads(fixture.read_text(encoding="utf-8"))
    custom_fields = {}
    allowed = {"fieldname", "fieldtype", "label", "insert_after", "options", "description", "module", "default",
        "depends_on", "collapsible", "read_only", "no_copy", "in_standard_filter", "search_index"}
    for definition in definitions:
        custom_fields.setdefault(definition["dt"], []).append({
            key: definition[key] for key in allowed if key in definition
        })
    create_custom_fields(custom_fields, update=True)

    for module in ("WorkIT", "ManageIT"):
        if not frappe.db.exists("Mobile Module Item", module):
            frappe.get_doc({"doctype": "Mobile Module Item", "module": module}).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Employee")
    frappe.clear_cache(doctype="Employee Checkin")
    return "Techy App access fields and module choices are ready. Reload the Employee form."


def ensure_ops_defaults():
    """Store Techy Ops Settings defaults once; never overwrite values a site has saved."""
    if not frappe.db.exists("DocType", "Techy Ops Settings"):
        return
    if frappe.db.get_single_value("Techy Ops Settings", "pm_lead_days") is None:
        frappe.db.set_single_value("Techy Ops Settings", "pm_lead_days", 3)
    if not frappe.db.exists("Mobile Module Item", "Ops"):
        frappe.get_doc({"doctype": "Mobile Module Item", "module": "Ops"}).insert(ignore_permissions=True)


# Task rights the Techy apps need, narrowed to each person's own work by projectit.permissions. Never delete.
TASK_RIGHTS = {"Maintenance User": ("read", "write", "create", "report", "print"),
    "Employee": ("read", "write", "report", "print")}
# Read the projects they are allocated to (narrowed by projectit.permissions.project_query).
PROJECT_RIGHTS = {"Maintenance User": ("read",), "Employee": ("read",)}


def ensure_task_permissions():
    """Give technicians and field staff Task access (only ever adds rights; a site's other changes are kept)."""
    from frappe.permissions import add_permission, update_permission_property
    for doctype, grants in (("Task", TASK_RIGHTS), ("Project", PROJECT_RIGHTS)):
        for role, rights in grants.items():
            if not frappe.db.exists("Role", role):
                continue
            add_permission(doctype, role, 0)
            row = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
                list(rights), as_dict=True) or {}
            for right in rights:
                if not row.get(right):
                    update_permission_property(doctype, role, 0, right, 1)
