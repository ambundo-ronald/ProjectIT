# Techy Ops: work orders, requests, assets, PM and team chat

Techy Ops is a maintenance and team-collaboration workspace (similar to MaintainX plus Slack) at `/techy-app/ops`. On desktop it has a sidebar with navigation and channels. On phones it has bottom tabs. Wherever possible it stores data in native ERPNext records, so Desk reports, permissions and audit history keep working.

| Feature | Stored as |
| --- | --- |
| Work order | ERPNext **Task** with *Work Order* checked, plus Asset, Location, Category |
| Procedure checklist | Child **Tasks** of the work order |
| Assignment | Standard **Assign To** (ToDo) |
| Activity, photos | Task **Comments** and private **Files** |
| Work request | ERPNext **Issue** with *Maintenance Request* checked, plus Asset and Location |
| Asset, location | ERPNext **Asset** and **Location** |
| Preventive maintenance | ERPNext **Asset Maintenance**, its tasks and **Asset Maintenance Logs** |
| Chat channel | **Techy Channel** (new DocType) with a member table |
| Chat message, thread reply | Frappe **Comment** on the channel. A reply links to its root Comment |
| Mentions and alerts | Frappe **Notification Log** (the Desk bell, plus email according to each user's notification settings) |

## Setup

1. Run `bench --site your-site migrate`. This adds the Task and Issue custom fields, the Techy Channel and Techy Ops Settings DocTypes, and the **Ops** mobile module.
2. Give people Techy Ops: users with Maintenance User, Maintenance Manager, Projects Manager or System Manager get it automatically. For anyone else, add **Ops** to *Techy App Access* on their Employee. Signing in then shows a **Techy Ops** button (see [docs/employee-access.md](employee-access.md)).
3. Give technicians a role with Task read/write and File create (for example *Projects User*), plus **Maintenance User** for the Assets and PM screens. ERPNext gives the maintenance roles no Asset access, so Ops shows Maintenance Users, managers and anyone with Asset read a read-only, non-financial view of assets and PM plans. Completing a PM work order submits its Asset Maintenance Log on the technician's behalf.
4. Managers need **Maintenance Manager**, **Projects Manager** or **System Manager**. In Techy Ops, these roles let them see every work order, assign and reprioritise work, approve or decline requests, and run PM generation.
5. Optional: in **Techy Ops Settings**, enable public requests from asset QR codes and set how many days before the due date PM work orders are created (the default is 3).
6. Realtime updates use the site's standard Frappe socket.io service. The green dot in the Ops header shows that live updates are connected. Without a connection, pages still work, and Refresh reloads the data.

## Lists

- **Pages:** long lists show numbered pages under the list, with *Showing 26–50 of 132*, previous and next buttons, and 25, 50 or 100 rows per page. The page size is remembered on each device.
  - Work requests, customer equipment, assets, project tasks and work history are paged by the server, so the total covers every record.
  - Work orders, procedures, contracts and projects are paged in the browser over what was loaded. Work orders loads the 500 most recently updated jobs; *Load older ones* fetches more.
  - Changing a search, filter or tab returns to page 1. A live refresh keeps the current page.
- **Cards or List:** customer equipment, assets, procedures and ManageIT projects have a **Cards / List** switch. On phones, work orders has the same switch; on a computer it has *Board / List*. Each page remembers its choice on each device.

## Work orders

- Create a work order from **Work orders**, from an asset, or by approving a request. Each one has a priority, category, due date, asset or location, assignees, an optional project, an optional procedure from the library (see [Procedures](#procedures)) and an optional quick checklist.
- The board groups work orders by status: Open (including ERPNext Overdue), In progress (Working), On hold / review (Pending Review) and Done (Completed). The list view adds status filters and search.
- Technicians see the work orders assigned to them or created by them. They can start, hold, complete and reopen them, tick checklist steps, add photos and post updates. They can create work orders but assign them only to themselves.
- Managers can also cancel work orders and change the assignees, priority and due date.
- ERPNext rules still apply. A group work order cannot be completed until its checklist steps are done. If a Task Workflow is active, status buttons are replaced by a link to Desk.
- Updates support `@mentions`. Type `@` and pick a person; that person receives a notification.
- When a work order has a project and a chat channel is linked to that project, its creation and completion are posted to the channel.
- **Adding photos.** Wherever photos are added (work orders, procedure photo steps, requests, project tasks and chat) there are two buttons:
  - **Camera** opens the phone's camera app. On a computer it opens a webcam window with a shutter button.
  - **Upload** (or **Photos** where several can be added at once) opens the gallery or file picker.
  - Photos are shrunk to at most 1600 px and saved as JPEG before upload, so they send quickly on mobile data.

## Offline mode

Technicians can keep working where there is no signal.

- **Getting ready.** Open the Techy app once while online, ideally from the home-screen icon.
  - The app saves itself on the phone, then quietly saves the open jobs assigned to you (up to 40), with their checklists, procedures, parts and history.
  - Any other job you open is saved too, as are the photos you have looked at.
- **Without a connection,** a bar says *You're offline. Showing what's saved on this phone.* You can then:
  - open your jobs and the work order list, and read chat you have already seen;
  - change a job's status, post updates, tick checklist steps, answer procedure steps (photos included), add photos, start and stop the timer, record failure codes and downtime, and write the service report's *Work done*.
  - Each change shows on the job straight away, and updates are marked *saved on this phone, waiting to send*. The bar counts what is waiting.
- **Back online,** the changes are sent in the order they were made. **Send now** sends them straight away.
  - Timer starts and stops keep the time they happened on the phone (up to three days back).
  - A status change made offline wins over one made on the server in the meantime.
- **Refused changes.** If the server refuses a change (for example the job was reassigned or cancelled meanwhile), the bar says so. **Review** lists each one with the reason: **Try again**, or **Discard** to see the job as it is now.
- **Needs a connection:** jobs never opened on the phone, creating jobs, chat messages, parts requests, invoices, and every manager screen.
- **How it works:** a service worker served at `/techy-sw.js` keeps the app's files and page. Jobs and queued changes are stored in the browser (IndexedDB) on that phone only. Signing out of the phone's browser profile, or clearing its site data, removes them; changes not yet sent are lost.

## Dispatch calendar

Managers plan the work under **Dispatch** (sidebar on a computer, name menu on a phone).

- **The board.** Technicians run down the side and days across, by day, week (Monday to Sunday) or two weeks. **Not assigned** holds planned jobs nobody has yet. Each person shows how many jobs they have in view, and a cell with more than four jobs is marked *Busy day*.
  - Technicians are staff with the Maintenance User or Maintenance Manager role, plus anyone with a planned job in view.
- **To plan.** Open jobs with no planned day are listed with the soonest due first, and can be filtered. *Planned earlier, not done* lists open jobs whose planned day has passed.
- **Planning a job.**
  - Drag a job onto a technician and day. Dragging it to another technician moves the job from the first to the second; dragging it to another day just moves the day.
  - Dropping a job back on **To plan** takes it off the plan and keeps its technicians.
  - Or tap a job to choose the day and technician in a dialog. That is also how to plan on a phone, or with the keyboard.
  - A technician who gets a job, or whose job moves to another day, is notified.
- **Due dates.** Planning a job after its due date asks first, then moves the due date to the planned day.
- Completed and cancelled jobs stay where they were done and cannot be moved.
- **In ERPNext:** the planned day is the Task's *Expected Start Date*, and technicians are its assignments, so the plan also shows in Desk.

## Procedures

Procedures are reusable checklists with typed steps, like MaintainX procedures. Find them under **Procedures** in the desktop sidebar, or from the **PM** page on a phone.

- **Step types:** checkbox, Pass / Fail, Yes / No / N/A, number (with an optional minimum, maximum and unit), text, multiple choice, photo, signature, and section headings. Any step except a heading can be marked **Required**.
- **Building:** managers build procedures in an editor that shows a live preview of what a technician will see. There are three starter templates: pump inspection, electrical isolation (LOTO) and fire extinguisher check. Archive a procedure to stop it being added to new work orders.
- **Attaching:** add a procedure when creating or approving a work order, or later from the work order page. To have preventive maintenance work orders include one automatically, choose it for the maintenance task on **PM** (stored in the *Techy Procedure* field on the ERPNext Asset Maintenance Task).
- **Saved copy:** attaching a procedure copies its steps into a *Techy Procedure Run* for that work order. Later edits to the template never change work that's already in progress or done.
- **Answering:** technicians answer steps on the work order, and each answer saves straight away with who answered and when. Photos and signatures are stored as private files on the Task, and signatures don't appear in the photo gallery. The first answer moves an Open work order to In progress.
- **Failures:** a **Fail** answer, or a number outside its range, marks the step as failed. If the step has *Raise a follow-up work order* turned on, a High-priority corrective work order is created once, for the same asset and location. Managers are notified, and the original work order's activity records the reading.
- **Completion rule:** a work order can't be completed while required steps are unanswered. This also applies in ERPNext Desk. Answers are locked once the work order is completed or cancelled; reopen it to change them.
- **Permissions:** only managers can create or edit procedures. A technician can remove a procedure from their work order only if it has no answers yet.

## Work requests

- Any staff member can **Report a problem** with an optional asset and photo. Maintenance Managers are notified.
- Managers review **Pending** requests. **Approve** creates a work order and copies the request's photos to it. **Decline** closes the Issue and records the reason.
- Completing the work order resolves the Issue and notifies the requester.
- Every asset page shows a printable **QR label** linking to `/techy-app/request?asset=…`. By default, the person scanning must sign in. When public requests are enabled, anyone can submit with a name and email. Public submissions are limited to 5 per hour per IP address.

## Customer equipment

Machines you sell and install for customers, such as RO systems, belong to the customer and are not ERPNext Assets. They are tracked as **Techy Equipment** under **Equipment › Customer equipment**.

- **From delivery to installation:**
  - Tick **Track Installs in Techy Ops** on the Item, in ERPNext.
  - When a Delivery Note for that item is submitted, each unit becomes an equipment record. The record holds:
    - the customer, project and Delivery Note;
    - the **site**, from the delivery (shipping) address;
    - what the unit was **built with** (see below);
    - the item's **standard meters** (see *Meter readings*).
  - **Supply and install** (the default):
    - The machine starts as *Awaiting installation*, shown as *Warranty from commissioning*.
    - An **Installation job** is created on the delivery's project. It carries the procedure set in *Techy Ops Settings › Installation Procedure* (for example *RO commissioning*), and managers are notified to schedule it.
    - Its labour defaults to *Included* and its parts to *Internal*, because installation is priced into the sale. Parts approved for it raise Material Requests on the project, so they appear in project costing.
    - Completing the installation job sets the machine to **Active**, records the install date and **starts the warranty**, using the item's *Warranty Period* counted from commissioning. It also submits an ERPNext **Installation Note** against the Delivery Note.
    - If ERPNext refuses the Installation Note, the job still completes and the reason is posted in its activity.
  - **Supply only:** tick **Supply Only (Customer Installs)** on the Delivery Note. The machine is **Active** at once, its **warranty starts on the delivery date**, and no installation job is raised.
  - Cancelling the Delivery Note before installation cancels the machine and its open installation job. This also applies to a supply-only machine.
- **Built with:**
  - Each unit records the materials it was assembled from.
  - The list comes from the delivery project's **manufacturing Work Order** for the item: what was actually consumed, per unit, preferring a completed order.
  - When there is no such Work Order, the list comes from the item's **default BOM**.
  - It is copied at delivery, so later BOM changes do not rewrite it.
  - The machine page lists the components with a link to the Work Order or BOM.
  - When a technician adds parts to a job on that machine, its own parts are listed first, marked *In this machine*.
  - Managers can **Refresh** the list, or **Copy from BOM** for machines delivered before this was recorded.
- **Machines installed earlier:** managers enter them with **Register equipment**. This works whether or not the item uses serial numbers. Serial numbers can be linked when an item has them.
- **Coverage** is shown on the machine, its jobs and its requests:
  - **Warranty from commissioning** while a supplied-and-installed machine waits for installation;
  - **Under warranty** until the warranty end date;
  - otherwise **Service contract** until the contract end date;
  - otherwise **Chargeable**.
- **Jobs and requests** can be raised for a machine. The job shows the customer site with **Call** and **Directions** buttons, and the machine page lists all of its jobs.
- **QR stickers:** each machine has a printable QR sticker. When public requests are on, the customer scans it, sees only the machine model and site, and reports a problem. The request is linked to the machine and the customer.
- **Permissions:** all staff can look up customer equipment. Only managers can register or edit it.

## Service contracts

What each contract covers varies per customer, so contracts are kept as **Techy Service Contract** records (**Equipment › Contracts**). Billing stays on the customer's ERPNext **Subscription**.

- **What a contract holds:**
  - the customer;
  - the linked Subscription (optional), whose dates can be copied with **Use the subscription's dates**;
  - start and end dates;
  - visit frequency (monthly to yearly) and the procedure for visits;
  - **Labour included** on scheduled visits, and **Breakdown call-outs included**;
  - **Parts included at no charge** (any stock items);
  - the customer's machines, each with its next visit date. If left blank, the first visit is one period after the start date.
- **Coverage:** saving a contract sets each machine's *contract end date* and links the contract. Removing a machine or cancelling the contract takes the cover away again. A machine still under warranty shows *Under warranty* first, with the contract alongside.
- **Visits:**
  - Every day, and on demand with **Create due visits**, Techy Ops creates a *Preventive* service-visit job for each machine whose next visit falls within the PM lead time.
  - The job has the contract's procedure attached, and its due date is the visit date.
  - The machine's next visit then moves on by the frequency, so running it twice never creates duplicate visits. Visits stop at the contract end date.
  - Managers are notified and assign the visits.
- **What technicians see:** a job on a contract machine shows the contract terms under the customer site: labour, call-outs and included parts.
- **Payment warnings:** if the linked Subscription is *Grace Period*, *Unpaid* or *Cancelled*, the job and the contract list show a payment warning. The status comes from ERPNext. For example, a subscription whose first period has ended without a paid invoice shows as *Unpaid*.
- **Lists:** the contract list filters Active, Expiring in 60 days (renewals), Expired and Cancelled.
- **Permissions:** only managers can create or change contracts. Cancel the ERPNext Subscription separately when a contract ends.

## Parts on jobs (approval and Material Requests)

1. **The technician lists parts.**
   - On the job, **Add part** searches stock items (in-stock items first). The technician picks the warehouse the part should come from, such as the main store or a van, and the quantity.
   - Lines start as *Not sent*. **Request approval** sends the whole list and notifies the approvers.
2. **A manager or Stock Manager decides.**
   - Approvers are users with Stock Manager, Maintenance Manager or Projects Manager. They can approve or reject each line, or **Approve all**, on the job or from **Parts requests**.
   - Parts requests is in the sidebar and account menu, and on the home screen. People without the Ops app module, such as stock keepers, see only this page.
   - A rejection needs a reason, which the technician sees.
3. **Approval raises the ERPNext Material Request.** There is one Material Request (type *Material Issue*) per company, linked to the job (*Work Order (Techy Ops)* on the Material Request), with each line's warehouse and the job's project.
4. **The stock team fulfils it in ERPNext as usual.** The Stock Entry made from the Material Request marks the lines *Issued*. Cancelling that Stock Entry sets them back to *Approved*, and cancelling the Material Request sends its lines back for approval.

**Rules:**
- A job can't be completed while its list has unsent or undecided lines. Approved lines don't need to be issued first.
- Approved and issued lines can't be removed from the job; cancel the Material Request in ERPNext instead.
- Stock levels are shown to the technician and the approver, but they don't block a request. Out-of-stock items can be approved and bought.

**Billing per line** follows the machine's cover:

| Situation | Billing |
|---|---|
| Job on our own asset, or not on customer equipment | Internal |
| Machine under warranty | Warranty |
| Part on the service contract's *Parts included* list | Contract |
| Anything else | Chargeable, at the *Standard Selling* price |

Managers can change the billing of any line until the job is invoiced. Each machine page lists the parts supplied to it.

## Labour and invoices

- **Labour on each customer job:**
  - Labour is charged **Hourly** (hours × rate) or as a **Flat fee**.
  - The rates come from the Standard Selling prices of the items set in *Techy Ops Settings › Labour Item (per hour)* and *Labour Item (flat fee)*, and can be changed per job.
  - The hourly item must use a unit that allows fractions, such as **Hour**, not *Nos*.
- **Default labour billing:**
  - *Included* when the machine is under warranty;
  - *Included* when its contract covers labour (scheduled visits) or call-outs (other jobs);
  - otherwise *Chargeable*.
- **Who edits labour:** technicians record the hours worked, usually with the job timer (below). Managers and accounts staff change the billing, mode and rates.
- **Creating invoices:**
  - Managers and Accounts Users create a **draft Sales Invoice**.
  - For one job, use **Create invoice** on the job.
  - For several jobs, the **Billing** page groups completed, uninvoiced jobs by customer. Tick the jobs to combine and press **Invoice N jobs together**.
  - The invoice has a labour line per job (hours × hourly item, or 1 × flat-fee item) plus the job's approved chargeable parts, oldest job first. It does not update stock, because parts already left through the Material Request.
  - The invoice stays a draft for accounts to review and submit.
- **No double invoicing:** each job is invoiced once. Cancelling or deleting the invoice in ERPNext frees its jobs to be invoiced again.

## Job timer

The **Time on job** card on each work order has a **Start timer** button.

- **Starting:** the clock runs for the person who pressed it. Starting it moves an open or on-hold job to *In progress*.
- **One clock per person:** starting on another job stops the clock on the first one.
- **Running banner:** while your clock runs, a bar at the top of every Ops screen shows the job and the time. Tap it to go back to the job.
- **Stopping:** press **Stop**. Putting the job on hold, completing it or cancelling it stops every clock on it, including teammates' clocks.
- **Several people:** each person runs their own clock. The card shows who is on the job now. Managers can stop someone else's clock.
- **Corrections:**
  - **Add time you forgot to clock** records time without the clock. Managers can record it for an assignee.
  - Each entry can be changed (in minutes) or deleted by the person who logged it, or by a manager, until the job is invoiced.
- **Labour hours:** the job's billable hours follow the logged total. If someone types other hours (a minimum call-out charge, say), those hours are kept. The labour card then shows the logged total with a **Use … hours** button.
- **Reports** use the logged time per person for technician hours and for the labour cost of contracts. Jobs without timer entries fall back to the typed hours, shared between the assignees.
- **In ERPNext:** every entry is a *Techy Time Log* (job, technician, start, stop, hours, timer or added by hand). Managers can read and export them.

## Failure codes and downtime

The **Failure & downtime** card on repairs and on jobs for a machine records what went wrong and how long the machine was out of service.

- **Codes.** Pick a **Problem** (what was wrong), a **Cause** (why) and a **Remedy** (what fixed it).
  - Managers keep the lists under **Reports › Failure codes**. **Add common water-treatment codes** fills an empty list with codes such as Leak, Membrane fouling or scaling, and Replaced part.
  - Managers can add codes or disable old ones. Jobs that already use a disabled code keep it.
  - The codes are *Techy Failure Code* records in ERPNext.
- **Required codes (optional).** Turn on *Techy Ops Settings › Require Problem and Cause Codes to Complete a Repair*. Corrective jobs on customer equipment or our assets then cannot be completed until both are chosen; the job points to the card.
- **Downtime.** Tick **Machine is down** when creating a job for a machine, or **Machine was down** on the card.
  - Downtime counts from that moment. Change **Down from** if the machine stopped earlier.
  - Completing the job puts the machine back in service. Fill in **Back in service** (or press **Back in service now**) if it ran again before the job was closed.
- **Reports** show:
  - **Downtime:** total hours down, stoppages and average time to repair, plus each machine's hours down, its availability for the period, and a *Down now* flag;
  - **Failures:** the most common problems and causes, and how many repairs were coded.
  - A stoppage that started before the period counts only its hours inside it.

## Meter readings

Customer equipment and our own Assets can have **meters**. Managers add them on the machine page with **Add meter**. Presets cover common RO meters: running hours, product water, permeate TDS, feed pressure and filter pressure drop.

- **Type:**
  - A **Counter** only goes up, like running hours or m³ produced. A reading lower than the last one is refused. If a meter was replaced or reset, a manager records the lower reading and confirms it.
  - A **Gauge** goes up and down, like TDS or pressure.
- **Triggers** raise jobs automatically, with an optional procedure, priority and job title:
  - **Every N** (counters only) raises a Preventive service job when the counter reaches *Next due at*, then moves the next due reading on by N. The machine page estimates the date from recent use.
  - **Goes above / Goes below** raises a Corrective job, High priority by default, when a reading crosses the limit.
  - Each trigger has one job open at a time. Further readings past the limit are added to the open job as comments. The next job is raised only after that one is completed or cancelled.
  - Managers are notified of every job raised.
- **Recording:**
  - Technicians record readings on the machine page, or on the job page while they work on that machine. A reading taken on a job is noted on the job.
  - The card shows the last reading, a trend line and any meter past its limit.
- **History:** select a meter's name to see the chart, with limit lines, and every reading with who took it, the job it was taken on and any job it raised. Managers can delete a mistaken reading; the meter then falls back to the previous one.

- **Standard meters per item:**
  - In ERPNext, open the Item and list its meters under **Techy Ops Meters › Standard Meters**: name, unit, type, *Service Every*, *Alert Above* and *Alert Below*.
  - Every new machine of that item gets those meters at delivery, or when it is registered by hand.
  - On older machines, managers press **Add standard meters**. Meters the machine already has, matched by name, are skipped.
- **Readings from procedures:**
  - A *Number* step in a procedure can name a meter under **Save to meter**, for example *Permeate TDS*.
  - When a technician answers that step on a job, the answer is also recorded as that meter's reading on the job's machine.
  - Correcting the answer replaces the reading; clearing it removes the reading.
  - This is how the commissioning checklist records each machine's first TDS, pressure and running-hours readings.
  - If the machine has no meter with that name, the answer is saved as a normal answer.

The records are *Techy Meter* (with its *Techy Meter Trigger* rows), *Techy Meter Reading* and, on Items, *Techy Meter Template*. All are visible in ERPNext Desk.

## Service reports

Every job has a **Service report** card. It produces a PDF for the customer.

- **Contents:**
  - the company's default ERPNext letter head;
  - customer, site and equipment, with serial number and warranty or contract cover;
  - when the job was reported, started and completed, and the technicians;
  - the reported problem and the **Work done** summary;
  - checklist steps, and procedure answers with readings and out-of-range results;
  - meter readings taken on the visit;
  - parts fitted, showing whether each was covered or chargeable (prices stay on the invoice);
  - labour hours;
  - up to 8 photos;
  - the customer's signature (the procedure's Signature step);
  - the next service: the next contract visit, and meter services with their estimated date;
  - the footer from *Techy Ops Settings › Service Report Footer*.
- **Work done:** the technician (or a manager) writes what was found and done in plain words. It can be written or corrected after the job is completed.
- **Preview PDF** opens the report. Anyone who can open the job can preview it.
- **Email to customer:**
  - The report is sent through ERPNext with the PDF attached. It is logged on the job's timeline in Desk, and the card shows when and to whom it was last sent.
  - Technicians on the job can send only to the customer's addresses on file: the customer's email and its contacts' emails. Managers can add other addresses.
  - Emails need an outgoing *Email Account* in ERPNext.
- **Automatic email:** tick *Techy Ops Settings › Email the Service Report when a Customer Job is Completed* to send it to the customer's first address on file as soon as the job is completed. It is off by default.
- **Invoices:** creating an invoice attaches each job's report PDF to the draft Sales Invoice.

## Reports

Managers open **Reports** from the sidebar, or from the account menu on a phone. Choose a period: 7 days, 30 days, 90 days or 12 months. The headline figures are compared with the period before.

- **Work:**
  - jobs completed and opened;
  - jobs open now and overdue;
  - average time to fix repairs (Corrective jobs, from opened to completed);
  - average time to start (from opened to first set to Working);
  - a chart of jobs opened and completed per day, week or month.
- **Preventive maintenance:** Preventive jobs due in the period are counted as on time (completed by the due date), late, missed (still open after the due date) or upcoming. *PM done on time* is on time ÷ (on time + late + missed). Late and missed jobs are listed.
- **Requests:** received, turned into jobs, declined and waiting. Jobs are also broken down by type, with each type's average time to finish.
- **Technician scorecard:** how much each person did and how well. For jobs they completed in the period:
  - **On time:** finished by the due date (jobs with a due date only).
  - **Fixed first time:** repairs where the same machine needed no other repair opened within 30 days of completion.
  - **Sent back:** jobs that went back to work after review or completion. Each return is counted on the job (*Times Sent Back* on the Task) from this update on; older jobs count as never sent back.
  - **Coded:** repairs with both a problem and a cause code.
  - Average time to finish, hours logged per job (from the job timer; jobs without entries share their typed hours between the assignees), and open jobs with how many are overdue.
  - **Score** out of 100: on time 30, fixed first time 35, not sent back 20, coded 15. Only the measures that apply to someone's jobs count, and people with fewer than 3 completed jobs in the period are not scored. The best score is named above the table. Click a person to see the jobs that lowered their score, with a link to the follow-up repair for each repeat.
  - Read it alongside the work mix: someone given the hardest breakdowns will have more repeats than someone doing routine visits.
- **Machines with the most repairs:** customer equipment and our own assets with the most repair jobs opened in the period. Repeat breakdowns are worth a closer look.
- **Service contract profit:**
  - **Money in** is the contract's subscription invoices plus invoices for extra work on its machines. Only submitted invoices count.
  - **Money out** is the parts issued at stock valuation cost plus labour hours × *Techy Ops Settings › Labour Cost per Hour*. Set that to what an hour of technician time costs you; until it is set, labour is not costed.
  - Contracts losing money are listed first.

The **Machines** tab covers the equipment side for the same period:

- **Cost and reliability**, per machine or per customer:
  - jobs done and breakdowns (repair jobs opened);
  - **time between breakdowns** (MTBF): the machine's running time in the period, from when it went into service, less its downtime, divided by its breakdowns;
  - hours down;
  - parts at stock cost, labour hours at your cost per hour, and the total.
- **Preventive maintenance by customer:** done on time, late and missed per customer. Open a customer to see each machine's figures.
- **Cover ending soon:** machine warranties and service contracts ending in the next 30, 60 or 90 days, as renewals to offer.

**Excel** downloads every table for the period as one workbook, a sheet per table. **Print / PDF** prints the tab you are on (choose *Save as PDF* in the print dialog). Both are for managers.

Jobs record when they were first started and when they were completed (*Started At*, *Completed At* on the Task). Jobs completed before this update use their last-modified time instead.

## Root cause investigations

When a problem keeps coming back, or a customer needs a proper explanation, open **Investigations** in the sidebar, or press **Investigate root cause** on a repair, inspection or safety job, or on a machine. Starting from a job fills in the problem, customer, site and machine, plus the job's failure codes. Anyone with Techy Ops can start and edit an investigation.

- **Problem:** what went wrong, what was measured against the target (e.g. 10 mg/L, target 0.5 mg/L), the site investigation and follow-up dates, what happened, and the RCA focus.
- **Causes and evidence (6M):** add causes under Method, Machine, Material, Manpower, Measurement or Management. Each has:
  - its evidence and actual vs required;
  - a status: *Confirmed* (documented on site), *Reported* (an account still to verify), *Potential* (to investigate) or *Open*;
  - the corrective or preventive action, its owner (e.g. Engineering / QC), a due date, the closure evidence, and *Action done*.
- **Fishbone diagram:** drawn from the causes each time you save (up to 7 per heading; the rest stay in the evidence table).
- **5 Whys:** each why with its answer and evidence (one point per line), then the **root cause**, **contributing factors** (one per line) and **closure requirements**.
- The machine's recent jobs, with their failure codes, are listed as evidence to draw on.
- **PDF report** (landscape, on the default letter head): the fishbone with the RCA focus, the RCA evidence table and closure requirements, then the 5 Whys with the root cause and contributing factors. Save first: the PDF shows what is saved.
- **Closing:** managers close an investigation once it has causes and a root cause, and every action is done with its closure evidence. A closed investigation is read-only until a manager reopens it. Managers can also delete one.
- In Desk the records are *Techy Investigation*.

## Assets and preventive maintenance

- **Assets** lists ERPNext Assets with their open work count. An asset page shows the PM schedule, work order history, requests and the QR label.
- To schedule recurring work, create an **Asset Maintenance** record in ERPNext with its tasks, periodicity and assignee. ERPNext plans an Asset Maintenance Log for each task.
- A daily job creates a *Preventive* work order for each Planned or Overdue log due within the configured lead time. Managers can also run it from **PM**. The job never creates a second work order for the same log.
- Completing the work order submits the log as Completed, and ERPNext then calculates the next due date and plans the next log.
- If the maintenance task requires a certificate, attach a photo or file before completing. The first attachment is used as the certificate.

## Chat

- Channels can be public (anyone can browse and join) or private (invite only). Direct messages are private two-person channels.
- Any staff member can create a channel. Only managers can link a channel to a project.
- Messages update in real time. You can reply in threads and `@mention` people. Unread counts appear in the sidebar and on the Chat tab.
- **Linking records.** You can link a task, work order, project, asset or request in any message or work order update:
  - Type `/` to search tasks, or `$` to search projects. Tabs at the top of the picker switch to the other record types.
  - Type a keyword followed by a space, such as `task `, `project `, `work order ` (or `wo `), `asset ` or `request `, and the matching picker opens.
  - On a phone, tap the link button next to Send.
  - To insert a record, tap it or press Enter. For a typed keyword, press Tab or use the arrow keys first, so that Enter still sends a sentence like "the task is done".
  - Links are stored as `[[project:PROJ-0001]]`. In messages they appear as chips showing the record's title, and tapping a chip opens the record in Techy Ops, Techy Work or Techy Manage (or in Desk if you don't have that app). Older `#TASK-…` references appear the same way.
  - A chip shows the title only to readers allowed to open the record on its own screen. Anyone else sees the ID as plain text. Notifications show links as "Project PROJ-0001".
- **Photos.** The camera and photo buttons in the message box add up to 6 photos to a message, with or without text. Tap a photo to open it full size.
  - Chat photos are private files attached to the channel. In a private channel or direct message, only its members can open them.
  - Deleting a message deletes its photos (copies on work orders stay).
- **Message to job.** Hover over a message (or tap it on a phone) and press the tool button to create a work order from it.
  - The form opens with the message as the title and description.
  - The message's photos are copied to the new job, and the job's activity says which message it came from.
  - A link to the job is posted in the message's thread.
  - It works for any message you can read, including one in a channel you have not joined, but not for a private channel you are not in.
- **Reactions.** Hover over a message (or tap it on a phone) and press the smiley to react with 👍 ✅ 👀 🙏 🎉 ❤️ 😂 or ⚠️. Tap a reaction to add yours or take it back. Hovering a reaction shows who reacted. Everyone sees reactions as they happen.
- **Pins.** The bookmark button pins a message to the conversation, such as a gate code or a delivery date. A note says who pinned it.
  - The bookmark in the conversation header lists the pinned messages, with **Show in chat** and **Unpin**.
  - Any member can pin or unpin, up to 50 pins per conversation.
- **Search.**
  - **Search all messages** on the Chat page covers every conversation you can open. Private channels and direct messages you are not in are never searched.
  - The magnifier in a conversation header searches only that conversation.
  - Opening a result jumps to the message and highlights it. A reply opens in its thread. **Jump to latest messages** returns to the newest messages.
- **Typing.** "Tina is typing…" shows under the conversation, or under the thread for replies, while someone writes.
- **Status.** Open your name menu and choose **Set a status**.
  - Pick a quick status (🚐 On site, 🚗 Driving, 🍽️ At lunch, 🤝 In a meeting, 🤒 Off sick, 🏖️ On leave) or type your own with an emoji.
  - Choose when it clears: 30 minutes, 1 hour, 4 hours, today, or never.
  - The emoji shows next to your name in messages. The full status shows in direct messages, the member list and the Chat page.
- **Online and away.**
  - A green dot means the person has a Techy app open now (checked about once a minute).
  - A grey ring means away or offline. **Set yourself away** in the name menu shows the grey ring even while your app is open, and keeps your status text.
  - Dots appear on direct messages in the sidebar and on the Chat page, in a direct message's header, and in a channel's member list.
- **Reminders.** The clock button on a message reminds you about it in 20 minutes, 1 hour, 3 hours, tomorrow at 8:00 or next Monday at 8:00.
  - When it is due, a pop-up appears in any open Techy app and stays until dismissed. A notification also lands in the bell in Desk and Techy.
  - Tapping the pop-up opens the message.
  - Upcoming reminders are listed on the Chat page, where you can cancel them. You can have up to 50 waiting.
  - Deleting a message cancels reminders still waiting on it.
  - Reminders are sent by a job that runs every minute, so the site's scheduler must be running (`bench enable-scheduler`, with the `bench schedule` process running in production).
- Members of a direct message are notified of every message. In channels, only @mentioned members are notified.
- Authors can delete their own messages; managers can delete any message. Deleting a thread root also deletes its replies.
- Private channels are hidden in Desk from non-members through permission hooks. System Managers can administer all channels in Desk.

## Verification on staging

Local tests: `python -m unittest discover -s tests -v` and `yarn build`. They mock Frappe, so test the following on a v16 staging site with technician and manager accounts:

- Create a work order with a checklist and two assignees. Complete the steps, then the work order. Confirm that ToDos close and that the board updates live for the other user.
- Submit a request with a photo. Approve it, complete the work order, and confirm the Issue is resolved and the requester notified. Decline a second request.
- Create an Asset Maintenance record with a task due tomorrow. Run **Create due work orders now**, complete the work order, and confirm the log is submitted and the next due date has moved.
- Print a QR label and scan it while signed out, with public requests both off and on.
- Create public and private channels and a direct message. Check unread counts, threads, mentions, realtime delivery across two browsers, and that a non-member cannot open a private channel in Desk or the app.
