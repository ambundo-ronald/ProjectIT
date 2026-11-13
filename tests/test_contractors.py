"""Contract tests for contractors: who sees which jobs, the request guard, accepting jobs, pay, site visits and
payouts (projectit.contractors, contractor_pay, site_visits, payouts) against a stub frappe."""
import importlib
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from test_ops import Dict, OpsTestCase

OWNER = Dict(contractor="CTR-1", contractor_name="Kamau Fixers", contractor_type="Company", member_role="Owner",
    pay_cycle="Monthly", purchases="Reimbursed")
LEAD = Dict(OWNER, member_role="Lead")
CREW = Dict(OWNER, member_role="Crew")


class ContractorCase(OpsTestCase):
    def setUp(self):
        super().setUp()
        self.c = importlib.import_module("projectit.contractors")
        self.pay = importlib.import_module("projectit.contractor_pay")
        self.visits = importlib.import_module("projectit.site_visits")
        self.payouts = importlib.import_module("projectit.payouts")
        self.perm = importlib.import_module("projectit.permissions")
        self.frappe.session.user = "crew@k.test"
        self.frappe.get_roles.return_value = ["Techy Contractor"]
        self.frappe.utils.get_time = lambda value: value

    def as_member(self, member):
        return patch.object(self.c, "membership", return_value=member)


class GuardTests(ContractorCase):
    def request(self, path, cmd=None):
        self.frappe.local.request = SimpleNamespace(path=path)
        self.frappe.local.form_dict = {"cmd": cmd} if cmd else {}

    def test_job_screen_and_own_endpoints_are_open(self):
        with self.as_member(CREW):
            for method in ("projectit.work_orders.get_work_order", "projectit.site_visits.check_in",
                    "projectit.contractor_pay.job_pay", "projectit.timer.start"):
                with self.subTest(method=method):
                    self.request(f"/api/method/{method}")
                    self.c.guard()

    def test_everything_else_is_refused(self):
        with self.as_member(CREW):
            for path in ("/api/method/projectit.billing.create_invoice", "/api/method/projectit.chat.list_channels",
                    "/api/resource/Sales Invoice", "/api/method/projectit.service_report.download",
                    "/api/method/projectit.work_orders.list_work_orders", "/api/method/frappe.client.get_list"):
                with self.subTest(path=path):
                    self.request(path)
                    with self.assertRaises(PermissionError):
                        self.c.guard()

    def test_switched_off_account_is_refused_even_for_its_own_endpoints(self):
        with self.as_member(None):
            self.request("/api/method/projectit.contractors.me")
            with self.assertRaises(PermissionError):
                self.c.guard()

    def test_staff_are_not_guarded(self):
        self.frappe.get_roles.return_value = ["Maintenance Manager"]
        self.request("/api/method/projectit.billing.create_invoice")
        self.c.guard()


class JobAccessTests(ContractorCase):
    def setUp(self):
        super().setUp()
        self.assigned = {("TASK-1", "crew@k.test")}
        self.perm_assigned = patch("projectit.permissions.assigned_to",
            side_effect=lambda name, user: (name, user) in self.assigned)
        self.perm_assigned.start()
        self.addCleanup(self.perm_assigned.stop)

    def job(self, name, contractor="CTR-1", parent=None):
        return Dict(name=name, custom_contractor=contractor, parent_task=parent)

    def test_crew_see_only_jobs_they_are_on(self):
        with self.as_member(CREW):
            self.assertTrue(self.c.sees_job(self.job("TASK-1")))
            self.assertFalse(self.c.sees_job(self.job("TASK-2")))  # their contractor's, but not theirs

    def test_owner_and_lead_see_all_their_contractors_jobs_only(self):
        for member in (OWNER, LEAD):
            with self.subTest(role=member.member_role), self.as_member(member):
                self.assertTrue(self.c.sees_job(self.job("TASK-2")))
                self.assertFalse(self.c.sees_job(self.job("TASK-9", contractor="CTR-2")))

    def test_contractors_never_create_tasks_or_see_the_pool(self):
        self.frappe.get_all = MagicMock(return_value=[])  # no other role grants Task rights
        self.frappe.db.exists = MagicMock(return_value=False)
        doc = MagicMock()
        doc.is_new.return_value = False
        doc.name, doc.parent_task = "TASK-5", None
        doc.get = lambda k, d=None: {"custom_contractor": None, "custom_work_order": 1, "status": "Open"}.get(k, d)
        with self.as_member(CREW):
            self.assertFalse(self.perm.task_permission(doc, "create", "crew@k.test"))
            self.assertFalse(self.perm.task_permission(doc, "read", "crew@k.test"))  # an open unassigned job
            self.assertFalse(self.perm.task_permission(doc, "delete", "crew@k.test"))

    def test_work_waits_for_acceptance(self):
        with self.assertRaises(PermissionError):
            self.c.check_can_work(Dict(custom_contractor_state="Offered"))
        self.c.check_can_work(Dict(custom_contractor_state="Accepted"))
        self.frappe.get_roles.return_value = ["Maintenance User"]  # staff are never stopped
        self.c.check_can_work(Dict(custom_contractor_state="Offered"))

    def test_list_rule_for_crew_has_no_contractor_wide_part(self):
        with self.as_member(CREW):
            self.assertNotIn("custom_contractor", self.c.job_query("crew@k.test"))
        with self.as_member(LEAD):
            self.assertIn("custom_contractor = 'CTR-1'", self.c.job_query("lead@k.test"))


