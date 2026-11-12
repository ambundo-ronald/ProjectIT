# External technicians (contractors): plan and checklist

Some work goes to technicians who are not on our staff: individuals, and small companies with their own crews. We assign them projects and work orders, they do the work in the Techy App, and we pay them for the work they did.

What already exists for our own technicians, and what contractors will use as it is:
- work orders, checklists (procedures), photos, readings and the customer's sign-off;
- the job timer and offline mode;
- the manager's review of a finished job;
- materials issued to a job from our stock (Techy Part Usage, with approval and a Stock Entry);
- billing the customer.

What is new: who the contractors are, their site check-in, what we agreed to pay them, and turning approved work into a bill we pay.

---

## Decisions to confirm before building

These are my recommendations, based on your answers. Change any you disagree with.

| # | Question | Recommendation |
|---|----------|----------------|
| D1 | Who is a contractor? | A new **Techy Contractor** record, linked to an ERPNext **Supplier**. It is either an *Individual* (one person) or a *Company* with its own crew. Contractors are not Employees, so they stay out of payroll, leave and HR reports. |
| D2 | Who signs in? | Each person gets their own account, linked to the contractor: the **owner** (a company's boss, or the individual), **leads**, and **crew**. A company's owner adds and removes their own crew, as a customer admin does with operators. |
| D3 | What can they see? | A new role, **Techy Contractor**, with no Desk. They see only the projects and work orders given to their contractor, and only the procedures, equipment and site details those jobs need. Never customer prices, invoices, our internal notes, other contractors, or our team chat. They see their own pay. |
| D4 | How is work given to them? | A work order or a whole project is given to a **contractor**, not just a person. For a company, the owner or a lead picks which crew members do it. For an individual, it goes straight to them. |
| D5 | Site check-in | Contractors check in and out at the site with a photo and GPS, the same screen as staff, offline included. Their check-ins are kept in their own record (**Techy Site Visit**), not in Employee Checkin, because they are not Employees. If the site has a location, a check-in far from it is flagged. Managers see a live **Who is on site** list covering staff and contractors. |
| D6 | How do we pay? | A **mix**, agreed per contractor and per job: **fixed price per job**, **per hour** (from check-in time or the job timer, you choose per agreement), **per unit** from a rate card (per filter changed, per meter installed, per metre of pipe), and **milestones** on a project (for example 40% on delivery and 60% at commissioning). One job can have several pay lines. |
| D7 | When do we pay? | Also a mix: each contractor has a usual **pay cycle** (per job, weekly or monthly), and milestones pay when they are approved. A **payout run** collects everything approved and due. |
| D8 | Who approves? | Two steps. **1.** The project manager approves the work when reviewing the job, and its pay becomes *Approved to pay*. Rework or a rejected job pays nothing until it is fixed. **2.** The payout run makes a **draft Purchase Invoice** per contractor, and Accounts checks and submits it, then pays it the usual way. |
| D9 | Materials we give them | Issued from our stock through the existing parts flow, to their job. It costs the project, not the contractor. At the end of the job they record what they used. Anything issued but neither used nor returned can be **deducted** from their pay, if the manager chooses. |
| D10 | Materials they buy on site | They log the purchase with a photo of the receipt. When agreeing the job, it is either **Reimbursed** (added to their bill once approved) or **Included in the price** (shown, but not paid extra). If it is chargeable, it still goes on the customer's invoice as parts do now. |
| D11 | Crews | We pay the **contractor**, never their crew members. The company pays its own people. We still see which crew member did what, checked in where, and for how long. |
| D12 | Tax | Withholding tax is set up by your accountant on the Supplier in ERPNext, and the Purchase Invoice applies it. Techy doesn't calculate tax itself. |
| D13 | Job costs | Contractor pay is charged to the job's project. Project profit uses what we actually pay the contractor instead of the single *Labour Cost Rate* used for staff. |

---

## Phase 1: Contractors and accounts

- [ ] **1.1 Techy Contractor** DocType:
  - fields: name, type (*Individual* or *Company*), Supplier, phone, active;
  - usual pay cycle;
  - skills or trades, for picking the right contractor;
  - a child table of members: user, role (*Owner*, *Lead* or *Crew*), active.
  - *Done when* a contractor can't be saved without a Supplier, and a person belongs to at most one contractor.
- [ ] **1.2 Role** `Techy Contractor` (no Desk), created on install and migrate.
- [ ] **1.3 Invite**: a manager presses **Invite** on the contractor. The person gets an email (and WhatsApp, once that is set up) with a link to set their password, plus the Play Store link.
- [ ] **1.4 Owner manages their crew**: add, disable, and make someone a lead.
- [ ] **1.5 Lock-down**, with permission hooks plus a check in every endpoint a contractor can call:
  - they read only their own contractor's work orders and projects, and the equipment and procedures on them;
  - no access to Desk, other projects, prices, invoices, chat or the Manage pages.
- [ ] **1.6 Security audit**: Contractor A never sees Contractor B's jobs or pay. A crew member sees only the jobs they are on, and only the owner sees pay. The audit runs in the test suite.
- [ ] **1.7 App routing**: contractors land on a **Work** view like our technicians', without the staff-only tabs.

## Phase 2: Giving them work

- [ ] **2.1 Contractor on the work order**: a new *Contractor* field, plus the crew member(s) the job is assigned to.
- [ ] **2.2 Contractor on the project**: the allocation screen accepts a contractor as well as Employees, with instructions as now.
- [ ] **2.3 Owner or lead assigns crew** from the app; the job then appears on those people's phones.
- [ ] **2.4 Accept or decline**: the contractor accepts a job, with the agreed pay shown to the owner. A declined job goes back to the manager with the reason.
- [ ] **2.5 The work itself**: checklists, photos, readings, the timer, customer sign-off and offline mode, all as for staff.
  - *Done when* a contractor's crew member finishes a job end to end on the phone, offline part of the way.

## Phase 3: Site check-in

- [ ] **3.1 Techy Site Visit** DocType: person, contractor, project or work order, check-in and check-out time, GPS, photos, device, and *offline* (with the same 24-hour limit).
- [ ] **3.2 The same check-in screen** as staff, choosing the job or project being visited.
- [ ] **3.3 Distance check**: if the site or equipment has a location, the distance is saved, and anything beyond a set distance (500 m by default) is flagged for the manager.
- [ ] **3.4 Who is on site**: one list for managers showing staff and contractors checked in now, per site, with the time they arrived.
- [ ] **3.5 Forgotten check-outs**: closed at the end of the day and flagged, so they don't count as paid hours until the manager confirms.

## Phase 4: What we agreed to pay

- [ ] **4.1 Rate card** per contractor: activity or item, unit (*job*, *hour*, *piece*, *metre*, and so on), rate, and valid from. Copy a standard rate card to a new contractor in one click.
- [ ] **4.2 Pay lines on the work order**, set by the manager when assigning the job. Each line is fixed, hourly or per unit, with its rate (from the rate card, or agreed for this job), and how on-site purchases are treated. Several lines per job are allowed.
- [ ] **4.3 Milestones on the project**: name, percentage or amount of the contract sum, and the work order or check that proves it is done.
- [ ] **4.4 Pay terms visible** to the contractor's owner before they accept.

## Phase 5: Recording the work

- [ ] **5.1 Hours** from check-in time or the job timer, as the agreement says; the manager can correct them, and the correction is recorded.
- [ ] **5.2 Quantities** for per-unit lines (filters changed, metres laid), entered by the crew and confirmed by the manager. Where the parts flow already counts something, it fills in the number.
- [ ] **5.3 On-site purchases**: item, amount, receipt photo and job, offline included.
- [ ] **5.4 Materials reconciliation** at job close: issued, used and returned for each item, with any shortfall shown to the manager, who chooses to deduct it or not.

## Phase 6: Approval and statements

- [ ] **6.1 Approve the pay** as part of the existing job review. Approving the job locks its pay lines as *Approved to pay*; sending it back for rework holds them.
- [ ] **6.2 Milestones** are approved by the project manager when their proof is done.
- [ ] **6.3 Contractor statement** in the app, for the owner: jobs done, approved, waiting and paid, with amounts and a PDF.
- [ ] **6.4 Queries**: the owner can question a line, which notifies the project manager.

## Phase 7: Payouts

- [ ] **7.1 Payout run** (Manage): choose a period and the contractors that are due by their pay cycle, review what is approved, and then press **Create bills**.
- [ ] **7.2 One draft Purchase Invoice per contractor**. Each job, milestone, reimbursement and deduction is its own line, with the project and cost centre, so ERPNext books the cost to the right project.
  - *Done when* Accounts can submit it unchanged and the project's costs go up by the right amount.
- [ ] **7.3 Paid status**: when the Purchase Invoice is paid in ERPNext, the lines show as *Paid* on the contractor's statement.
- [ ] **7.4 Nothing paid twice**: a line belongs to one bill. Cancelling the bill frees its lines for the next run.

## Phase 8: Costs and reports

- [ ] **8.1 Project profit** uses contractor pay for contractor jobs, and the Labour Cost Rate only for staff.
- [ ] **8.2 Contractor report**: jobs done, on-time rate, rework, average job cost, and amount paid in the period.
- [ ] **8.3 What we owe**: approved but not yet billed, and billed but not yet paid, per contractor.

## Phase 9: Testing, docs and go-live

- [ ] **9.1 Unit tests** for pay calculation (each pay type, mixed lines, reimbursed and included purchases, deductions), lock-down, and the payout run.
- [ ] **9.2 End-to-end on the dev site**: an individual and a two-person company, each doing a job, through check-in, approval, payout run and paid.
- [ ] **9.3 Docs**: `docs/contractors.md` for managers, and a short page for the contractors themselves.
- [ ] **9.4 Pilot on live** with one contractor you trust, for one pay cycle, before adding the rest.

---

## Order of work

1. Phases 1 to 3 together: contractors can sign in, get jobs and check in at sites. This is useful on its own, even before pay.
2. Phases 4 to 6: pay terms, recording and approval. Contractors can see what they have earned.
3. Phase 7: payouts into ERPNext.
4. Phase 8, then the go-live in Phase 9.

## Not in this version

- Paying contractors directly from Techy (M-Pesa or bank). Payment stays in ERPNext.
- Advances against future work.
- Contractors bidding on open jobs.
- Retention money held back until a warranty period ends (easy to add as a deduction line later, if you need it).
