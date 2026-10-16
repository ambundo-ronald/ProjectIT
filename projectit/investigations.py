"""Root cause investigations (RCA): why a problem happened, the evidence, and what was done about it.

An investigation names the problem (with what was measured against the target) and is usually started from
a job or a machine, which fills in the customer, site and machine. It holds:

- causes under the six fishbone headings (the 6Ms: Method, Machine, Material, Manpower, Measurement,
  Management), each with its evidence, actual vs required, how sure we are (Confirmed, Reported, Potential,
  Open), and the corrective or preventive action with its owner and closure evidence;
- a 5 Whys chain, the root cause and the contributing factors;
- what must be in place before it can be closed.

The fishbone diagram is drawn from the causes, so it never goes out of step with the evidence table. The PDF
(landscape A4, on the letter head) has the diagram, the evidence table and the 5 Whys.

Anyone with Techy Ops may start and edit an open investigation; managers close, reopen and delete them. An
investigation closes only when it has a root cause and every action is done with its closure evidence.
"""
import textwrap
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, format_datetime, getdate, nowdate, now_datetime

from projectit import ops

DOCTYPE = "Techy Investigation"
SIX_M = ("Method", "Machine", "Material", "Manpower", "Measurement", "Management")
STATUSES = ("Confirmed", "Reported", "Potential", "Open")
HEADER = ("title", "actual", "target", "customer", "site", "equipment", "asset", "work_order", "investigated_on",
    "follow_up_on", "prepared_by", "problem", "focus", "root_cause", "contributing_factors", "closure_requirements")
DATES = ("investigated_on", "follow_up_on")
LINKS = {"customer": "Customer", "equipment": "Techy Equipment", "asset": "Asset", "work_order": "Task", "prepared_by": "User"}
LIMITS = {"title": 140, "actual": 60, "target": 60, "site": 140, "problem": 4000, "focus": 1000, "root_cause": 2000,
    "contributing_factors": 2000, "closure_requirements": 2000}
CAUSE_LIMITS = {"cause": 300, "evidence": 1000, "actual_vs_required": 300, "action": 1000, "owner_name": 140,
    "closure_evidence": 1000}
WHY_LIMITS = {"question": 300, "answer": 1000, "evidence": 1500}
LIST_FIELDS = ["name", "title", "status", "customer", "customer_name", "site", "equipment", "asset", "work_order",
    "investigated_on", "closed_on", "modified", "creation"]


# Access ---------------------------------------------------------------------------------------------------------

def can_edit():
    from projectit import api
    return ops.manager() or api.has_app("Ops")


def _require_access():
    ops.system_user()
    if not can_edit():
        frappe.throw(_("Root cause investigations are part of Techy Ops."), frappe.PermissionError)


