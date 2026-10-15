"""Contract tests for the native ERPNext Task adapter (no live Bench required)."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

class ValidationError(Exception):
    pass

def fail(message, exception=ValidationError):
    raise exception(message)

class TaskTests(unittest.TestCase):
    def setUp(self):
        frappe = ModuleType("frappe")
        frappe.whitelist = lambda **kwargs: lambda fn: fn
        frappe._ = lambda text: text
        frappe.throw = fail
        frappe.PermissionError = PermissionError
        frappe.parse_json = json.loads
        frappe.session = SimpleNamespace(user="worker@example.com")
        frappe.get_roles = MagicMock(return_value=["Employee"])
        for name in ("get_doc","get_list","get_all","has_permission"):
            setattr(frappe,name,MagicMock())
        frappe.db = MagicMock()
        utils=ModuleType("frappe.utils")
        utils.cint=lambda value: int(value or 0)
        utils.strip_html=lambda text: text
        spec=importlib.util.spec_from_file_location("tasks_under_test",Path(__file__).resolve().parents[1]/"projectit/tasks.py")
        self.module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{"frappe":frappe,"frappe.utils":utils}):
            spec.loader.exec_module(self.module)
        self.frappe=frappe
        self.doc=MagicMock()
        self.doc.name="TASK-1"; self.doc.project="PROJ-1"; self.doc.is_template=0
        self.doc.modified="2026-10-01 10:00:00"; self.doc.is_group=0; self.doc.status="Open"
        frappe.get_doc.return_value=self.doc
        for name,value in [("_assigned_names",["TASK-1"]),("_allocated_projects",["PROJ-1"])]:
            patcher=patch.object(self.module,name,return_value=value);patcher.start();self.addCleanup(patcher.stop)

    def test_guest_rejected(self):
        self.frappe.session.user="Guest"
        with self.assertRaises(PermissionError):self.module.list_tasks()

    def test_task_requires_assignment_and_allocation(self):
        for assigned,allocated in [([], ["PROJ-1"]),(["TASK-1"],[])]:
            self.module._assigned_names.return_value=assigned;self.module._allocated_projects.return_value=allocated
            with self.assertRaises(PermissionError): self.module._task("TASK-1")

    def test_native_write_permission_checked(self):
        self.module._task("TASK-1",write=True)
        self.doc.check_permission.assert_any_call("write")
        self.frappe.get_doc.assert_any_call("Task","TASK-1",for_update=True)

    def test_worker_cannot_list_all_tasks_with_mine_false(self):
        self.frappe.get_list.return_value=[]
        self.module.list_tasks(mine=0)
        filters=self.frappe.get_list.call_args.kwargs["filters"]
        self.assertEqual(filters["name"],["in",["TASK-1"]])
        self.assertEqual(filters["project"],["in",["PROJ-1"]])

    def test_foreign_project_filter_rejected(self):
        with self.assertRaises(PermissionError):self.module.list_tasks(project="PROJ-OTHER")
        self.frappe.get_list.assert_not_called()

    def test_pages_report_the_total(self):
        names=[f"TASK-{i}" for i in range(60)]
        def get_list(doctype,**kw):
            if kw.get("fields")==["name","status"]:return [{"name":n,"status":"Open"} for n in names]
            return [{"name":n,"project":None} for n in reversed(kw["filters"]["name"][1])]
        self.frappe.get_list.side_effect=get_list
        result=self.module.list_tasks(start=25,page_length=25)
        self.assertEqual([t["name"] for t in result["tasks"]],names[25:50])  # this page, in list order
        self.assertEqual((result["total"],result["has_more"]),(60,True))
        last=self.module.list_tasks(start=50,page_length=25)
        self.assertEqual((len(last["tasks"]),last["has_more"]),(10,False))
        self.assertEqual(len(self.module.list_tasks()["tasks"]),50)  # older callers keep 50 per page

    def test_status_tabs_count_every_page(self):
        light=[{"name":"T1","status":"Open"},{"name":"T2","status":"Completed"},{"name":"T3","status":"Cancelled"},{"name":"T4","status":"Working"}]
        def get_list(doctype,**kw):
            if kw.get("fields")==["name","status"]:return light
            return [{"name":n,"project":None} for n in kw["filters"]["name"][1]]
        self.frappe.get_list.side_effect=get_list
        result=self.module.list_tasks(status="open",page_length=25)
        self.assertEqual([t["name"] for t in result["tasks"]],["T1","T4"])
        self.assertEqual(result["counts"],{"open":2,"done":1,"all":4})
        self.assertEqual([t["name"] for t in self.module.list_tasks(status="done")["tasks"]],["T2"])

    def test_workflow_cannot_be_bypassed(self):
        self.frappe.db.get_value.return_value="Approval Workflow"
        with self.assertRaises(ValidationError):self.module.update_status("TASK-1","Completed",self.doc.modified)
        self.doc.save.assert_not_called()

    def test_stale_update_rejected(self):
        self.frappe.db.get_value.return_value=None
        with self.assertRaises(ValidationError):self.module.update_status("TASK-1","Completed","old")
        self.doc.save.assert_not_called()

    def test_worker_cannot_cancel(self):
        self.frappe.db.get_value.return_value=None
        with self.assertRaises(PermissionError):self.module.update_status("TASK-1","Cancelled",self.doc.modified)
        self.doc.save.assert_not_called()

    def test_status_saves_through_native_controller(self):
        self.frappe.db.get_value.return_value=None
        with patch.object(self.module,"get_task",return_value={}):
            self.module.update_status("TASK-1","Completed",self.doc.modified)
        self.assertEqual(self.doc.status,"Completed");self.doc.save.assert_called_once()

    def test_dependency_validation_failure_propagates(self):
        self.frappe.db.get_value.return_value=None
        self.doc.save.side_effect=ValidationError("Incomplete dependent task")
        with self.assertRaises(ValidationError):self.module.update_status("TASK-1","Completed",self.doc.modified)

    def test_comment_is_escaped(self):
        with patch.object(self.module,"get_task",return_value={}):
            self.module.add_comment("TASK-1","<script>alert(1)</script>")
        self.doc.add_comment.assert_called_once_with("Comment","&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_non_manager_cannot_get_assignment_options(self):
        with self.assertRaises(PermissionError):self.module.task_options()

    def test_steps_are_bounded_and_validated(self):
        self.assertEqual(self.module._steps('["  Install  ", "Test"]'),["Install","Test"])
        for value in ([""], ["x"]*51, [123], {}, ["x"*141]):
            with self.assertRaises(ValidationError):self.module._steps(value)

    def test_create_reuses_task_and_assign_to_for_every_step(self):
        assignment=ModuleType("frappe.desk.form.assign_to");assignment.add=MagicMock()
        project=SimpleNamespace(status="Open")
        created=[]
        def get_doc(arg,*args,**kwargs):
            if arg=="Project":return project
            doc=MagicMock();doc.name=f"TASK-{len(created)+1}";doc.payload=arg;created.append(doc);return doc
        self.frappe.get_doc.side_effect=get_doc
        with patch.dict(sys.modules,{"frappe.desk.form.assign_to":assignment}), patch.object(self.module,"task_options",return_value={"people":[SimpleNamespace(user_id="worker@example.com")]}):
            result=self.module.create_task("PROJ-1","Installation","worker@example.com",steps=["Mount","Test"])
        self.assertEqual(result,{"name":"TASK-1"});self.assertEqual(len(created),3)
        self.assertEqual(created[0].payload["is_group"],1)
        self.assertEqual(created[1].payload["parent_task"],"TASK-1")
        self.assertEqual(assignment.add.call_count,3)
        for doc in created:doc.insert.assert_called_once()

    def test_create_rejects_unallocated_assignee(self):
        assignment=ModuleType("frappe.desk.form.assign_to");assignment.add=MagicMock()
        with patch.dict(sys.modules,{"frappe.desk.form.assign_to":assignment}), patch.object(self.module,"task_options",return_value={"people":[]}):
            with self.assertRaises(PermissionError):self.module.create_task("PROJ-1","Test","other@example.com")
        assignment.add.assert_not_called()

if __name__=="__main__":unittest.main()
