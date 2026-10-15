"""Slack-style team chat: Techy Channel documents hold membership; messages are native Comments.

Top-level messages are Comments on the channel; thread replies link to their root Comment
through Comment.subject (unused by plain comments). New messages are pushed to each member's socket.io room.

Photos are private Files attached to the channel, so only people who can read the channel can open them.
The message keeps a [[photo:<File name>]] token per photo; readers get the text and the photo URLs separately.
A message can be turned into a work order (work_orders.create_work_order with chat_message), which copies its
photos to the job and posts a link back in the message's thread.
"""
import hashlib
import re
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from projectit import links, ops

SLUG = re.compile(r"[^a-z0-9_-]+")
PHOTO = re.compile(r"\s*\[\[photo:([0-9A-Za-z]{6,40})\]\]")
MAX_PHOTOS = 6
MESSAGE_FIELDS = ["name", "content", "comment_type", "comment_email", "comment_by", "creation", "modified",
    "subject", "reference_name"]


def _split(content):
    """(text, photo File names) of a stored message."""
    return PHOTO.sub("", content or "").strip(), PHOTO.findall(content or "")


def _photo_urls(channel, names):
    """{File name: URL} for photos that really belong to this channel."""
    names = list(dict.fromkeys(names or []))
    if not names:
        return {}
    return dict(frappe.get_all("File", filters={"name": ["in", names], "attached_to_doctype": "Techy Channel",
        "attached_to_name": channel}, fields=["name", "file_url"], as_list=True))


def _members(channel):
    return frappe.get_all("Techy Channel Member", filters={"parent": channel, "parenttype": "Techy Channel"},
        fields=["name", "user", "last_read"], limit_page_length=0)


def _channel(name, member=True):
    ops.system_user()
    doc = frappe.get_doc("Techy Channel", name)
    is_member = any(row.user == frappe.session.user for row in doc.members)
    if doc.is_private and not is_member:
        frappe.throw(_("This channel is private."), frappe.PermissionError)
    if member and not is_member:
        frappe.throw(_("Join #{0} to post messages.").format(doc.channel_name), frappe.PermissionError)
    return doc


def _title(doc, user=None):
    if not doc.is_direct:
        return doc.channel_name
    others = [row.user for row in doc.members if row.user != (user or frappe.session.user)]
    return ", ".join(frappe.utils.get_fullname(u) for u in others) or frappe.utils.get_fullname(user)


def _unread(channel, last_read):
    filters = {"reference_doctype": "Techy Channel", "reference_name": channel, "comment_type": "Comment",
        "comment_email": ["!=", frappe.session.user], "subject": ["is", "not set"]}
    if last_read:
        filters["creation"] = [">", last_read]
    return frappe.db.count("Comment", filters)


def unread_total():
    rows = frappe.get_all("Techy Channel Member", filters={"user": frappe.session.user,
        "parenttype": "Techy Channel"}, fields=["parent", "last_read"], limit_page_length=0)
    return sum(_unread(row.parent, row.last_read) for row in rows)


@frappe.whitelist()
def list_channels():
    ops.system_user()
    user = frappe.session.user
    memberships = {row.parent: row.last_read for row in frappe.get_all("Techy Channel Member",
        filters={"user": user, "parenttype": "Techy Channel"}, fields=["parent", "last_read"], limit_page_length=0)}
    rows = frappe.get_all("Techy Channel", filters={"archived": 0}, or_filters={"is_private": 0,
        "name": ["in", list(memberships) or [""]]}, fields=["name", "channel_name", "description", "is_private",
        "is_direct", "project", "modified"], order_by="channel_name asc", limit_page_length=0)
    result = []
    for row in rows:
        row.is_member = row.name in memberships
        row.unread = _unread(row.name, memberships[row.name]) if row.is_member else 0
        if row.is_direct:
            row.title = _title(frappe.get_doc("Techy Channel", row.name))
        else:
            row.title = row.channel_name
        result.append(row)
    return result


