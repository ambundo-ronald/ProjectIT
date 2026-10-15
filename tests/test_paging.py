"""Contract tests for numbered pages: totals, the requested slice in order, computed filters, page sizes."""
import unittest

from test_ops import Dict, OpsTestCase


class PagingTests(OpsTestCase):
    def test_page_and_total(self):
        names = [f"EQ-{i}" for i in range(1, 61)]

        def get_all(doctype, **kw):
            if kw.get("pluck") == "name":
                return names
            return [Dict(name=n) for n in reversed(kw["filters"]["name"][1])]
        self.frappe.get_all.side_effect = get_all
        rows, total = self.ops.paged("Techy Equipment", {}, None, "name asc", 25, 25, ["name"])
        self.assertEqual(total, 60)
        self.assertEqual([r.name for r in rows], names[25:50])

    def test_past_the_end_is_empty(self):
        self.frappe.get_all.return_value = ["EQ-1"]
        self.assertEqual(self.ops.paged("Techy Equipment", start=50, page_length=25), ([], 1))
        self.assertEqual(self.frappe.get_all.call_count, 1)  # no second read for an empty page

    def test_computed_filter_counts_only_kept_rows(self):
        rows = [Dict(name=f"EQ-{i}", chargeable=i % 2) for i in range(10)]
        self.frappe.get_all.return_value = rows
        page, total = self.ops.paged("Techy Equipment", start=0, page_length=25, fields=["name"], keep=lambda r: r.chargeable)
        self.assertEqual((total, [r.name for r in page]), (5, ["EQ-1", "EQ-3", "EQ-5", "EQ-7", "EQ-9"]))

    def test_page_sizes(self):
        self.assertEqual(self.ops.page_size(50, 100), 50)
        self.assertEqual(self.ops.page_size(None, 100), 100)  # older callers keep their page
        self.assertEqual(self.ops.page_size(5000, 100), 100)  # no unbounded pages


if __name__ == "__main__":
    unittest.main()
