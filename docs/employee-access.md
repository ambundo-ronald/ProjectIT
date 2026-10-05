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

Installation and future migrations repair missing app-owned fields and module choices automatically. Existing Employee child rows and User roles are not changed. The repair removes only the exact obsolete Employee field-order export shipped by this app; independently customized layouts are preserved. If a site's custom layout explicitly hides the fields, adjust that layout in Customize Form.

This code does not deploy itself. The server must have the updated source before running the repair method. Run locally available unit tests with `python -m unittest discover -s tests -v`; live schema creation requires a v16 Bench staging check.
