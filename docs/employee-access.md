# Who can open which Techy app

| App | Opens for |
|---|---|
| **Techy Ops** | *Ops* ticked under Techy App Access on the person's Employee, **or** the user has Maintenance User, Maintenance Manager, Projects Manager or System Manager |
| **Techy Work** | *WorkIT* ticked on the Employee, or a System Manager who has an active Employee (checking in needs one) |
| **Techy Manage** | *ManageIT* ticked on the Employee, or a System Manager |

- **Home** (the app list) is always open. Someone with a single app goes straight into it right after signing in, or when they open the app from its start address. **All apps** in the name menu always brings them back to Home.
- **Ops pages that need more than Techy Ops** open only for the people allowed to use them:
  - **Billing:** managers and accounts staff.
  - **Parts requests:** parts approvers, including stock keepers without Techy Ops.
  - **Reports** and **Dispatch:** managers.
  - Their data is checked on the server as well.
- The rule lives in `projectit/api.py` (`apps_for`). The home page, the app's routes and the server's Techy Work and Techy Manage endpoints all use it.
- **What the apps can do** follows the roles below. Managers need Projects Manager to change project crews.

# Roles and rights

| Person | Roles to give | What they can do |
|---|---|---|
| **Technician** | Employee, **Maintenance User** (and *WorkIT* ticked if they also check in to projects) | Their own jobs and tasks; open jobs nobody has, to pick up |
| **Field staff** (projects only) | Employee, with *WorkIT* ticked | Their own project tasks, in the projects they are allocated to |
| **Maintenance manager** | Maintenance Manager (and Projects Manager for project crews) | Every job: assign, prioritise, complete, reports, dispatch, billing |
| **Office / project planner** | Projects User or Projects Manager | ERPNext's normal access to all tasks and projects |

**Do not give technicians Projects User.** It lets them see, change and delete every task in the company in ERPNext. The app no longer needs it: technicians and field staff get just enough rights from Maintenance User and Employee. Remove Projects User from technicians in *User › Roles*.

## What a technician can do

On jobs **assigned to them or created by them**:
- open them, start work, put them on hold, and resume;
- tick checklist steps, answer procedures, add updates, photos and time (timer or forgotten time);
- request parts, record meter readings and failure codes, and write the customer report;
- **send the job for review** when it is finished (the same checks as completing: required steps, failure codes, certificate);
- take back a job they sent for review, if they need to fix something;
- change the **due date**;
- **add a helper** from the team.

They can also:
- see **open jobs nobody is assigned to** (Work orders › *Available*), and **take one**, which assigns it to them;
- create jobs for themselves, report problems, look up customer equipment, and start investigations.

Technicians **cannot**:
- complete, reopen or cancel a job, or change its priority;
- take anyone off a job;
- open or change other people's jobs;
- approve parts or requests;
- see Reports, Dispatch or Billing;
- **delete** any task.

In ERPNext Desk they see only their own tasks, plus the open jobs nobody has, and can never delete. Field staff likewise see only the projects they are allocated to.

## Review

- A technician's **Send for review** shows the job as **Waiting for review** and tells the managers.
- Managers find these jobs under Work orders › **To review**. On each one they either:
  - **Approve & complete**: completes the job; the service report and the customer's rating link go out as usual.
  - **Send back**, with what still needs doing: the job returns to *In progress*, the reason is posted on the job and sent to the technicians, and it counts as *sent back* on the scorecard.
- **On hold** (waiting for parts, say) is separate from review. Resuming a job on hold does not count against anyone.

## How it works

- Migrating the app gives the **Maintenance User** and **Employee** roles Task read and write (Maintenance User also create), and Project read. It only ever adds these rights.
- `projectit/permissions.py` then narrows them to each person's own work, for lists, forms and reports in Desk and in the app.
- People with Projects User, Projects Manager, Maintenance Manager, HR or System Manager keep ERPNext's normal access.
- Checking out of a project submits the person's own timesheet for them, so field staff don't need the right to submit timesheets in general.

# Restore missing Techy App access fields

Run from the server's Bench directory, replacing `your-site` with the actual site name:

```sh
bench --site your-site list-apps
```

The app must appear as `projectit` (its internal name). If missing, install it after ensuring ERPNext and HRMS v16 are installed:

```sh
bench --site your-site install-app projectit
```

Update the app checkout to include this repair, then run:

```sh
bench --site your-site migrate
bench --site your-site execute projectit.setup.ensure_access_fields
bench --site your-site clear-cache
```

Reload the Employee form. Look for **Techy App Access** and **Techy App Modules** near Grade. Staff use WorkIT; managers use ManageIT; managers recording their own time need both. Ensure User ID is linked to the employee's enabled account. Managers still need Projects Manager on the linked User for task management. Module selection does not grant native document permissions.

**Project crews and instructions:**
- Only **Projects Manager** and **System Manager** can change *Project Allocation and Instrucions*, which hold project crews and site instructions. This applies in ManageIT and in Desk.
- **Projects User** can read allocations but not change them, because crew membership decides who may check in to a project.
- The allocation's own code enforces this as well. A *Custom DocPerm* that grants write to other roles therefore has no effect.

Installation and future migrations repair missing app-owned fields and module choices automatically. Existing Employee child rows and User roles are not changed. The repair removes only the exact obsolete Employee field-order export shipped by this app; independently customized layouts are preserved. If a site's custom layout explicitly hides the fields, adjust that layout in Customize Form.

This code does not deploy itself. The server must have the updated source before running the repair method. Run locally available unit tests with `python -m unittest discover -s tests -v`; live schema creation requires a v16 Bench staging check.
