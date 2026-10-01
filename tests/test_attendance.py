"""Unit-level contract tests; database/HRMS integration requires a Bench site."""
import importlib.util
import sys
import unittest
from datetime import datetime, time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


class ValidationError(Exception):
    pass


def fail(message, exception=ValidationError):
    raise exception(message)


def load_module():
    frappe = ModuleType("frappe")
    frappe.whitelist = lambda **kwargs: lambda fn: fn
    frappe._ = lambda text: text
    frappe.throw = fail
    frappe.PermissionError = PermissionError
    utils = ModuleType("frappe.utils")
    utils.get_datetime = lambda value: value if isinstance(value, datetime) else datetime.fromisoformat(value)
    utils.get_time = lambda value: value if isinstance(value, time) else time.fromisoformat(value)
    utils.now_datetime = lambda: datetime(2026,9,29,18)
    spec = importlib.util.spec_from_file_location("attendance_under_test", Path(__file__).resolve().parents[1] / "projectit/attendance.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"frappe": frappe, "frappe.utils": utils}):
        spec.loader.exec_module(module)
    return module


class AttendanceTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.frappe = self.module.frappe
        self.frappe.db = MagicMock()
        self.frappe.get_doc = MagicMock()
        self.frappe.get_all = MagicMock()
        self.frappe.get_single = MagicMock()
        self.frappe.get_cached_doc = MagicMock()
        self.frappe.session = SimpleNamespace(user="employee@example.com")
        self.employee = SimpleNamespace(name="EMP-1", company="Company")
        self.doc = MagicMock(name="timesheet")
        self.doc.name = "TS-1"
        self.doc.employee = "EMP-1"
        self.doc.parent_project = "PROJ-1"
        self.doc.docstatus = 0
        self.doc.note = ""
        self.frappe.get_doc.return_value = self.doc
        self.frappe.db.sql.return_value = [SimpleNamespace(name="IN-1", log_type="IN", time=datetime(2026,9,29,7))]
        self.settings = SimpleNamespace(start_time=time(8), end_time=time(17), regular_time_activity_type="Regular", over_time_activity_type="Overtime")
        self.settings.get = lambda field: getattr(self.settings, field)
        self.frappe.get_single.return_value = self.settings
        for name, value in [("_employee", self.employee), ("_photo", None), ("_punch", None), ("_summary", {"name":"TS-1"})]:
            mock = patch.object(self.module, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def checkout(self):
        return self.module.check_out("TS-1", 0, 0, "photo")

    def test_checkout_uses_final_server_time_not_first_segment_end(self):
        self.checkout()
        self.module._punch.assert_called_once_with("EMP-1", "TS-1", "OUT", datetime(2026,9,29,18), 0.0, 0.0)
        self.doc.check_permission.assert_any_call("submit")
        self.doc.submit.assert_called_once()
        segments = [call.args[1] for call in self.doc.append.call_args_list]
        self.assertEqual([r["activity_type"] for r in segments], ["Overtime","Regular","Overtime"])
        self.assertEqual(segments[-1]["to_time"], datetime(2026,9,29,18))

    def test_checkout_preserves_native_task_on_every_segment(self):
        self.doc.time_logs = [{"task": "TASK-1"}]
        self.checkout()
        self.assertTrue(all(call.args[1]["task"] == "TASK-1" for call in self.doc.append.call_args_list))

    def test_checkout_rejects_mixed_task_timesheets(self):
        self.doc.time_logs = [{"task": "TASK-1"}, {"task": "TASK-2"}]
        with self.assertRaises(ValidationError): self.checkout()
        self.doc.submit.assert_not_called()

    def test_cross_employee_checkout_denied(self):
        self.doc.employee = "EMP-OTHER"
        with self.assertRaises(PermissionError): self.checkout()
        self.doc.submit.assert_not_called()
        self.module._punch.assert_not_called()

    def test_duplicate_checkout_does_not_write_again(self):
        self.doc.docstatus = 1
        self.frappe.db.sql.return_value.append(SimpleNamespace(log_type="OUT", time=datetime(2026,9,29,18)))
        self.checkout()
        self.doc.submit.assert_not_called()
        self.module._punch.assert_not_called()
        self.module._photo.assert_not_called()

    def test_missing_in_log_rejected(self):
        self.frappe.db.sql.return_value = []
        with self.assertRaises(ValidationError): self.checkout()
        self.doc.submit.assert_not_called()

    def test_invalid_coordinates_do_not_write(self):
        for lat, lon in [(91,0),(0,181),(float("nan"),0),(0,float("inf")),(None,0)]:
            with self.assertRaises(ValidationError): self.module.check_out("TS-1",lat,lon,"photo")
        self.doc.submit.assert_not_called()

    def test_submit_error_propagates_before_punch(self):
        self.doc.submit.side_effect = ValidationError("Cannot submit")
        with self.assertRaises(ValidationError): self.checkout()
        self.module._punch.assert_not_called()

    def test_punch_error_propagates_for_request_rollback(self):
        self.module._punch.side_effect = ValidationError("Outside shift location")
        with self.assertRaises(ValidationError): self.checkout()
        self.module._photo.assert_not_called()
        # Actual transaction rollback must also be verified on a Frappe site.

    def test_photo_error_propagates_for_request_rollback(self):
        self.module._photo.side_effect = ValidationError("Invalid photo")
        with self.assertRaises(ValidationError): self.checkout()

    def test_missing_settings_rejected_before_submit(self):
        self.settings.regular_time_activity_type = None
        with self.assertRaises(ValidationError): self.checkout()
        self.doc.submit.assert_not_called()

    def test_retry_checkin_returns_existing_session(self):
        with patch.object(self.module, "_active_timesheet", return_value=self.doc):
            self.module.check_in("PROJ-1",0,0,"photo")
        self.module._punch.assert_not_called()
        self.module._photo.assert_not_called()

    def test_second_project_checkin_rejected(self):
        with patch.object(self.module, "_active_timesheet", return_value=self.doc):
            with self.assertRaises(ValidationError): self.module.check_in("PROJ-2",0,0,"photo")

    def test_unallocated_project_denied(self):
        self.doc.status = "Open"
        self.frappe.db.sql.return_value = []
        with patch.object(self.module, "_active_timesheet", return_value=None):
            with self.assertRaises(PermissionError): self.module.check_in("PROJ-1",0,0,"photo")
        self.doc.insert.assert_not_called()

    def test_pending_status_does_not_claim_present(self):
        log = SimpleNamespace(attendance=None, skip_auto_attendance=0, offshift=0, shift="Day", log_type="OUT", time=datetime(2026,9,29,18))
        self.frappe.get_all.side_effect = [[],[log]]
        self.frappe.get_cached_doc.return_value = SimpleNamespace(enable_auto_attendance=1, process_attendance_after="2026-01-01", last_sync_of_checkin=datetime(2026,9,29,17))
        result = self.module.get_attendance_status()
        self.assertIn("pending", result["message"])
        for call in self.frappe.get_all.call_args_list:
            self.assertEqual(call.kwargs["filters"]["employee"], "EMP-1")

    def test_offshift_prompts_hr_review(self):
        self.frappe.get_all.side_effect = [[],[SimpleNamespace(attendance=None,skip_auto_attendance=0,offshift=1,shift=None)]]
        self.assertIn("outside an assigned shift", self.module.get_attendance_status()["message"])


class EmployeeAccessTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.frappe = self.module.frappe
        self.frappe.session = SimpleNamespace(user="person@example.com")
        self.frappe.db = MagicMock()
        self.frappe.get_all = MagicMock(return_value=[SimpleNamespace(name="EMP-1",company="Company")])

    def test_guest_cannot_punch(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError): self.module._employee()
        self.frappe.get_all.assert_not_called()

    def test_unlinked_and_ambiguous_accounts_rejected(self):
        for employees in ([],[SimpleNamespace(name="EMP-1"),SimpleNamespace(name="EMP-2")]):
            self.frappe.get_all.return_value = employees
            with self.assertRaises(PermissionError): self.module._employee()

    def test_workit_module_required(self):
        self.frappe.db.exists.return_value = False
        with self.assertRaises(PermissionError): self.module._employee()

    def test_identity_comes_from_session_and_locks_employee(self):
        self.module._employee(lock=True)
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"], {"user_id":"person@example.com","status":"Active"})
        self.frappe.db.get_value.assert_called_once_with("Employee", "EMP-1", "name", for_update=True)


if __name__ == "__main__":
    unittest.main()
