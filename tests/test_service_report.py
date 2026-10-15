"""Contract tests for customer service reports: recipients, who may send, automatic email and answers."""
import importlib
import unittest
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


class ServiceReportTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.sr = importlib.import_module("projectit.service_report")
        self.sr.customer_emails = MagicMock(return_value=["facilities@seaview.test", "gm@seaview.test"])
        self.job = Dict(name="TASK-1", subject="Quarterly service", custom_customer="Seaview")

    def test_defaults_to_the_customers_first_address(self):
        self.assertEqual(self.sr._recipients(self.job, None), ["facilities@seaview.test"])

    def test_technicians_send_only_to_addresses_on_file(self):
        self.assertEqual(self.sr._recipients(self.job, "GM@seaview.test, facilities@seaview.test"),
            ["gm@seaview.test", "facilities@seaview.test"])
        with self.assertRaises(PermissionError):
            self.sr._recipients(self.job, ["me@gmail.test"])

    def test_managers_may_add_recipients(self):
        self.frappe.get_roles.return_value = ["Maintenance Manager"]
        self.assertEqual(self.sr._recipients(self.job, '["owner@seaview-group.test"]'), ["owner@seaview-group.test"])

    def test_invalid_or_missing_addresses(self):
        self.frappe.get_roles.return_value = ["Maintenance Manager"]
        with self.assertRaises(ValidationError):
            self.sr._recipients(self.job, ["not-an-email"])
        self.sr.customer_emails.return_value = []
        with self.assertRaises(ValidationError) as raised:
            self.sr._recipients(self.job, [])
        self.assertIn("has no email address", str(raised.exception))
        with self.assertRaises(ValidationError):
            self.sr._recipients(self.job, [f"a{i}@x.test" for i in range(11)])

    def test_only_customer_jobs_are_emailed(self):
        self.sr._job = MagicMock(return_value=Dict(name="TASK-2", custom_customer=None))
        with self.assertRaises(ValidationError):
            self.sr.email_report("TASK-2")

    def test_people_who_cannot_work_the_job_cannot_send(self):
        self.sr._job = MagicMock(return_value=self.job)
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError):
            self.sr.email_report("TASK-1")

    def test_automatic_email_follows_the_setting(self):
        self.frappe.db.get_single_value.return_value = 0
        self.sr.on_completed(self.job)
        self.frappe.enqueue.assert_not_called()
        self.frappe.db.get_single_value.return_value = 1
        self.sr.on_completed(Dict(name="TASK-3", custom_customer=None))
        self.frappe.enqueue.assert_not_called()  # internal jobs have no customer to send to
        self.sr.on_completed(self.job)
        self.frappe.enqueue.assert_called_once_with("projectit.service_report.auto_email", name="TASK-1",
            enqueue_after_commit=True)

    def test_answers_read_well(self):
        self.assertEqual(self.sr._answer({"field_type": "Checkbox", "value": "1"}), "Done")
        self.assertEqual(self.sr._answer({"field_type": "Checkbox", "value": ""}), "—")
        self.assertEqual(self.sr._answer({"field_type": "Number", "value": "17", "unit": "ppm"}), "17 ppm")
        self.assertEqual(self.sr._answer({"field_type": "Pass/Fail", "value": "Pass"}), "Pass")


if __name__ == "__main__":
    unittest.main()
