"""Contract tests for customer ratings: the private link, what a customer may submit, and who is told."""
import importlib
import unittest
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase


def task(**extra):
    row = Dict(name="TASK-1", subject="Fix leak", status="Completed", custom_work_order=1, custom_customer="CUST-1",
        custom_rating_key="k" * 24, custom_completed_at="2026-10-10 12:00:00", modified="2026-10-10 12:00:00",
        custom_equipment=None, custom_rating=0, custom_rating_comment=None, custom_rated_on=None, company="Techy")
    row.update(extra)
    return row


class RatingTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.ratings = importlib.import_module("projectit.ratings")
        self.frappe.session.user = "Guest"
        self.frappe.get_doc.return_value = MagicMock()
        wo = importlib.import_module("projectit.work_orders")
        patcher = patch.object(wo, "_assignees", MagicMock(return_value={"TASK-1": ["tina@x.com"]}))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_wrong_key_or_unfinished_job_is_refused(self):
        for row, key in ((task(), "wrong"), (task(), ""), (task(status="Working"), "k" * 24), (None, "k" * 24),
                (task(custom_customer=None), "k" * 24)):
            self.frappe.db.get_value.return_value = row
            with self.assertRaises(PermissionError):
                self.ratings.submit("TASK-1", key, 5)
        self.frappe.db.set_value.assert_not_called()

    def test_submit_stores_and_notes_the_rating(self):
        self.frappe.db.get_value.return_value = task()
        with patch.object(self.ratings.ops, "notify") as notify:
            self.ratings.submit("TASK-1", "k" * 24, "5", "Quick and tidy")
        values = self.frappe.db.set_value.call_args.args[2]
        self.assertEqual((values["custom_rating"], values["custom_rating_comment"]), (5, "Quick and tidy"))
        self.assertEqual(notify.call_args.args[0], ["tina@x.com"])

    def test_stars_must_be_one_to_five(self):
        self.frappe.db.get_value.return_value = task()
        for stars in (0, 6, "x"):
            with self.assertRaises(Exception):
                self.ratings.submit("TASK-1", "k" * 24, stars)

    def test_low_rating_tells_managers(self):
        self.frappe.db.get_value.return_value = task()
        meters = importlib.import_module("projectit.meters")
        with patch.object(self.ratings.ops, "notify") as notify, patch.object(meters, "_managers", return_value=["boss@x.com"]):
            self.ratings.submit("TASK-1", "k" * 24, 2)
        self.assertEqual(notify.call_args.args[0], ["tina@x.com", "boss@x.com"])

    def test_ratings_close_after_30_days(self):
        self.frappe.db.get_value.return_value = task(custom_completed_at="2026-09-01 12:00:00")
        with self.assertRaises(Exception) as caught:
            self.ratings.submit("TASK-1", "k" * 24, 4)
        self.assertIn("closed", str(caught.exception))

    def test_scorecard_counts_ratings(self):
        reports = importlib.import_module("projectit.reports")
        from test_reports import TODAY, job
        from datetime import date
        self.frappe.get_cached_value = MagicMock(return_value=None)
        jobs = [job(n, "Completed", "Preventive", completed="2026-10-05 10:00:00") for n in "ABC"]
        for j, stars in zip(jobs, (5, 4, 0)):
            j.custom_rating = stars
        rows = reports.by_technician(jobs, {n: ["tina@x.com"] for n in "ABC"}, date(2026, 10, 1), TODAY, TODAY)
        self.assertEqual((rows[0]["rating"], rows[0]["ratings"]), (4.5, 2))
        # Only "not sent back" (100) and the rating (90) apply: (20 x 100 + 20 x 90) / 40
        self.assertEqual(rows[0]["score"], 95)


if __name__ == "__main__":
    unittest.main()
