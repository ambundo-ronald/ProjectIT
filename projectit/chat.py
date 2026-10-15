"""Slack-style team chat: Techy Channel documents hold membership; messages are native Comments.

Top-level messages are Comments on the channel; thread replies link to their root Comment
through Comment.subject (unused by plain comments). New messages are pushed to each member's socket.io room.

Photos are private Files attached to the channel, so only people who can read the channel can open them.
The message keeps a [[photo:<File name>]] token per photo; readers get the text and the photo URLs separately.
A message can be turned into a work order (work_orders.create_work_order with chat_message), which copies its
photos to the job and posts a link back in the message's thread.

Members react with a fixed set of emoji (Techy Chat Reaction) and pin messages to the channel (Techy Chat Pin).
Reactions, pins and typing are pushed to the other members as they happen. Search covers every channel the
reader can open; get_messages(around=...) loads the conversation around a search result.
"""
import hashlib
from collections import defaultdict
import re
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from projectit import links, ops

SLUG = re.compile(r"[^a-z0-9_-]+")
PHOTO = re.compile(r"\s*\[\[photo:([0-9A-Za-z]{6,40})\]\]")
MAX_PHOTOS = 6
REACTIONS = ("👍", "✅", "👀", "🙏", "🎉", "❤️", "😂", "⚠️")
MAX_PINS = 50
NO_MARKS = ({}, set())
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


def _messages(channel, thread=None, before=None, limit=50, around=None):
    """(messages, has_more older, has_newer). `around` is a creation time to centre on (a search result)."""
    filters = {"reference_doctype": "Techy Channel", "reference_name": channel,
        "comment_type": ["in", ["Comment", "Info"]], "subject": thread if thread else ["is", "not set"]}
    limit = min(max(cint(limit), 1), 100)

    def fetch(extra, order):
        return frappe.get_all("Comment", filters={**filters, **extra}, fields=MESSAGE_FIELDS, order_by=order,
            limit_page_length=limit + 1)
    has_newer = False
    if around:
        older = fetch({"creation": ["<=", get_datetime(around)]}, "creation desc")
        newer = fetch({"creation": [">", get_datetime(around)]}, "creation asc")
        has_more, has_newer = len(older) > limit, len(newer) > limit
        rows = list(reversed(older[:limit])) + newer[:limit]
    else:
        rows = fetch({"creation": ["<", get_datetime(before)]} if before else {}, "creation desc")
        has_more, rows = len(rows) > limit, list(reversed(rows[:limit]))
    urls = _photo_urls(channel, [n for row in rows for n in _split(row.content)[1]])
    marks = _marks([row.name for row in rows])
    replies = {}
    if rows and not thread:
        for root, total, last in frappe.db.sql("""SELECT subject, COUNT(*), MAX(creation) FROM `tabComment`
                WHERE reference_doctype = 'Techy Channel' AND reference_name = %(channel)s
                  AND subject IN %(roots)s GROUP BY subject""",
                {"channel": channel, "roots": tuple(r.name for r in rows)}):
            replies[root] = {"count": total, "last": last}
    return [_message(row, replies.get(row.name), urls, marks) for row in rows], has_more, has_newer


def _marks(names):
    """({message: [{emoji, users}]}, {pinned message names}) for these messages."""
    names = list(names or [])
    if not names:
        return NO_MARKS
    grouped = defaultdict(dict)
    for row in frappe.get_all("Techy Chat Reaction", filters={"message": ["in", names]},
            fields=["message", "emoji", "user"], order_by="creation asc", limit_page_length=0):
        grouped[row.message].setdefault(row.emoji, []).append(row.user)
    reactions = {m: [{"emoji": e, "users": u} for e, u in by.items()] for m, by in grouped.items()}
    return reactions, set(frappe.get_all("Techy Chat Pin", filters={"message": ["in", names]}, pluck="message"))


