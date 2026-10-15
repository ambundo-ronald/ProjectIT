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