@frappe.whitelist(methods=["POST"])
def create_channel(channel_name, description=None, is_private=0, members=None, project=None):
    ops.system_user()
    slug = SLUG.sub("-", str(channel_name or "").strip().lower()).strip("-")[:60]
    if not slug or slug.startswith("dm-"):
        frappe.throw(_("Use letters, numbers, - or _ for the channel name."))
    if frappe.db.exists("Techy Channel", slug):
        frappe.throw(_("#{0} already exists.").format(slug))
    if project:
        if not ops.manager():
            frappe.throw(_("Only managers can link a channel to a project."), frappe.PermissionError)
        frappe.get_doc("Project", project).check_permission("read")
    users = [frappe.session.user] + [u for u in ops.active_users(members) if u != frappe.session.user]
    doc = frappe.get_doc({"doctype": "Techy Channel", "channel_name": slug, "is_private": cint(is_private),
        "description": ops.text(description, "a description", 250, required=False), "project": project or None,
        "members": [{"user": u} for u in users]})
    # Any staff member can open a channel, as in Slack; Desk administration keeps its own roles.
    doc.insert(ignore_permissions=True)
    post_system_message(doc.name, _("{0} created #{1}").format(frappe.utils.get_fullname(), slug))
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def open_direct(user):
    ops.system_user()
    other = ops.active_users([user])[0]
    pair = sorted({frappe.session.user, other})
    name = "dm-" + hashlib.sha1("|".join(pair).encode()).hexdigest()[:16]
    if not frappe.db.exists("Techy Channel", name):
        frappe.get_doc({"doctype": "Techy Channel", "channel_name": name, "is_private": 1, "is_direct": 1,
            "members": [{"user": u} for u in pair]}).insert(ignore_permissions=True)
    return {"name": name}


@frappe.whitelist(methods=["POST"])
def join_channel(name):
    doc = _channel(name, member=False)
    if doc.archived:
        frappe.throw(_("This channel is archived."))
    if not any(row.user == frappe.session.user for row in doc.members):
        doc.append("members", {"user": frappe.session.user, "last_read": now_datetime()})
        doc.save(ignore_permissions=True)
        post_system_message(doc.name, _("{0} joined").format(frappe.utils.get_fullname()))
    return get_channel(name)


@frappe.whitelist(methods=["POST"])
def leave_channel(name):
    doc = _channel(name)
    if doc.is_direct:
        frappe.throw(_("You cannot leave a direct message."))
    doc.members = [row for row in doc.members if row.user != frappe.session.user]
    doc.save(ignore_permissions=True)
    post_system_message(doc.name, _("{0} left").format(frappe.utils.get_fullname()))
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def add_members(name, users):
    doc = _channel(name)
    if doc.is_direct:
        frappe.throw(_("Start a new channel to add more people."))
    current = {row.user for row in doc.members}
    added = [u for u in ops.active_users(users) if u not in current]
    for user in added:
        doc.append("members", {"user": user})
    if added:
        doc.save(ignore_permissions=True)
        post_system_message(doc.name, _("{0} added {1}").format(frappe.utils.get_fullname(),
            ", ".join(frappe.utils.get_fullname(u) for u in added)))
        ops.notify(added, _("You were added to #{0}").format(doc.channel_name), "Techy Channel", doc.name)
    return get_channel(name)


@frappe.whitelist()
def get_channel(name):
    doc = _channel(name, member=False)
    return {"name": doc.name, "channel_name": doc.channel_name, "title": _title(doc), "description": doc.description,
        "is_private": doc.is_private, "is_direct": doc.is_direct, "project": doc.project, "archived": doc.archived,
        "is_member": any(row.user == frappe.session.user for row in doc.members),
        "members": ops.people([row.user for row in doc.members])}


def _messages(channel, thread=None, before=None, limit=50):
    filters = {"reference_doctype": "Techy Channel", "reference_name": channel,
        "comment_type": ["in", ["Comment", "Info"]]}
    if thread:
        filters["subject"] = thread
    else:
        filters["subject"] = ["is", "not set"]
    if before:
        filters["creation"] = ["<", get_datetime(before)]
    rows = frappe.get_all("Comment", filters=filters, fields=MESSAGE_FIELDS, order_by="creation desc",
        limit_page_length=min(max(cint(limit), 1), 100) + 1)
    has_more, rows = len(rows) > limit, list(reversed(rows[:limit]))
    urls = _photo_urls(channel, [n for row in rows for n in _split(row.content)[1]])
    replies = {}
    if rows and not thread:
        for root, total, last in frappe.db.sql("""SELECT subject, COUNT(*), MAX(creation) FROM `tabComment`
                WHERE reference_doctype = 'Techy Channel' AND reference_name = %(channel)s
                  AND subject IN %(roots)s GROUP BY subject""",
                {"channel": channel, "roots": tuple(r.name for r in rows)}):
            replies[root] = {"count": total, "last": last}
    return [_message(row, replies.get(row.name), urls) for row in rows], has_more


