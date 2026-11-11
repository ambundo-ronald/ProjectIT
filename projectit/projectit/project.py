import frappe

def after_insert_of_project(doc, event):
    """Every project gets its crew and instructions record, empty. The system makes it, so anyone allowed to create a
    project can (a salesperson, a Projects User), not only the project managers who later fill in the crew."""
    if frappe.db.exists("Project Allocation and Instrucions", {"project": doc.name}):
        return
    pai = frappe.new_doc("Project Allocation and Instrucions")
    pai.project = doc.name
    pai.flags.ignore_permissions = True
    pai.flags.created_with_project = True
    pai.insert()