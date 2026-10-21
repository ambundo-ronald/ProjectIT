"""Contract tests for filters and chemicals: when a change is due, stock, and recording changes."""
import importlib
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase


class SupplyTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.frappe.utils.escape_html = lambda v: v
        self.s = importlib.import_module("projectit.supplies")
        self.s.add_days = lambda value, days: date.fromordinal(date.fromisoformat(str(value)[:10]).toordinal() + days)
        self.s.getdate = lambda v=None: date.fromisoformat(str(v)[:10]) if v else date(2026, 10, 21)
        self.s.nowdate = lambda: "2026-10-21"
        self.s.now_datetime = lambda: datetime(2026, 10, 21, 9)

    def row(self, **extra):
        r = Dict(name="S1", supply_name="Cartridge filters", kind="Filter", unit="pcs", change_every_days=30, per_change=2,
            stock=6, reorder_at=2, order_qty=10, last_changed_on="2026-09-23 10:00:00", ordered_on=None, item_code="PF-5")
        r.update(extra)
        return r

    def test_due_soon_and_low(self):
        st = self.s.state(self.row())
        self.assertEqual((str(st["due_on"]), st["days_left"], st["soon"], st["due"], st["low"]), ("2026-10-23", 2, True, False, False))
        self.assertTrue(self.s.state(self.row(last_changed_on="2026-09-01"))["due"])
        self.assertTrue(self.s.state(self.row(stock=2))["low"])
        self.assertIsNone(self.s.state(self.row(change_every_days=0))["due_on"])  # no schedule, never due
        self.assertFalse(self.s.state(self.row(reorder_at=None, stock=0))["low"])  # no reorder level, never low

    def recorded(self, action, qty=None, **extra):
        row = self.row(**extra)
        self.frappe.db.get_value = MagicMock(side_effect=[None, row, row])
        self.frappe.get_doc = MagicMock()
        self.s.state = lambda r: r
        plant = importlib.import_module("projectit.plant")
        plant.queue_status = MagicMock()
        self.s.record("EQ-1", "S1", action, qty)
        return self.frappe.db.set_value.call_args.args[2]

    def test_a_change_uses_the_usual_amount_and_restarts_the_clock(self):
        values = self.recorded("Changed")
        self.assertEqual(values["stock"], 4)
        self.assertEqual(values["last_changed_on"], datetime(2026, 10, 21, 9))

    def test_stock_never_goes_below_zero(self):
        self.assertEqual(self.recorded("Refilled", 5, stock=1)["stock"], 0)

    def test_a_delivery_adds_stock_and_closes_the_order(self):
        values = self.recorded("Received", 10, ordered_on="2026-10-20")
        self.assertEqual((values["stock"], values["ordered_on"]), (16, None))
        self.assertNotIn("last_changed_on", values)

    def test_a_count_sets_the_stock(self):
        self.assertEqual(self.recorded("Counted", 3)["stock"], 3)

    def test_refill_needs_an_amount(self):
        with self.assertRaises(Exception):
            self.recorded("Refilled")


if __name__ == "__main__":
    unittest.main()
