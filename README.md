# Techy App

Techy App 16 is an open-source field workforce and project tracking app for Frappe, ERPNext, and Frappe HR version 16.

Employees can check in and out with photos and GPS, view their allocations and instructions, and record project time. Managers can allocate employees, share instructions, and view team activity. The mobile sections are **Techy Work** and **Techy Manage**.

## Requirements

- Frappe, ERPNext, and HRMS: `>=16.0.0,<17.0.0`
- Python 3.14+, Node.js 24+, Yarn 1.22+
- A configured Frappe Bench and MariaDB 11.8 (see the official installation guide)
- HTTPS for camera and geolocation access on mobile devices

See [Frappe installation](https://docs.frappe.io/framework/user/en/installation) and the [v16 migration guide](https://github.com/frappe/frappe/wiki/Migrating-to-version-16).

## Installation

Use this Techy App checkout, or your own fork containing these changes, in a version-16 Bench. Do not install the original upstream repository expecting this rebrand.

```sh
bench get-app /absolute/path/to/this/checkout
bench --site your-site install-app projectit
bench build --app projectit
bench --site your-site migrate
```

ERPNext and HRMS must already be installed on the site. Open `https://your-site/techy-app` and sign in with your site credentials. On iOS, use Safari's Share menu and Add to Home Screen. On Android, use the browser's install/Add to Home Screen option when available.

## Existing installations

The product is named **Techy App**, but the Python/Bench app key remains `projectit`. Existing module identifiers, DocTypes, custom fields, API paths, asset paths, and stored WorkIT/ManageIT assignments are retained to preserve existing data. `/projectit` and its nested routes remain usable; `/techy-app` is the new public entry point.

Back up the site, upgrade the Bench and all three platform apps to version 16 using their official migration guides, then update this app checkout and run:

```sh
bench setup requirements
bench build --app projectit
bench --site your-site migrate
bench --site your-site clear-cache
```

Restart the deployment's services after the upgrade. Verify login/logout, both module assignments, allocations, instructions, photo/GPS check-in and checkout, timesheets, and attendance on a staging site before production. Existing installations may need to refresh or reinstall their home-screen shortcut to pick up the new branding.

## Attendance

Techy App records IN/OUT punches and delegates Present/Half Day/Absent decisions to HRMS shift rules. See [attendance setup and staging checks](docs/attendance.md).

## Tasks and checklists

Use ERPNext Tasks and child Tasks on mobile and desktop. See [task setup and usage](docs/tasks.md).

## Development

```sh
yarn install
yarn dev
yarn build
```

The frontend is in `mobile/`; the backend and custom DocTypes are in `projectit/`. The build creates both branded and legacy HTML entry points under `projectit/www/`. See [mobile development](mobile/README.md).

## Validation status

Version 16 runtime constraints and relevant API/configuration changes are included. Full compatibility still requires the staging-site checks above; a frontend build alone cannot validate Frappe permissions, database migration, or HRMS behavior.

## License and attribution

GPL-3.0. Techy App is derived from [ProjectIT by Arus Info](https://github.com/Arus-Info/ProjectIT). Original copyright and author attribution are retained. See [license.txt](license.txt).
