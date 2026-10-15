"""Offline support for the Techy app.

The app's service worker is built into /assets/projectit/projectit/sw.js, but a service worker only controls pages
under its own folder. This page renderer serves it at /techy-sw.js so it can control /techy-app: it keeps the app's
files and its page for use without a connection. The jobs a technician has open are kept in the browser by the app,
and changes made offline wait there until the connection is back (see mobile/src/data/offline.js).
"""
from pathlib import Path

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

ROUTE = "techy-sw.js"


class ServiceWorker(BaseRenderer):
    def can_render(self):
        return self.path == ROUTE

    def render(self):
        path = Path(frappe.get_app_path("projectit", "public", "projectit", "sw.js"))
        body = path.read_bytes() if path.exists() else b"/* The Techy app has not been built on this site. */"
        response = Response(body, mimetype="application/javascript")
        # Browsers check for a new worker on every visit, so a deploy reaches phones on their next visit.
        response.headers["Cache-Control"] = "no-cache"
        return response