class RespondTests(ContractorCase):
    def setUp(self):
        super().setUp()
        self.doc = MagicMock()
        self.doc.name, self.doc.subject, self.doc.parent_task = "TASK-1", "Install RO", None
        values = {"custom_work_order": 1, "custom_contractor": "CTR-1", "custom_contractor_state": "Offered", "parent_task": None}
        self.doc.get = lambda k, d=None: values.get(k, d)
        self.frappe.get_doc.return_value = self.doc
        self.c.job_contractor = MagicMock(return_value={})
        patcher = patch("projectit.meters._managers", return_value=["boss@x.test"])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_crew_cannot_answer(self):
        with self.as_member(CREW), self.assertRaises(PermissionError):
            self.c.respond("TASK-1", 1)

    def test_lead_accepts(self):
        with self.as_member(LEAD):
            self.c.respond("TASK-1", 1)
        self.frappe.db.set_value.assert_called_with("Task", "TASK-1", {"custom_contractor_state": "Accepted",
            "custom_contractor_note": None})

    def test_declining_needs_a_reason(self):
        with self.as_member(OWNER), self.assertRaises(Exception):
            self.c.respond("TASK-1", 0, "")

    def test_another_contractors_job_is_refused(self):
        with self.as_member(Dict(OWNER, contractor="CTR-2")), self.assertRaises(PermissionError):
            self.c.respond("TASK-1", 1)


class InviteTests(ContractorCase):
    def test_owner_cannot_add_another_owner(self):
        with self.as_member(OWNER), self.assertRaises(PermissionError):
            self.c.invite_member(full_name="Pat", email="pat@k.test", member_role="Owner")

    def test_crew_cannot_add_people(self):
        with self.as_member(CREW), self.assertRaises(PermissionError):
            self.c.invite_member(full_name="Pat", email="pat@k.test")

    def test_staff_email_is_refused(self):
        self.frappe.db.get_value = MagicMock(return_value=Dict(name="tech@x.test", user_type="System User"))
        with self.as_member(OWNER), self.assertRaises(Exception) as caught:
            self.c.invite_member(full_name="Tech", email="tech@x.test")
        self.assertIn("staff account", str(caught.exception))