def _get(name, write=False):
    _require_access()
    if not name or not frappe.db.exists(DOCTYPE, name):
        frappe.throw(_("Investigation {0} was not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc(DOCTYPE, name)
    if write and doc.status == "Closed":
        frappe.throw(_("This investigation is closed. A manager can reopen it."))
    return doc


# Reading --------------------------------------------------------------------------------------------------------

def _lines(value):
    return [line.strip(" \t-•*") for line in str(value or "").splitlines() if line.strip(" \t-•*")]


def gaps(doc):
    """What still stops the investigation from closing."""
    causes = doc.get("causes") or []
    result = []
    if not causes:
        result.append(_("Add the causes you looked at."))
    if not (doc.get("root_cause") or "").strip():
        result.append(_("Write the root cause."))
    open_actions = [c for c in causes if (c.get("action") or "").strip() and not cint(c.get("done"))]
    if open_actions:
        result.append(_("{0} action(s) still to be done.").format(len(open_actions)))
    unproven = [c for c in causes if cint(c.get("done")) and not (c.get("closure_evidence") or "").strip()]
    if unproven:
        result.append(_("{0} done action(s) need their closure evidence.").format(len(unproven)))
    return result


def _machine(doc):
    if doc.get("equipment"):
        from projectit.equipment import summary
        row = summary(doc.equipment)
        return row and {"kind": "equipment", "name": row["name"], "label": row["equipment_name"],
            "detail": " · ".join(x for x in (row.get("serial_no") and _("S/N {0}").format(row["serial_no"]), row.get("site")) if x)}
    if doc.get("asset"):
        label = frappe.db.get_value("Asset", doc.asset, "asset_name")
        return {"kind": "asset", "name": doc.asset, "label": label or doc.asset, "detail": _("Our equipment")}
    return None


def history(doc, limit=12):
    """Recent jobs on the same machine: evidence the investigation can draw on."""
    field, value = ("custom_equipment", doc.equipment) if doc.get("equipment") else \
        ("custom_asset", doc.asset) if doc.get("asset") else (None, None)
    if not field:
        return []
    rows = frappe.get_all("Task", filters={"custom_work_order": 1, field: value, "status": ["!=", "Cancelled"]},
        fields=["name", "subject", "status", "creation", "custom_completed_at", "custom_work_category",
            "custom_problem_code", "custom_cause_code", "custom_machine_down", "custom_down_from", "custom_down_to"],
        order_by="creation desc", limit_page_length=limit)
    codes = {c for r in rows for c in (r.custom_problem_code, r.custom_cause_code) if c}
    titles = dict(frappe.get_all("Techy Failure Code", filters={"name": ["in", list(codes)]}, fields=["name", "title"],
        as_list=True)) if codes else {}
    for r in rows:
        r.problem = titles.get(r.custom_problem_code, r.custom_problem_code)
        r.cause = titles.get(r.custom_cause_code, r.custom_cause_code)
    return rows


def detail(doc):
    data = {f: doc.get(f) for f in HEADER + ("name", "status", "customer_name", "closed_on", "closed_by", "modified", "owner", "creation")}
    job = frappe.db.get_value("Task", doc.work_order, ["name", "subject"], as_dict=True) if doc.work_order else None
    manager = ops.manager()
    return {
        "investigation": data,
        "causes": [{k: c.get(k) for k in ("name", "category", "cause", "evidence", "actual_vs_required", "status", "action",
            "owner_name", "due_date", "closure_evidence", "done", "done_on", "done_by")} for c in doc.causes],
        "whys": [{k: w.get(k) for k in ("name", "question", "answer", "evidence")} for w in doc.whys],
        "fishbone": fishbone(doc),
        "machine": _machine(doc), "job": job, "history": history(doc),
        "people": {u: frappe.utils.get_fullname(u) for u in {doc.prepared_by, doc.closed_by, doc.owner} if u},
        "gaps": gaps(doc) if doc.status == "Open" else [],
        "can_edit": doc.status == "Open" and can_edit(), "can_close": doc.status == "Open" and manager,
        "can_reopen": doc.status == "Closed" and manager, "can_delete": manager,
        "options": {"categories": SIX_M, "statuses": STATUSES},
    }


@frappe.whitelist()
def list_investigations(status=None, search=None, equipment=None, asset=None, work_order=None):
    _require_access()
    filters = {}
    if status in ("Open", "Closed"):
        filters["status"] = status
    for field, value in (("equipment", equipment), ("asset", asset), ("work_order", work_order)):
        if value:
            filters[field] = value
    or_filters = None
    if search:
        like = f"%{str(search).strip()[:80]}%"
        or_filters = {"name": ["like", like], "title": ["like", like], "customer_name": ["like", like],
            "site": ["like", like], "equipment": ["like", like]}
    rows = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, fields=LIST_FIELDS,
        order_by="modified desc", limit_page_length=500)
    names = [r.name for r in rows]
    causes = frappe.get_all("Techy Investigation Cause", filters={"parent": ["in", names], "parenttype": DOCTYPE},
        fields=["parent", "action", "done"], limit_page_length=0) if names else []
    from projectit.equipment import labels
    machines = labels(r.equipment for r in rows)
    for r in rows:
        mine = [c for c in causes if c.parent == r.name]
        actions = [c for c in mine if (c.action or "").strip()]
        r.causes = len(mine)
        r.actions = len(actions)
        r.actions_done = sum(1 for c in actions if cint(c.done))
        r.machine = (machines.get(r.equipment) or {}).get("equipment_name") if r.equipment else \
            frappe.db.get_value("Asset", r.asset, "asset_name") if r.asset else None
    return {"investigations": rows, "manager": ops.manager()}


@frappe.whitelist()
def get_investigation(name):
    return detail(_get(name))


# Changes --------------------------------------------------------------------------------------------------------

def _date(value, label):
    if value in (None, ""):
        return None
    try:
        return getdate(value)
    except Exception:
        frappe.throw(_("{0} is not a valid date.").format(label))


def _link(field, value):
    if not value:
        return None
    if not frappe.db.exists(LINKS[field], value):
        frappe.throw(_("{0} {1} was not found.").format(_(LINKS[field]), value))
    return value


@frappe.whitelist(methods=["POST"])
def start(work_order=None, equipment=None, asset=None, title=None):
    """A new investigation, filled in from the job or machine it starts from."""
    _require_access()
    values = {"doctype": DOCTYPE, "status": "Open", "investigated_on": nowdate(), "prepared_by": frappe.session.user}
    if work_order:
        from projectit import work_orders
        job = work_orders._work_order(work_order)  # checks the caller can open the job
        values.update(work_order=job.name, title=job.subject[:140], equipment=job.get("custom_equipment"),
            asset=job.get("custom_asset"), customer=job.get("custom_customer"))
        codes = [frappe.db.get_value("Techy Failure Code", c, "title") or c
            for c in (job.get("custom_problem_code"), job.get("custom_cause_code")) if c]
        problem = ops.plain(job.description or "").strip()
        if codes:
            problem = "\n".join(x for x in (problem, _("Coded on job {0}: {1}").format(job.name, " / ".join(codes))) if x)
        values["problem"] = problem[:4000]
    if equipment and not values.get("equipment"):
        values["equipment"] = _link("equipment", equipment)
    if asset and not values.get("asset") and not values.get("equipment"):
        values["asset"] = _link("asset", asset)
    if values.get("equipment"):
        row = frappe.db.get_value("Techy Equipment", values["equipment"], ["customer", "site", "equipment_name"], as_dict=True)
        if row:
            values["customer"] = values.get("customer") or row.customer
            values["site"] = row.site
    if title:
        values["title"] = ops.text(title, "the problem", 140)
    if not values.get("title"):
        values["title"] = _("New investigation")
    doc = frappe.get_doc(values)
    doc.insert(ignore_permissions=True)
    return detail(doc)


def _rows(raw, limits, required, extra=None):
    rows = frappe.parse_json(raw) if isinstance(raw, str) else (raw or [])
    if not isinstance(rows, list) or len(rows) > 60:
        frappe.throw(_("Too many rows."))
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean = {k: ops.text(row.get(k), k.replace("_", " "), n, required=False) or None for k, n in limits.items()}
        if not clean[required]:
            continue  # an empty row the person never filled in
        if extra:
            extra(row, clean)
        result.append(clean)
    return result


def _cause(row, clean):
    if row.get("category") not in SIX_M:
        frappe.throw(_("Choose a 6M heading for every cause."))
    clean["category"] = row["category"]
    clean["status"] = row.get("status") if row.get("status") in STATUSES else "Potential"
    clean["due_date"] = _date(row.get("due_date"), _("Due date"))
    clean["done"] = cint(row.get("done"))
    clean["done_on"] = (_date(row.get("done_on"), _("Done on")) or getdate(nowdate())) if clean["done"] else None
    clean["name"] = row.get("name")


@frappe.whitelist(methods=["POST"])
def save(name, data, modified=None):
    """Save the whole investigation: its details, causes and whys."""
    doc = _get(name, write=True)
    if modified and str(doc.modified) != str(modified):
        frappe.throw(_("Someone else changed this investigation. Reload it to see their changes, then try again."))
    data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
    for field in HEADER:
        if field not in data:
            continue
        value = data.get(field)
        if field in DATES:
            value = _date(value, _(field.replace("_", " ").capitalize()))
        elif field in LINKS:
            value = _link(field, value)
        else:
            value = ops.text(value, "the problem" if field == "title" else field.replace("_", " "), LIMITS[field],
                required=field == "title") or None
        doc.set(field, value)
    if "causes" in data:
        before = {c.name: c for c in doc.causes}
        causes = _rows(data["causes"], CAUSE_LIMITS, "cause", _cause)
        doc.set("causes", [])
        for c in causes:
            old = before.get(c.pop("name", None))
            c["done_by"] = (old.done_by if old and cint(old.done) and old.done_by else frappe.session.user) if c["done"] else None
            doc.append("causes", c)
    if "whys" in data:
        doc.set("whys", [])
        for w in _rows(data["whys"], WHY_LIMITS, "question"):
            doc.append("whys", w)
    doc.save(ignore_permissions=True)
    return detail(doc)


@frappe.whitelist(methods=["POST"])
def close(name):
    doc = _get(name, write=True)
    ops.require_manager()
    missing = gaps(doc)
    if missing:
        frappe.throw(_("Not ready to close: {0}").format(" ".join(missing)))
    doc.update({"status": "Closed", "closed_on": nowdate(), "closed_by": frappe.session.user})
    doc.save(ignore_permissions=True)
    doc.add_comment("Info", escape(_("{0} closed the investigation.").format(frappe.utils.get_fullname())))
    return detail(doc)


@frappe.whitelist(methods=["POST"])
def reopen(name):
    doc = _get(name)
    ops.require_manager()
    doc.update({"status": "Open", "closed_on": None, "closed_by": None})
    doc.save(ignore_permissions=True)
    doc.add_comment("Info", escape(_("{0} reopened the investigation.").format(frappe.utils.get_fullname())))
    return detail(doc)


@frappe.whitelist(methods=["POST"])
def delete(name):
    doc = _get(name)
    ops.require_manager()
    frappe.delete_doc(DOCTYPE, doc.name, ignore_permissions=True)
    return {"deleted": doc.name}


# Fishbone diagram -----------------------------------------------------------------------------------------------

COLOURS = {"Method": "#2563eb", "Machine": "#059669", "Material": "#d97706", "Manpower": "#ea580c",
    "Measurement": "#7c3aed", "Management": "#0d9488"}
WIDTH = 1180
COLUMN = 310
WRAP = 33
LINE = 13
MAX_CAUSES = 7
MAX_LINES = 3


def _wrap(text, width=WRAP, lines=MAX_LINES):
    rows = textwrap.wrap(" ".join(str(text or "").split()), width) or ["—"]
    if len(rows) > lines:
        rows = rows[:lines]
        rows[-1] = rows[-1][: width - 1].rstrip() + "…"
    return rows


def _blocks(causes):
    """Wrapped cause texts for one heading, with a closing note when some do not fit."""
    blocks = [_wrap(c.get("cause")) for c in causes[:MAX_CAUSES]]
    if len(causes) > MAX_CAUSES:
        blocks.append([_("+ {0} more in the evidence table").format(len(causes) - MAX_CAUSES)])
    return blocks


def _height(blocks):
    return sum(len(b) * LINE + 10 for b in blocks)


def _text(x, y, lines, size=11, weight="normal", fill="#1f2937", anchor="start", italic=False):
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else size + 2}">{escape(line)}</tspan>' for i, line in enumerate(lines))
    style = ' font-style="italic"' if italic else ""
    return (f'<text x="{x}" y="{y}" font-family="Helvetica, Arial, sans-serif" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}"{style}>{spans}</text>')


