frappe.ui.form.on("Task", {
  refresh(frm) {
    if (frm.is_new() || !frm.doc.project || frm.doc.is_template) return;
    frm.add_custom_button(
      __("Checklist Steps"),
      () => {
        frappe.set_route("List", "Task", { parent_task: frm.doc.name });
      },
      __("Techy App"),
    );
    if (frm.doc.is_group && frappe.model.can_create("Task")) {
      frm.add_custom_button(
        __("Add Checklist Step"),
        () => {
          frappe.new_doc("Task", {
            project: frm.doc.project,
            parent_task: frm.doc.name,
          });
        },
        __("Techy App"),
      );
    }
    frm.add_custom_button(
      __("Open in Techy App"),
      () => {
        const manager = frappe.user_roles.some((role) =>
          ["Projects Manager", "System Manager"].includes(role),
        );
        const section = manager ? "manageit" : "workit";
        window.open(
          `/techy-app/${section}/tasks?task=${encodeURIComponent(frm.doc.name)}`,
          "_blank",
          "noopener",
        );
      },
      __("Techy App"),
    );
  },
});