def _message(row, replies=None, urls=None):
    text, names = _split(row.content)
    if urls is None:
        urls = _photo_urls(row.reference_name, names)
    return {"name": row.name, "content": ops.plain(text), "system": row.comment_type == "Info",
        "photos": [{"name": n, "url": urls[n]} for n in names if n in urls],
        "user": row.comment_email, "full_name": row.comment_by or frappe.utils.get_fullname(row.comment_email),
        "image": frappe.get_cached_value("User", row.comment_email, "user_image") if row.comment_email else None,
        "creation": row.creation, "edited": row.modified != row.creation, "thread": row.subject or None,
        "reply_count": (replies or {}).get("count", 0), "last_reply": (replies or {}).get("last")}


@frappe.whitelist()
def get_messages(channel, thread=None, before=None, limit=50):
    _channel(channel, member=False)
    messages, has_more = _messages(channel, thread, before, cint(limit) or 50)
    root = None
    if thread:
        root = frappe.get_all("Comment", filters={"name": thread, "reference_doctype": "Techy Channel",
            "reference_name": channel}, fields=MESSAGE_FIELDS)
        if not root:
            frappe.throw(_("Thread not found."))
        root = _message(root[0])
    return {"messages": messages, "has_more": has_more, "root": root}


def _photos(value):
    photos = frappe.parse_json(value) if isinstance(value, str) else (value or [])
    if not isinstance(photos, list) or len(photos) > MAX_PHOTOS:
        frappe.throw(_("Send at most {0} photos in one message.").format(MAX_PHOTOS))
    return photos


@frappe.whitelist(methods=["POST"])
def post_message(channel, content=None, thread=None, photos=None):
    doc = _channel(channel)
    if doc.archived:
        frappe.throw(_("This channel is archived."))
    photos = _photos(photos)
    content = PHOTO.sub("", ops.text(content, "a message", 4000, required=not photos)).strip()
    if not content and not photos:
        frappe.throw(_("Write a message or add a photo."))
    if thread and not frappe.db.exists("Comment", {"name": thread, "reference_doctype": "Techy Channel",
            "reference_name": doc.name, "subject": ["is", "not set"]}):
        frappe.throw(_("Thread not found."))
    # Membership was checked above; the files follow the channel's own permission.
    files = [ops.save_photo("Techy Channel", doc.name, photo, "chat", ignore_permissions=True) for photo in photos]
    comment = _comment(doc, "Comment", content, thread, photos=[f.name for f in files])
    members = [row.user for row in doc.members]
    _mark_read(doc.name)
    message = _message(frappe._dict(name=comment.name, content=comment.content, comment_type="Comment",
        comment_email=comment.comment_email, comment_by=comment.comment_by, creation=comment.creation,
        modified=comment.creation, subject=thread), urls={f.name: f.file_url for f in files})
    ops.push(members, "techy_chat", {"channel": doc.name, "message": message})
    mentioned = ops.mentions(content, set(members))
    if doc.is_direct:
        mentioned = [u for u in members if u != frappe.session.user]
    said = links.readable(content) or (_("sent a photo") if len(files) == 1 else _("sent {0} photos").format(len(files)))
    ops.notify(mentioned, _("{0} in {1}: {2}").format(frappe.utils.get_fullname(),
        _("a direct message") if doc.is_direct else f"#{doc.channel_name}", said[:120]),
        "Techy Channel", doc.name, "Mention")
    return message


def _comment(doc, comment_type, content, thread=None, by=None, photos=None):
    # Membership was checked by the caller; Comment's own permission follows the channel.
    stored = "\n".join([escape(content)] + [f"[[photo:{name}]]" for name in photos or []]).strip()
    return frappe.get_doc({"doctype": "Comment", "comment_type": comment_type, "reference_doctype": doc.doctype,
        "reference_name": doc.name, "content": stored, "comment_email": frappe.session.user,
        "comment_by": by or frappe.utils.get_fullname(), "subject": thread or None}).insert(ignore_permissions=True)