class PayTests(ContractorCase):
    def test_lines_are_checked(self):
        with self.assertRaises(Exception):
            self.pay._clean_line({"pay_type": "Bonus", "description": "x", "rate": 1}, "CTR-1")
        with self.assertRaises(Exception):
            self.pay._clean_line({"pay_type": "Fixed", "description": "Install", "rate": 0}, "CTR-1")
        fixed = self.pay._clean_line({"pay_type": "Fixed", "description": "Install", "rate": 8000}, "CTR-1")
        self.assertEqual((fixed["qty"], fixed["amount"]), (1, 8000))
        hourly = self.pay._clean_line({"pay_type": "Hourly", "description": "Labour", "rate": 500}, "CTR-1")
        self.assertEqual(hourly["hours_from"], "Check-in")

    def test_deductions_count_against_the_bill(self):
        self.assertEqual(self.pay.signed(Dict(pay_type="Deduction", amount=300)), -300)
        self.assertEqual(self.pay.signed(Dict(pay_type="Fixed", amount=300)), 300)

    def test_approval_counts_hours_and_reported_quantities(self):
        job = Dict(name="TASK-1")
        hourly = MagicMock(pay_type="Hourly", hours_from="Timer", rate=500, contractor="CTR-1")
        with patch.object(self.pay, "hours", return_value=6.5) as hours:
            self.pay._approve(hourly, job)
        hours.assert_called_once_with("TASK-1", "CTR-1", "Timer")
        self.assertEqual((hourly.qty, hourly.amount, hourly.status), (6.5, 3250, "Approved"))
        unit = MagicMock(pay_type="Per unit", qty=0, reported_qty=12, rate=250)
        self.pay._approve(unit, job)
        self.assertEqual((unit.qty, unit.amount), (12, 3000))

    def test_completing_the_job_approves_and_reopening_undoes(self):
        doc = MagicMock(status="Completed", name="TASK-1")
        doc.get = lambda k, d=None: {"custom_contractor": "CTR-1", "custom_work_order": 1}.get(k, d)
        doc.has_value_changed.return_value = True
        doc.get_doc_before_save.return_value = Dict(status="Pending Review")
        self.frappe.get_all = MagicMock(return_value=["PAY-1", "PAY-2"])
        with patch.object(self.pay, "_approve") as approve:
            self.pay.on_task_update(doc)
        self.assertEqual(approve.call_count, 2)
        doc.status = "Working"
        doc.get_doc_before_save.return_value = Dict(status="Completed")
        self.frappe.get_all = MagicMock(return_value=["PAY-1"])
        self.pay.on_task_update(doc)
        self.frappe.db.set_value.assert_called_with(self.pay.LINE, "PAY-1", {"status": "Draft", "approved_by": None,
            "approved_on": None})

    def test_only_the_owner_sees_the_statement(self):
        for member in (LEAD, CREW):
            with self.subTest(role=member.member_role), self.as_member(member), self.assertRaises(PermissionError):
                self.pay.statement()

    def test_crew_do_not_see_amounts(self):
        row = self.pay._redact(Dict(name="PAY-1", pay_type="Per unit", rate=250, amount=3000, qty=12), "crew")
        self.assertNotIn("rate", row)
        self.assertNotIn("amount", row)
        self.assertEqual(row["qty"], 12)

    def test_paid_means_the_purchase_invoice_is_paid(self):
        invoices = {"PI-1": Dict(docstatus=1, outstanding_amount=0), "PI-2": Dict(docstatus=1, outstanding_amount=50)}
        self.assertEqual(self.pay.shown_status(Dict(status="Billed", purchase_invoice="PI-1"), invoices), "Paid")
        self.assertEqual(self.pay.shown_status(Dict(status="Billed", purchase_invoice="PI-2"), invoices), "Billed")


class SiteVisitTests(ContractorCase):
    def test_distance(self):
        # Nairobi CBD to Westlands: about 2.2 km as the crow flies.
        self.assertAlmostEqual(self.visits._distance_m(-1.2864, 36.8172, -1.2676, 36.8108), 2200, delta=300)
        self.assertEqual(round(self.visits._distance_m(-1.0, 36.0, -1.0, 36.0)), 0)

    def test_cannot_check_out_of_someone_elses_visit(self):
        self.frappe.get_doc.return_value = Dict(user="other@k.test", status="On site")
        with self.as_member(CREW), self.assertRaises(PermissionError):
            self.visits.check_out("VIS-1", -1.28, 36.81)

    def test_check_out_counts_hours(self):
        doc = MagicMock(user="crew@k.test", status="On site", check_in_at=datetime(2026, 10, 11, 6, 30))
        doc.get = lambda k, d=None: getattr(doc, k, d)
        self.frappe.get_doc.return_value = doc
        self.visits._row = MagicMock(return_value={})
        with self.as_member(CREW):
            self.visits.check_out("VIS-1", -1.28, 36.81)
        values = doc.update.call_args.args[0]
        self.assertEqual((values["hours"], values["status"], values["confirmed"]), (2.5, "Checked out", 1))


