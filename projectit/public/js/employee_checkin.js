frappe.ui.form.on("Employee Checkin", {
  async refresh(frm) {
    // HRMS hides location fields unless HR Settings geolocation tracking is on. Techy App punches always
    // record GPS, so show their coordinates and map without enabling HRMS geofencing for everyone.
    if (!frm.doc.custom_timesheet || !frm.doc.latitude) return;
    // Wait for HRMS's own refresh (which awaits the same setting) before un-hiding.
    await frappe.db.get_single_value("HR Settings", "allow_geolocation_tracking");
    setTimeout(() => {
      frm.toggle_display(["latitude", "longitude", "geolocation"], true);
      frm.toggle_display("fetch_geolocation", false);
    }, 0);
  },
});
