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
2. On each Employee, add **Ops** to *Techy App Access*. Signing in to the app then shows a **Techy Ops** button.
3. Give technicians a role with Task read/write and File create (for example *Projects User*), plus **Maintenance User** for the Assets and PM screens. ERPNext gives the maintenance roles no Asset access, so Ops shows Maintenance Users, managers and anyone with Asset read a read-only, non-financial view of assets and PM plans. Completing a PM work order submits its Asset Maintenance Log on the technician's behalf.
4. Managers need **Maintenance Manager**, **Projects Manager** or **System Manager**. In Techy Ops, these roles let them see every work order, assign and reprioritise work, approve or decline requests, and run PM generation.
5. Optional: in **Techy Ops Settings**, enable public requests from asset QR codes and set how many days before the due date PM work orders are created (the default is 3).
6. Realtime updates use the site's standard Frappe socket.io service. The green dot in the Ops header shows that live updates are connected. Without a connection, pages still work, and Refresh reloads the data.

## Work orders

- Create a work order from **Work orders**, from an asset, or by approving a request. Each one has a priority, category, due date, asset or location, assignees, an optional project, an optional procedure from the library (see [Procedures](#procedures)) and an optional quick checklist.
- The board groups work orders by status: Open (including ERPNext Overdue), In progress (Working), On hold / review (Pending Review) and Done (Completed). The list view adds status filters and search.
- Technicians see the work orders assigned to them or created by them. They can start, hold, complete and reopen them, tick checklist steps, add photos and post updates. They can create work orders but assign them only to themselves.
- Managers can also cancel work orders and change the assignees, priority and due date.
- ERPNext rules still apply. A group work order cannot be completed until its checklist steps are done. If a Task Workflow is active, status buttons are replaced by a link to Desk.
- Updates support `@mentions`. Type `@` and pick a person; that person receives a notification.
- When a work order has a project and a chat channel is linked to that project, its creation and completion are posted to the channel.

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
    - the **warranty end**, set from the item's *Warranty Period* and counted from the delivery date.
  - Its status starts as *Awaiting installation*, and an **Installation job** is created. That job carries the procedure set in *Techy Ops Settings › Installation Procedure* (for example *RO commissioning*), and managers are notified to schedule it.
  - Completing the installation job sets the machine to **Active**, records the install date, and submits an ERPNext **Installation Note** against the Delivery Note.
  - If ERPNext refuses the Installation Note, the job still completes and the reason is posted in its activity.
  - Cancelling the Delivery Note before installation cancels the machine and its open installation job.
- **Machines installed earlier:** managers enter them with **Register equipment**. This works whether or not the item uses serial numbers. Serial numbers can be linked when an item has them.
- **Coverage** is shown on the machine, its jobs and its requests:
  - **Under warranty** until the warranty end date;
  - otherwise **Service contract** until the contract end date;
  - otherwise **Chargeable**.
- **Jobs and requests** can be raised for a machine. The job shows the customer site with **Call** and **Directions** buttons, and the machine page lists all of its jobs.
- **QR stickers:** each machine has a printable QR sticker. When public requests are on, the customer scans it, sees only the machine model and site, and reports a problem. The request is linked to the machine and the customer.
- **Permissions:** all staff can look up customer equipment. Only managers can register or edit it.

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