def _message(row, replies=None, urls=None, marks=None):
    text, names = _split(row.content)
    if urls is None:
        urls = _photo_urls(row.reference_name, names)
    reactions, pinned = marks if marks is not None else _marks([row.name])
    return {"name": row.name, "content": ops.plain(text), "system": row.comment_type == "Info",
        "photos": [{"name": n, "url": urls[n]} for n in names if n in urls],
        "reactions": reactions.get(row.name, []), "pinned": row.name in pinned,
        "user": row.comment_email, "full_name": row.comment_by or frappe.utils.get_fullname(row.comment_email),
        "image": frappe.get_cached_value("User", row.comment_email, "user_image") if row.comment_email else None,
        "creation": row.creation, "edited": row.modified != row.creation, "thread": row.subject or None,
        "reply_count": (replies or {}).get("count", 0), "last_reply": (replies or {}).get("last")}


@frappe.whitelist()
def get_messages(channel, thread=None, before=None, limit=50, around=None):
    """`around`: a message name to open the conversation at (its thread root when it is a reply)."""
    _channel(channel, member=False)
    focus, pivot = None, None
    if around and not thread:
        target = frappe.db.get_value("Comment", {"name": around, "reference_doctype": "Techy Channel",
            "reference_name": channel}, ["name", "subject", "creation"], as_dict=True)
        if not target:
            frappe.throw(_("Message not found."))
        focus = {"message": target.name, "thread": target.subject}
        pivot = frappe.db.get_value("Comment", target.subject, "creation") if target.subject else target.creation
    messages, has_more, has_newer = _messages(channel, thread, before, cint(limit) or 50, pivot)
    root = None
    if thread:
        root = frappe.get_all("Comment", filters={"name": thread, "reference_doctype": "Techy Channel",
            "reference_name": channel}, fields=MESSAGE_FIELDS)
        if not root:
            frappe.throw(_("Thread not found."))
        root = _message(root[0])
    return {"messages": messages, "has_more": has_more, "has_newer": has_newer, "root": root, "focus": focus}


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
        modified=comment.creation, subject=thread), urls={f.name: f.file_url for f in files}, marks=NO_MARKS)
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
        urls={}, marks=NO_MARKS)})


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
    gone = [c.name for c in removed]
    frappe.db.delete("Techy Chat Reaction", {"message": ["in", gone]})
    frappe.db.delete("Techy Chat Pin", {"message": ["in", gone]})
    # Copies made for work orders are separate File records and stay with the job.
    for photo in _photo_urls(comment.reference_name, [n for c in removed for n in _split(c.content)[1]]):
        frappe.delete_doc("File", photo, ignore_permissions=True)
    return {"name": name}


def _member_message(name):
    """A chat message in a channel the user belongs to, with that channel."""
    row = frappe.db.get_value("Comment", name, MESSAGE_FIELDS + ["reference_doctype"], as_dict=True)
    if not row or row.reference_doctype != "Techy Channel" or row.comment_type != "Comment":
        frappe.throw(_("Message not found."))
    doc = _channel(row.reference_name)
    if doc.archived:
        frappe.throw(_("This channel is archived."))
    return row, doc


def _changed(doc, message, **changes):
    ops.push([row.user for row in doc.members], "techy_chat_update",
        {"channel": doc.name, "message": message, **changes})


