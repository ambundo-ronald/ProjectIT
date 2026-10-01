# Techy App mobile frontend

Vue 3, Frappe UI, Tailwind CSS, and Vite frontend for Techy App 16.

Use Node.js 24+ and Yarn 1.22+ with a running Frappe/ERPNext/HRMS v16 site.

```sh
yarn install --frozen-lockfile
yarn dev
yarn build
```

Open the Vite dev server with your Bench site's hostname and `/techy-app` path. The development proxy discovers the Bench webserver port, defaulting to 8000 outside a Bench. Set `FRAPPE_URL` to override the backend URL. It preserves the request hostname for site resolution. Production assets use `/assets/projectit/projectit/`; the build script copies HTML to both `techy-app.html` and `projectit.html` under `projectit/www/` using portable Node filesystem APIs.

The visible brand is Techy App; legacy API paths, stored module names, and `/projectit` routes remain compatible. The manifest retains the original app identity and uses the new launch URL. Service-worker registration remains disabled as in the original app; offline operation and push delivery are not provided by this rebrand.

Do not disable CSRF protection on production sites. Use the site's normal session authentication and CSRF token.