class PayoutTests(ContractorCase):
    def test_only_approved_unbilled_lines_up_to_the_date_are_due(self):
        rows = [Dict(name="A", status="Approved", approved_on="2026-10-01 10:00:00"),
            Dict(name="B", status="Approved", approved_on="2026-10-20 10:00:00"),
            Dict(name="C", status="Approved", approved_on="2026-10-01 10:00:00", purchase_invoice="PI-1"),
            Dict(name="D", status="On hold", approved_on="2026-10-01 10:00:00")]
        due = self.payouts._due(rows, self.frappe.utils.getdate("2026-10-11"))
        self.assertEqual([r.name for r in due], ["A"])

    def test_deductions_become_the_invoice_discount(self):
        con = MagicMock(supplier="SUP-1", contractor_name="Kamau Fixers")
        invoice = MagicMock(grand_total=7700, name="PI-9")
        def get_doc(arg, *a, **k):
            if isinstance(arg, dict):
                invoice.data = arg
                return invoice
            return con
        self.frappe.get_doc = MagicMock(side_effect=get_doc)
        self.frappe.get_cached_doc.return_value = Dict(contractor_item="CONTRACT-WORK")
        self.frappe.get_all = MagicMock(return_value=[])
        self.frappe.db.get_value = MagicMock(return_value=Dict(tax_withholding_category=None))
        self.frappe.utils.fmt_money = lambda v, **k: str(v)
        self.frappe.defaults = SimpleNamespace(get_user_default=lambda key: "Norwa")
        lines = [Dict(name="PAY-1", pay_type="Fixed", amount=8000, description="Install", work_order=None, project=None),
            Dict(name="PAY-2", pay_type="Deduction", amount=300, description="Not returned", work_order=None, project=None)]
        with patch("projectit.contractor_pay._owners", return_value=[]):
            self.payouts._bill("CTR-1", lines)
        self.assertEqual([i["rate"] for i in invoice.data["items"]], [8000])
        self.assertEqual(invoice.discount_amount, 300)
        self.frappe.db.set_value.assert_any_call(self.payouts.LINE, "PAY-2", {"status": "Billed", "purchase_invoice": invoice.name})

    def test_nothing_left_after_deductions_is_refused(self):
        self.frappe.get_doc = MagicMock(return_value=MagicMock(supplier="SUP-1", contractor_name="K"))
        self.frappe.get_cached_doc.return_value = Dict(contractor_item="CONTRACT-WORK")
        self.frappe.get_all = MagicMock(return_value=[])
        self.frappe.utils.fmt_money = lambda v, **k: str(v)
        lines = [Dict(name="PAY-1", pay_type="Fixed", amount=100, description="x"),
            Dict(name="PAY-2", pay_type="Deduction", amount=300, description="y")]
        with self.assertRaises(Exception):
            self.payouts._bill("CTR-1", lines)

    def test_a_cancelled_invoice_frees_its_lines(self):
        self.frappe.get_all = MagicMock(return_value=["PAY-1"])
        self.payouts.release_lines(Dict(name="PI-1"))
        self.frappe.db.set_value.assert_called_once_with(self.payouts.LINE, "PAY-1", {"status": "Approved",
            "purchase_invoice": None})


class JobScreenTests(ContractorCase):
    def test_contractors_never_see_prices_on_the_job(self):
        data = {"billing": {"total": 9000}, "report": {"x": 1}, "rating": {}, "manager": True,
            "parts": {"rows": [{"item_code": "FILTER", "qty": 2, "rate": 900, "amount": 1800, "valuation_rate": 600}],
                "chargeable_total": 1800, "cost_total": 1200}}
        with patch.object(self.c, "job_contractor", return_value={"contractor": "CTR-1"}):
            out = self.wo._for_contractor(data, Dict(name="TASK-1"))
        self.assertIsNone(out["billing"])
        self.assertIsNone(out["report"])
        self.assertEqual(out["parts"]["rows"], [{"item_code": "FILTER", "qty": 2}])
        self.assertIsNone(out["parts"]["cost_total"])

    def test_contractors_choose_crew_through_their_own_screen(self):
        doc = MagicMock(name="TASK-1", modified="m", status="Working")
        with patch.object(self.wo, "_work_order", return_value=doc), self.as_member(LEAD):
            with self.assertRaises(PermissionError):
                self.wo.update_work_order("TASK-1", "m", assignees='["x@k.test"]')

    def test_owner_opens_a_job_their_crew_is_on(self):
        # The job screen's own check used to know only assignees, so an owner got "not assigned to you".
        doc = MagicMock(name="TASK-1", custom_work_order=1, owner="boss@x.test")
        doc.get = lambda k, d=None: {"custom_contractor": "CTR-1", "custom_contractor_state": "Accepted"}.get(k, d)
        self.frappe.get_doc.return_value = doc
        with self.as_member(OWNER), patch.object(self.c, "sees_job", return_value=True):
            self.assertIs(self.wo._work_order("TASK-1"), doc)
        with self.as_member(OWNER), patch.object(self.c, "sees_job", return_value=False), self.assertRaises(PermissionError):
            self.wo._work_order("TASK-1")
