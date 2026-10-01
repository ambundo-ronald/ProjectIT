# Project tasks and checklists

Techy App uses ERPNext's existing Task tree, ToDo assignments, comments, attachments and Timesheet task links. No new DocTypes or checklist database tables are introduced.

## Desktop

On a saved Project, use the Techy App button group:

- Project Tasks opens the native filtered Task list (including native list/tree/board tools).
- New Task opens the standard Task form with Project filled in.
- New Checklist opens a group Task. Save it, then use Add Checklist Step on its form to create child Tasks. Use Checklist Steps to view the children.

Assign the group and each step using ERPNext's Assign To sidebar. Assigning a parent does not automatically assign existing children. Use native descriptions, deadlines, priority, attachments and comments. Open in Techy App deep-links to the same task on mobile.

## Mobile

Techy Work > Tasks lists the signed-in user's assigned project tasks. Techy Manage > Tasks lists tasks permitted by ERPNext and offers New task / checklist to Project Managers. The create form creates a group plus child Tasks when steps are supplied, assigning every created Task to the selected employee through standard Assign To. Existing records can be reassigned through their standard ERPNext form.

Open a task to view its steps, instructions, status, priority, attachments and comments. Employees can update permitted statuses, add comments and attach private JPEG/PNG photos. Refresh retrieves desktop changes. Completed assignments remain visible via their closed ToDos; cancelled assignments are excluded. Lists are paginated.

At project check-in, an optional Task selector lists assigned, open leaf Tasks for that project. The chosen Task stays on all regular/overtime Timesheet rows at checkout, feeding ERPNext's task time/cost calculations. Project-only check-ins continue to work.

## Permissions and workflows

- Employees need an active linked Employee with WorkIT enabled, allocation to the project, a ToDo assignment to each Task, Project read, and the appropriate native Task permissions. Native Assign To may share read access only: grant scoped Task write access for status updates, comments and photos. Private uploads also need File create permission.
- Managers using the task creation API need Projects Manager or System Manager, Project write, and Task create permissions. Enable ManageIT to expose their mobile manager screen. Being given ManageIT alone does not grant management rights.
- Desktop remains governed by ERPNext's native permissions. Configure User Permissions/sharing appropriately; these APIs do not grant broad Task permissions or alter role definitions.
- ERPNext validates dependent Tasks before completion and closes assignments on completion. Standard Pending Review is a status, not enforced manager approval. If you need mandatory approval, configure an ERPNext Task Workflow. Direct mobile status writes are blocked while a Task Workflow is active; Open in ERPNext provides its native workflow actions.
- API writes check document permissions and stale status versions. An existing task's project or assignee cannot be changed through the status endpoint.

## Deployment and verification

Run `bench build --app projectit`, migrate the site and clear its cache to load the Task form script. Restart services as appropriate for the deployment.

Local tests: `python -m unittest discover -s tests -v` and `yarn build`. These use mocked Frappe services; no live v16 site is available in this workspace.

On v16 staging, create a Project/group/child Tasks in Desk, assign each to an allocated employee, and verify they appear on mobile. Complete child Tasks, then complete the parent; check dependency validation, ToDo closure and shared visibility. Test private photos, comments, stale edits, an unassigned employee, a different project, and configured workflows. Create a checklist on mobile and verify the native Task tree/assignments in Desk. Check in against a leaf Task and verify that every checkout Timesheet row retains that task and native actual time updates. Validate the site's scoped permissions for both employee and manager roles.