def _arrow(x1, y, x2, colour):
    return (f'<line x1="{x1}" y1="{y}" x2="{x2 - 6}" y2="{y}" stroke="{colour}" stroke-width="1.6"/>'
        f'<polygon points="{x2 - 7},{y - 4} {x2},{y} {x2 - 7},{y + 4}" fill="{colour}"/>')


def _box(cx, y, label, colour):
    return (f'<rect x="{cx - 78}" y="{y}" width="156" height="30" rx="6" fill="{colour}" fill-opacity="0.16" '
        f'stroke="{colour}" stroke-width="1.6"/>' + _text(cx, y + 20, [label.upper()], 13, "bold", "#111827", "middle"))


def fishbone(doc):
    """The fishbone diagram as SVG: causes on six bones leading to the problem."""
    causes = doc.get("causes") or []
    groups = {m: [c for c in causes if c.get("category") == m] for m in SIX_M}
    top, bottom = SIX_M[:3], SIX_M[3:]
    blocks = {m: _blocks(groups[m]) for m in SIX_M}
    top_h = max(130, *(_height(blocks[m]) for m in top))
    bottom_h = max(130, *(_height(blocks[m]) for m in bottom))
    box_top = 8
    spine = box_top + 30 + 18 + top_h + 8
    bottom_box = spine + 22 + bottom_h + 4
    height = bottom_box + 30 + 10

    title = _wrap(str(doc.get("title") or "").upper(), 20, 4)
    actual, target = (doc.get("actual") or "").strip(), (doc.get("target") or "").strip()
    effect_h = 18 + len(title) * 18 + (24 if actual else 0) + (18 if target else 0) + 6
    effect_y = max(4, spine - effect_h / 2)
    height = max(height, effect_y + effect_h + 6)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{int(height)}" '
        f'viewBox="0 0 {WIDTH} {int(height)}" role="img"><rect width="100%" height="100%" fill="#ffffff"/>']
    out.append(f'<line x1="14" y1="{spine}" x2="950" y2="{spine}" stroke="#1f2937" stroke-width="5"/>'
        f'<polygon points="944,{spine - 11} 962,{spine} 944,{spine + 11}" fill="#1f2937"/>')
    for i, m in enumerate(SIX_M):
        x0 = 20 + (i % 3) * COLUMN
        colour = COLOURS[m]
        bone_far, bone_near = x0 + 215, x0 + 300
        if m in top:
            y_box, y1, y2 = box_top, box_top + 30, spine
            out.append(_box(bone_far, y_box, m, colour))
            y = box_top + 30 + 18
        else:
            y_box, y1, y2 = bottom_box, bottom_box, spine
            out.append(_box(bone_far, y_box, m, colour))
            y = spine + 22
        out.append(f'<line x1="{bone_far}" y1="{y1}" x2="{bone_near}" y2="{y2}" stroke="{colour}" stroke-width="3"/>')

        def bone_x(at):
            share = (at - y1) / (y2 - y1) if y2 != y1 else 0
            return bone_far + share * (bone_near - bone_far)

        for n, lines in enumerate(blocks[m]):
            more = n >= MAX_CAUSES
            out.append(_text(x0, y + 10, lines, 11, fill="#6b7280" if more else "#1f2937", italic=more))
            if not more:
                mid = y + 10 + (len(lines) - 1) * LINE / 2 - 3
                out.append(_arrow(x0 + 202, mid, bone_x(mid) - 2, colour))
            y += len(lines) * LINE + 10
        if not groups[m]:
            out.append(_text(x0, y + 10, [_("No causes recorded")], 11, fill="#9ca3af", italic=True))

    out.append(f'<rect x="966" y="{effect_y}" width="204" height="{effect_h}" rx="8" fill="#fef2f2" stroke="#dc2626" stroke-width="2"/>')
    cy = effect_y + 24
    out.append(_text(1068, cy, title, 15, "bold", "#7f1d1d", "middle"))
    cy += len(title) * 17 + 6
    if actual:
        out.append(_text(1068, cy + 4, [actual], 17, "bold", "#7f1d1d", "middle"))
        cy += 24
    if target:
        out.append(_text(1068, cy, [_("(Target {0})").format(target)], 11, "bold", "#7f1d1d", "middle"))
    out.append("</svg>")
    return "".join(out)


