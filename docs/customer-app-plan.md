# Customer app: plan and checklist

A simple app for customers whose water-treatment plant we installed. Once a machine is registered (Techy Equipment with a customer), we create accounts for the customer. Their operators log daily plant data, and the customer and our team both follow it on dashboards.

It uses the same design, colour palette, navy dark mode and T icon as the Techy App.

---

## Decisions to confirm before building

These are my recommendations. Change any you disagree with.

| # | Question | Recommendation |
|---|----------|----------------|
| D1 | Where does the app live? | **Same PWA, its own section** at `/techy-app/plant`, with its own simple layout. Customers never see the Ops, Work or Manage pages, and it shares one codebase, one install and one icon. |
| D2 | What kind of account? | A **Website User** (no Desk access) linked to the customer through a Contact. They cannot open `/app` (Desk). |
| D3 | Which account types? | **Customer admin**: sees all the customer's machines, can add or remove their own operators, and raises requests. **Operator**: sees only the machines given to them, logs data and raises requests. |
| D4 | How do accounts start? | A manager presses **Create customer account** on the machine (or customer). The person gets an email with a link to set their password. Nobody types passwords for customers. |
| D5 | Where do the operator's logs go? | Into the same **Techy Meter Reading** records the technicians use, marked *Source: Customer*. One history per machine, so Health, RO normalisation, forecasts and CIP alerts all use them. |
| D6 | Can customers see costs? | **No.** No prices, labour, internal notes, investigations or technician chat. They see what was done, the readings, and the service report. |
| D7 | Do customer logs raise jobs automatically? | **No.** A breach (for example "clean the membranes") alerts *our* managers, who decide. The customer sees "We've been told and will contact you". |
| D8 | Offline logging? | **Yes.** Plant rooms often have no signal. Logs queue on the phone and send when back online, as the technicians' readings do now. |
| D9 | How often do operators log? | **Daily**, set per machine (daily, each shift or weekly). Missing logs show on our side and remind the operator. |

---

## Phase 1: Accounts and access (the foundation)