@frappe.whitelist(methods=["POST"])
def react(message, emoji):
    """Add my reaction, or take it back if I already reacted with this emoji."""
    if emoji not in REACTIONS:
        frappe.throw(_("Choose one of the reactions offered."))
    row, doc = _member_message(message)
    mine = {"message": row.name, "user": frappe.session.user, "emoji": emoji}
    existing = frappe.db.get_value("Techy Chat Reaction", mine, "name")
    if existing:
        frappe.delete_doc("Techy Chat Reaction", existing, ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Techy Chat Reaction", "channel": doc.name, **mine}).insert(ignore_permissions=True)
    reactions = _marks([row.name])[0].get(row.name, [])
    _changed(doc, row.name, reactions=reactions)
    return reactions


@frappe.whitelist(methods=["POST"])
def pin(message, pinned=1):
    """Pin a message to the channel (or unpin it). Any member may, as in Slack."""
    row, doc = _member_message(message)
    existing = frappe.db.get_value("Techy Chat Pin", {"message": row.name}, "name")
    if cint(pinned) and not existing:
        if frappe.db.count("Techy Chat Pin", {"channel": doc.name}) >= MAX_PINS:
            frappe.throw(_("A channel can have at most {0} pinned messages. Unpin one first.").format(MAX_PINS))
        frappe.get_doc({"doctype": "Techy Chat Pin", "channel": doc.name, "message": row.name,
            "pinned_by": frappe.session.user}).insert(ignore_permissions=True)
        post_system_message(doc.name, _("{0} pinned a message").format(frappe.utils.get_fullname()))
    elif not cint(pinned) and existing:
        frappe.delete_doc("Techy Chat Pin", existing, ignore_permissions=True)
    _changed(doc, row.name, pinned=bool(cint(pinned)))
    return {"pinned": bool(cint(pinned))}


@frappe.whitelist()
def pins(channel):
    """The channel's pinned messages, most recently pinned first."""
    doc = _channel(channel, member=False)
    names = frappe.get_all("Techy Chat Pin", filters={"channel": doc.name}, order_by="creation desc", pluck="message")
    rows = {r.name: r for r in frappe.get_all("Comment", filters={"name": ["in", names or [""]],
        "reference_doctype": "Techy Channel", "reference_name": doc.name}, fields=MESSAGE_FIELDS)}
    urls = _photo_urls(doc.name, [n for r in rows.values() for n in _split(r.content)[1]])
    marks = _marks(list(rows))
    return [_message(rows[n], urls=urls, marks=marks) for n in names if n in rows]


def _readable_channels():
    member = frappe.get_all("Techy Channel Member", filters={"user": frappe.session.user,
        "parenttype": "Techy Channel"}, pluck="parent")
    return frappe.get_all("Techy Channel", filters={"archived": 0}, or_filters={"is_private": 0,
        "name": ["in", member or [""]]}, pluck="name")


@frappe.whitelist()
def search(query, channel=None, limit=30):
    """Messages containing the words, newest first, from one channel or every channel the reader can open."""
    ops.system_user()
    words = str(query or "").strip()[:80]
    if len(words) < 2:
        frappe.throw(_("Type at least 2 characters to search."))
    names = [_channel(channel, member=False).name] if channel else _readable_channels()
    if not names:
        return []
    limit = min(max(cint(limit), 1), 50)
    # Messages are stored HTML-escaped; LIKE wildcards in the words are matched literally.
    stored = escape(words).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = frappe.get_all("Comment", filters={"reference_doctype": "Techy Channel", "reference_name": ["in", names],
        "comment_type": "Comment", "content": ["like", f"%{stored}%"]}, fields=MESSAGE_FIELDS,
        order_by="creation desc", limit_page_length=limit * 2)
    # Ignore hits inside photo tokens.
    rows = [r for r in rows if words.lower() in ops.plain(_split(r.content)[0]).lower()][:limit]
    titles = {}
    for name in {r.reference_name for r in rows}:
        doc = frappe.get_doc("Techy Channel", name)
        titles[name] = {"title": _title(doc), "is_direct": doc.is_direct, "is_private": doc.is_private}
    urls = {}
    for name in titles:
        urls.update(_photo_urls(name, [n for r in rows if r.reference_name == name for n in _split(r.content)[1]]))
    marks = _marks([r.name for r in rows])
    return [{"channel": r.reference_name, **titles[r.reference_name], "message": _message(r, urls=urls, marks=marks)}
        for r in rows]


@frappe.whitelist(methods=["POST"])
def typing(channel, thread=None):
    """Tell the other members I am typing; the browser calls this at most every few seconds."""
    doc = _channel(channel)
    for row in doc.members:
        if row.user != frappe.session.user:
            frappe.publish_realtime("techy_typing", {"channel": doc.name, "thread": thread or None,
                "user": frappe.session.user, "full_name": frappe.utils.get_fullname()}, user=row.user)
    return {"ok": True}


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
