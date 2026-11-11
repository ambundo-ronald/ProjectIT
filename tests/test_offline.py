"""Contract tests for timer changes sent late by a phone that was offline."""
import importlib
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase


class OfflineTimerTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.t = importlib.import_module("projectit.timer")
        self.t._finished = MagicMock(side_effect=lambda name, changes: changes)
        self.t.logged_total = MagicMock(return_value=0)
        self.t._job = MagicMock(return_value=Dict(name="TASK-1", status="Working", save=MagicMock()))
        self.wo._workflow = MagicMock(return_value=None)

    def test_phone_time_used_within_limits(self):
        now = datetime(2026, 10, 11, 9)
        self.assertEqual(self.t._at("2026-10-11 07:15:00"), datetime(2026, 10, 11, 7, 15))  # offline since 07:15
        self.assertEqual(self.t._at("2026-10-11T09:03"), now)  # a phone clock a little fast: now
        self.assertEqual(self.t._at("2026-10-12 09:00:00"), now)  # far future: now
        self.assertEqual(self.t._at("2026-10-01 09:00:00"), now)  # more than three days back: now
        self.assertEqual(self.t._at("not a time"), now)
        self.assertEqual(self.t._at(None), now)

    def test_start_and_stop_use_the_phone_times(self):
        self.t._running = MagicMock(return_value=[])
        self.t.start("TASK-1", at="2026-10-11 07:00:00")
        self.assertEqual(self.frappe.get_doc.call_args.args[0]["started_at"], datetime(2026, 10, 11, 7))
        entry = Dict(name="L1", work_order="TASK-1", user="tech@example.com", started_at="2026-10-11 07:00:00")
        self.t._running = MagicMock(return_value=[entry])
        self.t.stop("TASK-1", at="2026-10-11 08:30:00")
        self.frappe.db.set_value.assert_called_with("Techy Time Log", "L1",
            {"ended_at": datetime(2026, 10, 11, 8, 30), "hours": 1.5})

    def test_a_stop_never_ends_before_the_start(self):
        self.t._close(Dict(name="L1", started_at="2026-10-11 08:00:00"), "2026-10-11 07:00:00")
        self.frappe.db.set_value.assert_called_with("Techy Time Log", "L1",
            {"ended_at": datetime(2026, 10, 11, 8), "hours": 0.0})


if __name__ == "__main__":
    unittest.main()


class OfflineOnMyWayTests(OpsTestCase):
    """An On my way tapped without signal: the phone's time, and no stale message to the customer."""

    def setUp(self):
        super().setUp()
        import sys
        self.notify = MagicMock()
        sys.modules["projectit.customer_notify"] = self.notify
        import projectit
        projectit.customer_notify = self.notify
        self.addCleanup(sys.modules.pop, "projectit.customer_notify", None)
        self.doc = Dict(name="TASK-1", status="Open", custom_equipment="EQ-1", custom_customer="C-1",
            db_set=MagicMock(), add_comment=MagicMock())
        self.doc.get = lambda key, default=None: self.doc[key] if key in self.doc else default
        self.wo._work_order = MagicMock(return_value=self.doc)
        self.wo._assignees = MagicMock(return_value={"TASK-1": ["tech@example.com"]})
        self.wo.get_work_order = MagicMock(return_value={})

    def test_recent_offline_tap_uses_phone_time_and_tells_customer(self):
        self.wo.on_my_way("TASK-1", 30, at="2026-10-11 08:40:00")  # now is 09:00
        self.assertEqual(self.doc.db_set.call_args.args[0]["custom_on_way_at"], datetime(2026, 10, 11, 8, 40))
        self.notify.on_the_way.assert_called_once()

    def test_late_offline_tap_is_recorded_without_messaging(self):
        self.wo.on_my_way("TASK-1", 30, at="2026-10-11 07:30:00")
        self.assertEqual(self.doc.db_set.call_args.args[0]["custom_on_way_at"], datetime(2026, 10, 11, 7, 30))
        self.notify.on_the_way.assert_not_called()
        self.assertIn("not messaged", self.doc.add_comment.call_args.args[1])

    def test_online_tap_tells_customer(self):
        self.wo.on_my_way("TASK-1", 15)
        self.notify.on_the_way.assert_called_once()
