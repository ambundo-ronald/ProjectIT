# Copyright (c) 2025, frappe.dev@arus.co.in and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Allocations decide who may check in to a project, so only these roles may change them,
# even if a site's Custom DocPerm grants write to others.
EDITORS = {"Projects Manager", "System Manager"}


def check_editor():
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch or frappe.session.user == "Administrator":
		return
	if not EDITORS & set(frappe.get_roles()):
		frappe.throw(_("Only project managers can change project crews and instructions."), frappe.PermissionError)


class ProjectAllocationandInstrucions(Document):
	def validate(self):
		check_editor()

	def on_trash(self):
		check_editor()
