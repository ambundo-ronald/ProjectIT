"""Contract tests for the monthly plant report: the month, and what we recommend."""
import importlib
import unittest
from datetime import date

from test_ops import Dict, OpsTestCase


class MonthlyReportTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.r = importlib.import_module("projectit.monthly_report")
        self.r.getdate = lambda v=None: date.fromisoformat(str(v)[:10]) if v else date(2026, 10, 21)
        self.r.nowdate = lambda: "2026-10-21"
        self.frappe.utils.format_date = lambda v, fmt=None: str(v)

    def test_month_range(self):
        self.assertEqual(self.r.month_range("2026-02")[:2], (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(self.r.month_range()[:2], (date(2026, 9, 1), date(2026, 9, 30)))  # last month by default
        with self.assertRaises(Exception):
            self.r.month_range("2026-11")  # not started yet
        with self.assertRaises(Exception):
            self.r.month_range("soon")

    def machine(self, **extra):
        m = {"membranes": None, "expected": 30, "logged": 30, "supplies": [], "visits": [], "repairs": 0}
        m.update(extra)
        return m

    def test_nothing_to_recommend_for_a_well_run_plant(self):
        row = Dict(warranty_until="2027-06-01", contract_until="2027-06-01")
        self.assertEqual(self.r.recommend(self.machine(), row), [])

    def test_recommendations(self):
        row = Dict(warranty_until="2026-11-15", contract_until=None)
        m = self.machine(membranes={"needs_cleaning": True}, logged=12, repairs=2, supplies=[
            {"name": "Cartridge filters", "due": True, "low": False, "stock": 4, "unit": "pcs"},
            {"name": "Antiscalant", "due": False, "low": True, "stock": 1.5, "unit": "L"}])
        tips = " | ".join(self.r.recommend(m, row))
        for words in ("Clean the membranes", "12 of 30 logged", "Change the cartridge filters", "Order more antiscalant",
                "warranty ends on 2026-11-15", "service contract with regular visits"):
            self.assertIn(words, tips)


if __name__ == "__main__":
    unittest.main()
