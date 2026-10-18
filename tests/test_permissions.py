"""Contract tests for technicians' rights: their own tasks, open jobs to pick up, and what stays with managers."""
import importlib
import json
import unittest
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase


class TaskPermissionTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.perm = importlib.import_module("projectit.permissions")
        self.frappe.get_roles.return_value = ["Employee", "Maintenance User"]
        self.todos = set()  # (task, user) assignments
        self.frappe.db.exists = MagicMock(side_effect=self.exists)
        self.frappe.db.get_value = MagicMock(return_value=None)
        self.frappe.db.escape = lambda v: f"'{v}'"

    def exists(self, doctype, filters=None):
        if doctype != "ToDo":
            return None
        user = filters.get("allocated_to")
        return any(t == filters["reference_name"] and (user is None or u == user) for t, u in self.todos) or None

    def task(self, **extra):
        doc = Dict(name="T1", owner="boss@x.com", custom_work_order=1, parent_task=None, is_template=0, status="Open")
        doc.update(extra)
        doc.is_new = lambda: False
        return doc

    def test_own_tasks_read_and_write_never_delete(self):
        self.todos.add(("T1", "tech@example.com"))
        doc = self.task()
        self.assertTrue(self.perm.task_permission(doc, "read"))
        self.assertTrue(self.perm.task_permission(doc, "write"))
        self.assertFalse(self.perm.task_permission(doc, "delete"))
        self.assertTrue(self.perm.task_permission(self.task(owner="tech@example.com"), "write"))

    def test_checklist_steps_of_own_job(self):
        self.todos.add(("T1", "tech@example.com"))
        self.assertTrue(self.perm.task_permission(self.task(name="T1-step", parent_task="T1", custom_work_order=0), "write"))

    def test_someone_elses_task_is_refused(self):
        self.todos.add(("T1", "tina@x.com"))
        doc = self.task()
        self.assertFalse(self.perm.task_permission(doc, "read"))
        self.assertFalse(self.perm.task_permission(doc, "write"))

    def test_open_unassigned_job_can_be_read_not_changed(self):
        doc = self.task()
        self.assertTrue(self.perm.task_permission(doc, "read"))
        self.assertFalse(self.perm.task_permission(doc, "write"))
        self.assertFalse(self.perm.task_permission(self.task(status="Working"), "read"))
        self.assertFalse(self.perm.task_permission(self.task(custom_work_order=0), "read"))

    def test_wider_roles_keep_erpnext_access(self):
        for roles in (["Projects User"], ["Maintenance Manager"], ["System Manager"]):
            self.frappe.get_roles.return_value = roles
            self.assertTrue(self.perm.task_permission(self.task(), "delete"))
            self.assertEqual(self.perm.task_query("x@x.com"), "")

    def test_list_condition_covers_own_steps_and_pool(self):
        sql = self.perm.task_query("tech@example.com")
        for part in ("`tabTask`.owner = 'tech@example.com'", "td.allocated_to = 'tech@example.com'",
                "`tabTask`.parent_task", "status in ('Open', 'Overdue')", "not exists"):
            self.assertIn(part, sql)


class ProjectPermissionTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.perm = importlib.import_module("projectit.permissions")
        self.frappe.db.sql = MagicMock(return_value=[("PROJ-1",)])
        self.frappe.db.escape = lambda v: f"'{v}'"

    def test_field_staff_read_only_their_projects(self):
        self.frappe.get_roles.return_value = ["Employee"]
        self.assertTrue(self.perm.project_permission(Dict(name="PROJ-1"), "read"))
        self.assertFalse(self.perm.project_permission(Dict(name="PROJ-2"), "read"))
        self.assertFalse(self.perm.project_permission(Dict(name="PROJ-1"), "write"))
        self.assertIn("e.user_id = 'tech@example.com'", self.perm.project_query("tech@example.com"))

    def test_project_staff_keep_erpnext_access(self):
        self.frappe.get_roles.return_value = ["Projects User"]
        self.assertTrue(self.perm.project_permission(Dict(name="PROJ-2"), "write"))
        self.assertEqual(self.perm.project_query("x@x.com"), "")


class TechnicianJobRuleTests(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.doc = MagicMock()
        self.doc.name, self.doc.owner, self.doc.custom_work_order = "TASK-1", "boss@example.com", 1
        self.doc.modified, self.doc.status, self.doc.custom_review_requested = "2026-10-01 10:00:00", "Working", 0
        self.doc.get = lambda k, d=None: getattr(self.doc, k, d)
        self.frappe.get_doc.return_value = self.doc
        self.frappe.get_all.return_value = ["TASK-1"]
        self.wo.frappe.db.get_value = MagicMock(return_value=None)
        patcher = patch.object(self.wo, "_assignees", return_value={"TASK-1": ["tech@example.com"]})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_technician_cannot_complete(self):
        with self.assertRaises(PermissionError) as caught:
            self.wo.update_work_order("TASK-1", self.doc.modified, status="Completed")
        self.assertIn("Send it for review", str(caught.exception))
        self.doc.save.assert_not_called()

    def test_technician_cannot_change_priority(self):
        with self.assertRaises(PermissionError):
            self.wo.update_work_order("TASK-1", self.doc.modified, priority="Urgent")

    def test_technician_cannot_remove_people(self):
        with patch.object(self.wo, "_team", return_value={"tech@example.com", "tom@example.com"}):
            with self.assertRaises(PermissionError):
                self.wo.update_work_order("TASK-1", self.doc.modified, assignees=json.dumps(["tom@example.com"]))

    def test_technician_cannot_add_outsiders(self):
        self.frappe.get_all.return_value = ["tech@example.com", "visitor@example.com"]
        with patch.object(self.wo, "_team", return_value={"tech@example.com"}):
            with self.assertRaises(PermissionError):
                self.wo.update_work_order("TASK-1", self.doc.modified,
                    assignees=json.dumps(["tech@example.com", "visitor@example.com"]))


if __name__ == "__main__":
    unittest.main()
