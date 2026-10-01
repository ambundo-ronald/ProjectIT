frappe.ui.form.on("Project", {
  refresh(frm) {
    if (frm.is_new()) return;
    frm.add_custom_button(
      __("Project Tasks"),
      () => {
        frappe.set_route("List", "Task", { project: frm.doc.name });
      },
      __("Techy App"),
    );
    if (frappe.model.can_create("Task")) {
      frm.add_custom_button(
        __("New Task"),
        () => {
          frappe.new_doc("Task", { project: frm.doc.name });
        },
        __("Techy App"),
      );
      frm.add_custom_button(
        __("New Checklist"),
        () => {
          frappe.new_doc("Task", { project: frm.doc.name, is_group: 1 });
        },
        __("Techy App"),
      );
    }

    frm.add_custom_button(
      "Allocation and Instructions",
      () => {
        frappe.db
          .get_list("Project Allocation and Instrucions", {
            filters: { project: frm.doc.name },
          })
          .then((data) => {
            if (data.length) {
              frappe.set_route(
                "Form",
                "Project Allocation and Instrucions",
                data[0].name,
              );
            }
          });
      },
      "Actions",
    );
  },
});
