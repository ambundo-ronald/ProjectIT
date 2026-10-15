"""Contract tests for procedures: template validation, answer rules, follow-ups and the completion rule."""
import importlib
import unittest
from unittest.mock import MagicMock

from test_ops import Dict, OpsTestCase, ValidationError


def step(field_type, label="Check", **extra):
    return {"field_type": field_type, "label": label, **extra}


class ProcedureTemplateTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.proc = importlib.import_module("projectit.procedures")

    def test_steps_are_normalised(self):
        rows = self.proc._clean_steps([step("Heading", "Safety", required=1),
            step("Number", "Pressure", min_value=" 4 ", max_value="6", unit="bar", create_follow_up=1, required=1),
            step("Checkbox", "Isolate", create_follow_up=1),
            step("Multiple Choice", "Filter", options="Clean\n\nDirty\nClean")])
        self.assertEqual(rows[0]["required"], 0)  # headings never required
        self.assertEqual((rows[1]["min_value"], rows[1]["max_value"], rows[1]["create_follow_up"]), ("4", "6", 1))
        self.assertEqual(rows[2]["create_follow_up"], 0)  # only Pass/Fail and Number can fail
        self.assertEqual(rows[3]["options"], "Clean\nDirty")

    def test_invalid_templates_rejected(self):
        for steps in ([step("Essay")], [step("Heading")], [step("Multiple Choice", options="Only one")],
                [step("Number", min_value="9", max_value="1")], [step("Number", min_value="abc")],
                [step("Number", create_follow_up=1)], [step("Checkbox", label="")],
                [step("Checkbox")] * 101):
            with self.assertRaises(ValidationError, msg=steps[:1]):
                self.proc._clean_steps(steps)

    def test_only_managers_save(self):
        with self.assertRaises(PermissionError):
            self.proc.save_procedure("Pump", [step("Checkbox")])
        self.manager()
        doc = MagicMock(name="PROC-00001", disabled=0, steps=[])
        self.frappe.new_doc = MagicMock(return_value=doc)
        self.frappe.get_doc.return_value = doc
        self.proc.save_procedure("Pump", [step("Checkbox")], category="Preventive")
        doc.save.assert_called_once_with(ignore_permissions=True)
        doc.set.assert_called_once()

    def test_technicians_do_not_see_archived_procedures(self):
        self.proc.list_procedures(archived=1)
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"], {"disabled": 0})


class ProcedureAnswerTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.proc = importlib.import_module("projectit.procedures")

    def row(self, field_type, **extra):
        return Dict({"field_type": field_type, "label": "Check", "options": "", "min_value": "", "max_value": "", "unit": "", **extra})

    def test_answer_values_and_failures(self):
        value = self.proc._value
        self.assertEqual(value(self.row("Checkbox"), "true", None), ("1", 0))
        self.assertEqual(value(self.row("Checkbox"), "", None), ("", 0))
        self.assertEqual(value(self.row("Pass/Fail"), "Fail", None), ("Fail", 1))
        self.assertEqual(value(self.row("Yes/No/N/A"), "No", None), ("No", 0))
        number = self.row("Number", min_value="4", max_value="6")
        self.assertEqual(value(number, "5.50", None), ("5.5", 0))
        self.assertEqual(value(number, "7", None), ("7", 1))
        self.assertEqual(value(number, "3.9", None), ("3.9", 1))
        self.assertEqual(value(self.row("Number", max_value="80"), "-5", None), ("-5", 0))
        self.assertEqual(value(self.row("Multiple Choice", options="Clean\nDirty"), "Dirty", None), ("Dirty", 0))
        for row, bad in ((self.row("Pass/Fail"), "Maybe"), (number, "high"), (self.row("Heading"), "x"),
                (self.row("Multiple Choice", options="Clean\nDirty"), "Broken")):
            with self.assertRaises(ValidationError):
                value(row, bad, None)

    def test_closed_work_orders_are_locked(self):
        doc = MagicMock(status="Completed", custom_work_order=1, owner="tech@example.com")
        self.frappe.get_doc.return_value = doc
        with self.assertRaises(ValidationError):
            self.proc.answer("TASK-1", "row-1", "1")

    def test_completion_blocked_while_required_steps_open(self):
        wo = importlib.import_module("projectit.work_orders")
        doc = MagicMock(status="Completed", custom_work_order=1, custom_asset_maintenance_log=None)
        doc.name = "TASK-1"
        doc.get = lambda key: getattr(doc, key)
        doc.is_new.return_value = False
        doc.has_value_changed.return_value = True
        self.frappe.db.get_value.return_value = "RUN-1"
        self.frappe.db.sql.return_value = [[2]]
        self.frappe.db.count.return_value = 0  # no open parts requests
        with self.assertRaises(ValidationError) as raised:
            wo.validate_task(doc)
        self.assertIn("2 required", str(raised.exception))
        self.frappe.db.sql.return_value = [[0]]
        wo.validate_task(doc)  # all answered: allowed

    def test_failed_step_raises_one_follow_up(self):
        wo = importlib.import_module("projectit.work_orders")
        created = MagicMock()
        created.name = "TASK-9"
        wo.create = MagicMock(return_value=created)
        doc = MagicMock(subject="Pump check", custom_asset="A-1", custom_location="Plant", project=None)
        doc.name = "TASK-1"
        row = Dict(label="Pressure", value="7", unit="bar")
        self.assertEqual(self.proc._follow_up(doc, row), "TASK-9")
        args, kwargs = wo.create.call_args
        self.assertEqual(args[2:6], ("High", "Corrective", "A-1", "Plant"))
        self.assertTrue(kwargs["ignore_permissions"])
        self.assertIn("7 bar", doc.add_comment.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