def post_system_message(channel, content, thread=None):
    doc = frappe.get_doc("Techy Channel", channel)
    comment = _comment(doc, "Info", content, thread, by=_("Techy Ops"))
    ops.push([row.user for row in doc.members], "techy_chat", {"channel": doc.name, "message": _message(
        frappe._dict(name=comment.name, content=comment.content, comment_type="Info", comment_email=None,
        comment_by=comment.comment_by, creation=comment.creation, modified=comment.creation, subject=thread),
        urls={})})


@frappe.whitelist(methods=["POST"])
def edit_message(name, content):
    comment = _own_message(name)
    names = _split(comment.content)[1]
    text = PHOTO.sub("", ops.text(content, "a message", 4000, required=not names)).strip()
    comment.content = "\n".join([escape(text)] + [f"[[photo:{n}]]" for n in names]).strip()  # photos stay
    comment.save(ignore_permissions=True)
    return {"name": comment.name}


@frappe.whitelist(methods=["POST"])
def delete_message(name):
    comment = _own_message(name, allow_manager=True)
    removed = [comment]
    for reply in frappe.get_all("Comment", filters={"subject": comment.name,
            "reference_doctype": "Techy Channel"}, fields=["name", "content"]):
        removed.append(reply)
        frappe.delete_doc("Comment", reply.name, ignore_permissions=True)
    frappe.delete_doc("Comment", comment.name, ignore_permissions=True)
    # Copies made for work orders are separate File records and stay with the job.
    for photo in _photo_urls(comment.reference_name, [n for c in removed for n in _split(c.content)[1]]):
        frappe.delete_doc("File", photo, ignore_permissions=True)
    return {"name": name}


def message_source(name):
    """A chat message someone wants to turn into a work order, after checking they can read its channel."""
    row = frappe.db.get_value("Comment", name, MESSAGE_FIELDS + ["reference_doctype"], as_dict=True)
    if not row or row.reference_doctype != "Techy Channel" or row.comment_type != "Comment":
        frappe.throw(_("Message not found."))
    _channel(row.reference_name, member=False)
    return row


def link_work_order(message, work_order):
    """Copy the message's photos to the new work order and say so in the message's thread."""
    for url in _photo_urls(message.reference_name, _split(message.content)[1]).values():
        frappe.get_doc({"doctype": "File", "file_url": url, "is_private": 1, "attached_to_doctype": "Task",
            "attached_to_name": work_order.name}).insert(ignore_permissions=True)
    channel = frappe.get_doc("Techy Channel", message.reference_name)
    where = _("a direct message") if channel.is_direct else f"#{channel.channel_name}"
    work_order.add_comment("Info", escape(_("Created from a message by {0} in {1}").format(
        message.comment_by or message.comment_email, where)))
    post_system_message(channel.name, _("{0} created work order [[work-order:{1}]] from this message").format(
        frappe.utils.get_fullname(), work_order.name), thread=message.subject or message.name)


def _own_message(name, allow_manager=False):
    ops.system_user()
    comment = frappe.get_doc("Comment", name)
    if comment.reference_doctype != "Techy Channel" or comment.comment_type != "Comment":
        frappe.throw(_("Message not found."))
    _channel(comment.reference_name)
    if comment.comment_email != frappe.session.user and not (allow_manager and ops.manager()):
        frappe.throw(_("You can only change your own messages."), frappe.PermissionError)
    return comment


def _mark_read(channel):
    row = frappe.db.get_value("Techy Channel Member", {"parent": channel, "parenttype": "Techy Channel",
        "user": frappe.session.user}, "name")
    if row:
        frappe.db.set_value("Techy Channel Member", row, "last_read", now_datetime(), update_modified=False)


@frappe.whitelist(methods=["POST"])
def mark_read(channel):
    _channel(channel)
    _mark_read(channel)
    return {"unread": unread_total()}


# Permission hooks --------------------------------------------------------------------------------------------

def has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not doc.is_private or "System Manager" in frappe.get_roles(user):
        return True
    return any(row.user == user for row in doc.members)


def permission_query_conditions(user=None):
    user = user or frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return ""
    user = frappe.db.escape(user)
    return f"""(`tabTechy Channel`.is_private = 0 OR `tabTechy Channel`.name IN (SELECT parent
        FROM `tabTechy Channel Member` WHERE parenttype = 'Techy Channel' AND user = {user}))"""