# PDF ------------------------------------------------------------------------------------------------------------

WHY_COLOURS = ("#2563eb", "#059669", "#d97706", "#ea580c", "#dc2626", "#7c3aed", "#0d9488")
STATUS_NOTES = {"Confirmed": "Confirmed", "Reported": "Reported — verify", "Potential": "Potential", "Open": "Open"}


def context(name):
    import base64
    from projectit import service_report
    doc = _get(name)
    machine = _machine(doc)
    svg = fishbone(doc)
    causes = []
    for c in doc.causes:
        status = _(STATUS_NOTES.get(c.status, c.status or ""))
        if cint(c.done):
            status = _("{0}; action done {1}").format(status, getdate(c.done_on).strftime("%d %b %Y") if c.done_on else "")
        causes.append({"category": c.category, "colour": COLOURS.get(c.category, "#374151"), "cause": c.cause or "",
            "evidence": c.evidence or "", "actual": c.actual_vs_required or "", "status": status,
            "confirmed": c.status == "Confirmed", "action": c.action or "", "owner": c.owner_name or "",
            "due": getdate(c.due_date).strftime("%d %b %Y") if c.due_date and not cint(c.done) else "",
            "closure": c.closure_evidence or ""})
    order = {m: i for i, m in enumerate(SIX_M)}
    causes.sort(key=lambda c: order.get(c["category"], 9))
    whys = [{"n": i + 1, "colour": WHY_COLOURS[i % len(WHY_COLOURS)], "question": w.question or "",
        "answer": w.answer or "", "evidence": _lines(w.evidence)} for i, w in enumerate(doc.whys)]
    day = lambda v: getdate(v).strftime("%d %B %Y") if v else ""
    return {
        "company": service_report._company(doc.name, _("Root cause analysis")), "doc": doc, "machine": machine,
        "fishbone": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(),
        "causes": causes, "whys": whys, "contributing": _lines(doc.contributing_factors),
        "subline": " | ".join(x for x in (doc.site, day(doc.investigated_on) and _("Site investigation: {0}").format(
            day(doc.investigated_on)), day(doc.follow_up_on) and _("Follow-up: {0}").format(day(doc.follow_up_on))) if x),
        "investigated_on": day(doc.investigated_on), "follow_up_on": day(doc.follow_up_on), "closed_on": day(doc.closed_on),
        "prepared_by": frappe.utils.get_fullname(doc.prepared_by) if doc.prepared_by else "",
        "closed_by": frappe.utils.get_fullname(doc.closed_by) if doc.closed_by else "",
        "job": frappe.db.get_value("Task", doc.work_order, "subject") if doc.work_order else None,
        "printed": format_datetime(now_datetime(), "dd MMM yyyy HH:mm"),
    }


def build(name):
    from frappe.utils.pdf import get_pdf
    from projectit import service_report
    html = service_report._inline_images(frappe.render_template("projectit/templates/investigation_report.html", context(name)))
    pdf = get_pdf(html, {"page-size": "A4", "orientation": "Landscape", "margin-top": "10mm", "margin-bottom": "12mm",
        "margin-left": "10mm", "margin-right": "10mm", "encoding": "UTF-8", "load-error-handling": "ignore",
        "load-media-error-handling": "ignore"})
    return pdf, f"Root cause analysis {name}.pdf"


@frappe.whitelist()
def download(name):
    """The PDF, shown in the browser."""
    pdf, filename = build(name)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"