- [x] **1.1 Roles**: add the roles `Techy Customer Admin` and `Techy Operator` (desk access off), created on install and migrate.
- [x] **1.2 Link people to customers**: the user is linked to a Contact, which is linked to the Customer. An operator also gets a list of the machines they may use (a child table on the user's access record).
  - *Done when* one person can belong to exactly one customer, and an operator to some of its machines.
- [x] **1.3 Create account button** (manager only) on the Equipment page and the Customer: choose a name, email and type (admin or operator), then send the invite.
  - *Done when* the invite email arrives, the link sets a password, and login lands on the customer app.
- [x] **1.4 Customer admin manages their own operators**: add, disable, and choose which machines each operator can use.
- [x] **1.5 Lock-down**, with permission hooks plus a check inside every customer endpoint:
  - a customer reads only their own Equipment, readings, visits, service reports, contracts and requests;
  - an operator reads only the machines given to them;
  - no access to Desk, Task, Project, prices, invoices, chat or the other apps' pages.
- [x] **1.6 Security audit script**: the role audit we already run, extended so Customer A can never see Customer B and an operator never sees machines not given to them.
  - *Done when* every check passes and the audit runs in the test suite.
- [x] **1.7 Login routing**: customer users go straight to `/techy-app/plant`. Staff routes and the Home app picker are hidden from them, and typing an Ops URL redirects back.

## Phase 2: App shell (same look)

- [x] **2.1 Customer layout**: bottom tabs on the phone (**Home · Log · Service · Account**) and a side menu on desktop. Same components, colours, navy dark mode and theme switch.
- [x] **2.2 Customer branding on screen**: the customer's name and their site at the top, and our logo plus support phone number on the Account page.
- [x] **2.3 Install as an app**: the same manifest and T icon. The install prompt works on Android and iPhone.
- [x] **2.4 Machine picker**: if a customer has more than one machine, choose it once and remember it. With one machine, skip the picker.

## Phase 3: Operator log (the core feature)

- [x] **3.1 Log form per machine**, built from the machine's meters (the RO set: feed, concentrate and permeate pressure; feed and permeate TDS; permeate and concentrate flow; temperature; running hours; plus any others the machine has):
  - big number fields, the unit shown, the last value shown as a hint;
  - optional fields can be skipped;
  - a notes box and an optional photo (for example of the gauges).
- [x] **3.2 Checks while typing**: the same "Is this right?" check for unusual values, and counters can't go backwards (unless marked as a meter reset by us).
- [x] **3.3 Save as one log**: every reading saves with the same time, `Source: Customer` and the operator's name, so RO normalisation groups them as one log.
  - *Done when* a log entered in the customer app shows up in our Health tab and in the RO charts.
- [x] **3.4 Offline queue**: logs save on the phone without signal, with "3 logs waiting to send", and send automatically later.
- [x] **3.5 Log history**: the operator's past logs (last 30), with an edit window of 24 hours for typos. After that, only our team can correct them, and the correction is recorded.
- [x] **3.6 Log schedule per machine** (daily, each shift or weekly), set by us: shows "Today's log: done / due" and powers reminders.
- [x] **3.7 Our-side marking**: on the staff Health page, readings show who took them (customer operator or technician), and the data-completeness card counts missed customer logs.

## Phase 4: Customer dashboard

- [ ] **4.1 Plant status at a glance**: a simple status (Good / Needs attention / Action needed) from the health score and the RO cleaning rules, in plain words, with icon and label (never colour alone).
- [ ] **4.2 Key numbers**: today's permeate flow, permeate TDS (water quality), recovery and running hours, each with the change from last week.
- [ ] **4.3 Charts**: permeate flow, TDS and pressures over 30 or 90 days, plus the normalised RO performance (flow, salt passage, pressure drop) in simplified wording. Same chart components, hover and table view.
- [ ] **4.4 What's next**: the next service visit, warranty and contract end dates, and "membranes may need cleaning soon" when forecast.
- [ ] **4.5 Logging streak**: "Logged 26 of the last 30 days", so the customer admin can see whether operators are logging.
- [ ] **4.6 Hide the internals**: no costs, no MTBF or availability jargon, no technician names beyond the visit's lead technician.

## Phase 5: Service

- [ ] **5.1 Raise a request** (problem or question) for a machine, with a photo. It uses the existing work-request flow, so it shows up in our Requests inbox.
- [ ] **5.2 Track requests**: Received, Scheduled (with date), In progress, Done, with simple status words.
- [ ] **5.3 Visit history**: past visits with date, what was done and the readings taken, and a **Download service report (PDF)** without prices.
- [ ] **5.4 Rate a visit**: the existing rating flow, inside the app.
- [ ] **5.5 Contract and warranty page**: what's covered, visits included and used, and the end date.

## Phase 6: Notifications

- [ ] **6.1 Push notifications to the customer phone** (the existing push system):
  - visit scheduled or changed;
  - technician on the way;
  - visit done, with the report ready;
  - request answered;
  - membranes need cleaning.
- [ ] **6.2 Log reminder** to operators when today's log is missing at a set time (for example 10:00). It stops once they log.
- [ ] **6.3 Our side**: managers are notified when a customer log breaks a cleaning rule or a machine has had no logs for N days (N set in Techy Ops Settings).
- [ ] **6.4 Per-person notification settings** on the Account page.

## Phase 7: Our side (staff)

- [ ] **7.1 Customer accounts list**: who has access, to which machines, last login and last log; disable or resend the invite.
- [ ] **7.2 Logging compliance report**: per customer and machine, the logs expected, received and missed, plus an export (Excel/PDF, as in the other reports).
- [ ] **7.3 "Customer view" preview**: a manager can see a machine's page as the customer sees it, to check nothing internal leaks.

## Phase 8: Testing, docs and go-live

- [ ] **8.1 Unit tests**: account creation, scoping, log save and grouping, the edit window, reminders.
- [ ] **8.2 Browser flows** (Playwright), each as a separate account:
  - a customer admin;
  - an operator;
  - a second customer that must see nothing of the first.

  They cover phone and desktop size, light and dark mode, and offline logging.
- [ ] **8.3 Docs**:
  - `docs/customer-app.md`, a short guide for customers and operators;
  - a staff section in `docs/ops.md` on creating accounts and reading customer logs.
- [ ] **8.4 Go-live checklist**:
  - email sending set up (needed for invites);
  - HTTPS (needed for install and push);
  - the RO meters set up on each machine;
  - log schedules set;
  - a pilot with one customer before everyone.

---

## Order of work

Each step is committed and pushed when it passes its tests.

1. Phase 1 (accounts and lock-down): nothing customer-facing ships before the security audit passes.
2. Phase 2 plus Phase 3 (shell and operator log): the first useful version; pilot with one customer.
3. Phase 4 (dashboard).
4. Phase 5 (service).
5. Phase 6 (notifications).
6. Phase 7 (staff tools).
7. Phase 8 runs alongside each phase. Docs and go-live come last.

## Not in this version

- Automatic readings from sensors (IoT): deferred, as for the staff app. The log is built so sensor readings can feed the same records later.
- Invoices and payments in the customer app.
- Chat between customers and technicians.
