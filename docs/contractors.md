# Contractors (external technicians)

Some work goes to technicians who are not on our staff: individuals, and small companies with their own crews. Techy lets you give them jobs and projects, see them check in at sites, agree what you pay them, and turn approved work into bills that Accounts pays in ERPNext.

The plan behind it, with the decisions taken, is in [contractors-plan.md](contractors-plan.md).

## Setting up, once

In **Techy Ops Settings → Contractors**, set:

| Setting | What for |
|---|---|
| **Contractor Work Item** | A non-stock service item, for example *Contractor services*, used on their bills. Its expense account is where their pay is booked. Required for payouts. |
| **Contractor Reimbursement Item** | Optional: an item for things they bought on site that we pay back. Without it, the work item is used. |
| **Bought On Site Item** | Optional: an item for customer invoices, when the customer pays for something a contractor bought on site. |
| **Flag check-ins further than (m)** | 500 by default. A check-in further than this from the site is flagged. |

A site's location is taken from the machine (**Techy Equipment → Site Latitude / Longitude**), or else from the project (**Project → Site location**). You can also set it from a contractor's check-in in **On site** (*This is the site's location*).

## Adding a contractor

**Techy Ops → Contractors → New contractor.**

1. Enter the name, and choose **Individual** or **Company with a crew**.
2. Choose their usual pay cycle: per job, weekly or monthly.
3. Choose whether things they buy on site are **paid back** or **included in their price**. You can change this per job.
4. A Supplier with the same name is used, or created. Accounts sets withholding tax on that Supplier (Tax Withholding Category); their bills then apply it.
5. Add their **rate card**: their usual prices per job, hour, piece, metre and so on.
6. Under **People**, press **Invite**:
   - For a company, invite the **owner** first. The owner adds their own leads and crew in the app.
   - For an individual, invite them as **Owner**.

Each person gets an email with a link to set their password. The link is also shown, so you can send it by WhatsApp or SMS. They sign in at the Techy App on the web, or in the Android app with your company's address.

| Role | Can |
|---|---|
| **Owner** | Accept or decline jobs, choose crew, add and switch off their people, see the pay and statements, query a line |
| **Lead** | Accept or decline jobs, choose crew |
| **Crew** | Do the jobs given to them, check in at sites, report quantities, log purchases and materials used |

Contractors never see Desk, customer prices, invoices, our chat or other contractors' work. They see only their own jobs, and the projects you give them.

Switching someone off takes them off their open jobs and stops them signing in. Their past work stays.

## Giving them a job

Open the work order and press **Give to a contractor**.

1. Choose the contractor and press **Offer the job**. Their owner and leads are told.
2. Under **Contractor pay**, press **Set pay** and add one or more lines:
   - **Fixed price**: the agreed price for the job, or a number of things at a fixed price.
   - **Per hour**: the rate per hour. Choose whether hours come from their **site check-in** or the **job timer**. Only their own people's hours count.
   - **Per unit**: a rate per piece, metre or filter. Their crew report how many they did. Leave the quantity empty to use what they report.
   - **From their rate card** fills in a line from the rate card.
3. The owner or a lead accepts or declines the job in their app. A decline comes with a reason and tells you.
4. Once accepted, they choose who on their crew does it. You can also choose the crew yourself.

Until they accept, they can read the job but not work on it.

**Take the job back** removes their crew and cancels pay not yet approved.

## Projects and milestones

In **Techy Manage**, open a project:

- **Contractors → Add** gives them the project, with instructions only for them. They see it in their app and can check in to it.
- **Milestones → Add** pays them in stages: a percentage of the contract sum, or an amount. You can link a milestone to a job, for example *40% on delivery* when the delivery job is completed. **Approve** it when it is done.

## While they work

They use the same job screen as our technicians: checklists and procedures, readings, photos, the timer, failure codes, parts requests, and the customer's sign-off. Offline works too.

**Check-in at sites.** In their app's **Site** tab, they check in with a photo and GPS when they arrive, and check out when they leave. **Techy Ops → Contractors → On site** shows who is on site now, staff and contractors together. Under it, **Contractor visits** lists:

- check-ins far from the site;
- forgotten check-outs. These are closed at midnight with no hours. Press **Confirm the hours** to enter the real hours; until then they don't count for pay.

**Bought on site.** The crew adds what they bought, with a photo of the receipt. On the job, you accept or reject it. You choose whether we pay it back and whether the customer is charged. A charged purchase goes on the customer's invoice with the job.

**Materials from our stores.** Parts issued to the job through the usual parts flow are charged to the project, not to the contractor. At the end of the job the crew reports how much they used and returned. If something is missing, you can choose **Deduct from their pay**, at our stock cost.

## Approving their pay

Completing the job approves its pay. This is the same review as for our technicians: they send it for review, and you complete it.

- Hourly lines take the hours at that moment.
- Per-unit lines take the quantity you set, or else the one they reported.

Reopening a completed job turns pay that isn't billed yet back to *Waiting*. Cancelling a job cancels its unapproved pay.

On a contractor's page you can **Hold** an approved line, to keep it out of payouts, or **Release** it. The owner can **Query** a line from their app. Open queries are listed in **Payouts → Queries**, where you answer them.

## Paying them

**Techy Ops → Payouts** (managers and Accounts staff).

1. **Payout run**: choose *Approved up to* and, if you want, a pay cycle. Each contractor shows their approved lines, reimbursements and deductions, and the net amount.
2. Tick the contractors and press **Create draft bills**. Each gets one draft **Purchase Invoice** to their Supplier:
   - each job, milestone and reimbursement is its own line, with its project and the project's cost centre;
   - deductions are taken off as the invoice's discount, and listed in its remarks;
   - withholding tax applies if the Supplier has a Tax Withholding Category.
3. Accounts reviews, submits and pays the invoice in ERPNext as usual. When it is paid, the lines show as **Paid** in the contractor's statement.

Cancelling or deleting a bill makes its lines approved again, for the next run. A line is never on two bills.

**What we owe** lists, per contractor, what is approved but not billed, and what is billed but not paid. **Report** shows, per contractor, jobs done, on-time rate, rework, declined jobs, average job cost and amount paid.

## Costs

Machine costs, contract profit and machine health count what we pay the contractor for their jobs, instead of the staff *Labour Cost Rate*.

## For the contractor

Send them this:

> Sign in with the link in your email to set your password. Then use the Techy App on your phone (Play Store) with our company's address, or the web address in the email.
>
> - **Jobs**: what we offered you (accept or decline), what you are working on, and what is done. Open a job to do the work, the same as our own technicians.
> - **Site**: check in when you arrive at a site, and out when you leave. It takes a photo and your location, and works without signal.
> - **Pay** (owners): what is waiting for approval, what will be paid next, and what was paid. Press **Query** if a line is wrong. Download a statement as a PDF.
> - **Team** (owners and leads): your people. Owners add crew and leads, and switch people off.

## Where things are

| | |
|---|---|
| `projectit/contractors.py` | Contractors, their people and accounts, giving and accepting jobs, the request guard |
| `projectit/site_visits.py` | Check-in and check-out at sites, On site, forgotten check-outs |
| `projectit/contractor_pay.py` | Pay lines, approval, milestones, purchases, materials, statements, queries |
| `projectit/payouts.py` | Payout runs (Purchase Invoices), what we owe, the contractor report |
| DocTypes | Techy Contractor (with Member, Rate), Techy Site Visit, Techy Contractor Pay Line, Techy Contractor Purchase, Techy Contractor Allocation |
| `mobile/src/pages/contractor/` | The contractor app |
| `mobile/src/pages/ops/Contractors.vue`, `ContractorDetail.vue`, `OnSite.vue`, `Payouts.vue` | Staff screens |
