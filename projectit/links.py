"""Document links in chat and comments: [[kind:name]] tokens for tasks, work orders, projects, assets and requests.

The composer searches with search_links; readers resolve tokens with resolve_links. Both apply the same
visibility as each document's own Techy screen, so a link never reveals a title its reader could not open.
"""
import re

import frappe

from projectit import ops

TOKEN = re.compile(r"\[\[(task|work-order|project|asset|equipment|request):([^\[\]\n]{1,140})\]\]")
LABELS = {"task": "Task", "work-order": "Work order", "project": "Project", "asset": "Asset", "equipment": "Equipment",
    "request": "Request"}
KINDS = {
    # kind: (doctype, title field, detail field, base filters)
    "task": ("Task", "subject", "status", {"custom_work_order": 0, "is_template": 0, "project": ["is", "set"]}),
    "work-order": ("Task", "subject", "status", {"custom_work_order": 1, "is_template": 0,
        "parent_task": ["is", "not set"]}),
    "project": ("Project", "project_name", "status", {}),
    "asset": ("Asset", "asset_name", "location", {"docstatus": ["<", 2]}),
    "equipment": ("Techy Equipment", "equipment_name", "customer_name", {"status": ["!=", "Cancelled"]}),
    "request": ("Issue", "subject", "status", {"custom_maintenance_request": 1}),
}

# People look machines up by customer, sticker tag or site rather than by model.
EXTRA_SEARCH = {"equipment": ("customer_name", "tag", "site")}


def readable(content):
    """Plain text for notifications: [[project:PROJ-0001]] becomes 'Project PROJ-0001'."""
    return TOKEN.sub(lambda m: f"{LABELS[m.group(1)]} {m.group(2)}", content or "")


def _scope(kind):
    """Extra filters limiting rows to what the user may open in Techy, or None for no access."""
    if kind == "task":
        from projectit import tasks
        if tasks._manager():
            return {}
        try:
            projects = tasks._allocated_projects()
        except frappe.PermissionError:
            return None  # no single active Employee: no project tasks
        return {"project": ["in", projects or [""]], "name": ["in", tasks._assigned_names() or [""]]}
    if kind == "work-order":
        if ops.manager():
            return {}
        from projectit import work_orders
        owned = frappe.get_all("Task", filters={"custom_work_order": 1, "owner": frappe.session.user}, pluck="name")
        return {"name": ["in", list(set(work_orders._mine()) | set(owned)) or [""]]}
    if kind == "asset":
        try:
            ops.require_asset_access()
        except frappe.PermissionError:
            return None
        return {}
    if kind == "request":
        return {} if ops.manager() else {"raised_by": frappe.session.user}
    return {}


def _rows(kind, txt=None, names=None, limit=8):
    doctype, title, detail, base = KINDS[kind]
    scope = _scope(kind)
    if scope is None:
        return []
    filters = dict(base)
    if names is not None:
        allowed = set(names)
        if isinstance(scope.get("name"), list):
            allowed &= set(scope.pop("name")[1])
        filters["name"] = ["in", list(allowed) or [""]]
    filters.update(scope)
    or_filters = None
    if txt:
        like = f"%{txt}%"
        or_filters = {field: ["like", like] for field in ("name", title, *EXTRA_SEARCH.get(kind, ()))}
    # Tasks and projects keep ERPNext's own permissions; assets and requests are checked by _scope,
    # as on their Techy screens (ERPNext gives maintenance roles no Asset access).
    query = frappe.get_list if doctype in ("Task", "Project") else frappe.get_all
    rows = query(doctype, filters=filters, or_filters=or_filters, fields=["name", f"{title} as title",
        f"{detail} as detail"], order_by="modified desc", limit_page_length=limit)
    return [{"kind": kind, "name": r.name, "title": r.title or r.name, "detail": r.detail or ""} for r in rows]


@frappe.whitelist()
def search_links(kind, txt=None):
    ops.system_user()
    if kind not in KINDS:
        frappe.throw(frappe._("Choose what to link."))
    return _rows(kind, str(txt or "").strip()[:80] or None)


@frappe.whitelist()
def resolve_links(refs):
    """{'kind:name': {title, detail}} for the references the user may open; others are left out."""
    ops.system_user()
    refs = frappe.parse_json(refs) if isinstance(refs, str) else refs
    wanted = {}
    for ref in (refs or [])[:100]:
        kind, _sep, name = str(ref).partition(":")
        if kind in KINDS and name:
            wanted.setdefault(kind, set()).add(name)
    found = {}
    for kind, names in wanted.items():
        for row in _rows(kind, names=names, limit=len(names)):
            found[f"{kind}:{row['name']}"] = {"title": row["title"], "detail": row["detail"]}
    return found
