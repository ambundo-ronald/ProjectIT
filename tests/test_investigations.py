"""Contract tests for root cause investigations: who may use them, closing rules, saving rows and the fishbone."""
import importlib
import json
import unittest
from unittest.mock import MagicMock, patch
from xml.dom import minidom

from test_ops import Dict, OpsTestCase


def cause(category="Method", text="No SOP", **extra):
    return Dict(category=category, cause=text, evidence=extra.get("evidence"), status=extra.get("status", "Potential"),
        action=extra.get("action"), done=extra.get("done", 0), closure_evidence=extra.get("closure"),
        done_on=None, done_by=extra.get("done_by"), name=extra.get("name"))


class InvestigationTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.inv = importlib.import_module("projectit.investigations")
        self.api = importlib.import_module("projectit.api")
        patcher = patch.object(self.api, "has_app", MagicMock(return_value=True))
        self.has_app = patcher.start()
        self.addCleanup(patcher.stop)

    def test_needs_techy_ops(self):
        self.has_app.return_value = False
        with self.assertRaises(PermissionError):
            self.inv.list_investigations()
        self.manager()
        self.frappe.get_all.return_value = []
        self.assertEqual(self.inv.list_investigations()["investigations"], [])

    def test_closing_gaps(self):
        doc = Dict(causes=[], root_cause="")
        self.assertEqual(len(self.inv.gaps(doc)), 2)
        doc = Dict(root_cause="No approved SOP", causes=[cause(action="Write the SOP"),
            cause(action="Train operators", done=1), cause(action="Fit draw-off", done=1, closure="As-built P&ID"), cause()])
        self.assertEqual(self.inv.gaps(doc), ["1 action(s) still to be done.", "1 done action(s) need their closure evidence."])
        doc.causes = [cause(action="Fit draw-off", done=1, closure="As-built P&ID"), cause()]
        self.assertEqual(self.inv.gaps(doc), [])

    def test_only_managers_close(self):
        doc = MagicMock(status="Open", root_cause="x", causes=[cause()])
        self.frappe.db.exists.return_value = True
        self.frappe.get_doc.return_value = doc
        with self.assertRaises(PermissionError):
            self.inv.close("RCA-00001")
        doc.save.assert_not_called()

    def test_closed_investigations_are_read_only(self):
        self.frappe.db.exists.return_value = True
        self.frappe.get_doc.return_value = MagicMock(status="Closed")
        with self.assertRaises(Exception) as caught:
            self.inv.save("RCA-00001", "{}")
        self.assertIn("closed", str(caught.exception))

    def test_cause_rows_are_cleaned(self):
        rows = json.dumps([{"category": "Machine", "cause": " No draw-off point ", "status": "Bogus", "done": 1},
            {"category": "Method", "cause": ""}])
        clean = self.inv._rows(rows, self.inv.CAUSE_LIMITS, "cause", self.inv._cause)
        self.assertEqual(len(clean), 1)  # the empty row is dropped
        self.assertEqual((clean[0]["cause"], clean[0]["status"], clean[0]["done"]), ("No draw-off point", "Potential", 1))
        self.assertEqual(str(clean[0]["done_on"]), "2026-10-11")
        with self.assertRaises(Exception):
            self.inv._rows([{"category": "Mother Nature", "cause": "Rain"}], self.inv.CAUSE_LIMITS, "cause", self.inv._cause)
        with self.assertRaises(Exception):
            self.inv._rows([{"category": "Method", "cause": "x" * 301}], self.inv.CAUSE_LIMITS, "cause", self.inv._cause)

    def test_fishbone_is_valid_svg_with_every_cause(self):
        causes = [cause(m, f"{m} cause <{i}> & more") for m in self.inv.SIX_M for i in range(2)]
        causes += [cause("Method", f"Extra {i}") for i in range(8)]
        doc = Dict(title="Excessive chlorine residual", actual="10 mg/L", target="0.5 mg/L", causes=causes)
        svg = self.inv.fishbone(doc)
        minidom.parseString(svg)  # well formed: user text is escaped
        for m in self.inv.SIX_M:
            self.assertIn(m.upper(), svg)
        self.assertIn("Machine cause &lt;1&gt; &amp; more", svg)
        self.assertIn("+ 3 more in the evidence table", svg)  # Method has 10; 7 are drawn
        self.assertIn("(Target 0.5 mg/L)", svg)

    def test_fishbone_without_causes(self):
        svg = self.inv.fishbone(Dict(title="Leak", causes=[]))
        minidom.parseString(svg)
        self.assertEqual(svg.count("No causes recorded"), 6)

    def test_lines(self):
        self.assertEqual(self.inv._lines("- one\n\n• two \n  three"), ["one", "two", "three"])


if __name__ == "__main__":
    unittest.main()
