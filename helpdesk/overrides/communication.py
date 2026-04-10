import re

import frappe


# Subjects shorter than this won't be used for matching (too generic to be safe)
_MIN_SUBJECT_LEN = 8


def _normalize_subject(subject: str) -> str:
    """Strip Re:/Fw:/Fwd: prefixes and return lower-cased, whitespace-collapsed subject."""
    s = re.sub(r"^(RE|FW|FWD)\s*:\s*", "", subject or "", flags=re.IGNORECASE).strip()
    return re.sub(r"\s+", " ", s).lower()


def after_communication_insert(doc, method=None):
    try:
        _auto_merge(doc)
        _auto_split_different_subject(doc)
    except Exception:
        frappe.log_error(title="auto_communication_insert error", message=frappe.get_traceback())


# ---------------------------------------------------------------------------
# AUTO-MERGE
# Fixes: client sends RE: emails without In-Reply-To → new tickets created
# ---------------------------------------------------------------------------

def _auto_merge(doc):
    """
    When a received email creates a brand-new HD Ticket with a RE:/FW: subject
    but couldn't be threaded via In-Reply-To, find the matching older ticket from
    the same sender and silently merge the duplicate into it.
    """
    if doc.communication_type != "Communication":
        return
    if doc.sent_or_received != "Received":
        return
    if doc.reference_doctype != "HD Ticket" or not doc.reference_name:
        return
    # Skip if Frappe already threaded this via In-Reply-To (doc.in_reply_to is set)
    if doc.in_reply_to:
        return

    ticket_name = doc.reference_name

    # The ticket must have only this one communication (brand new ticket from this email)
    existing_comm_count = frappe.db.count(
        "Communication",
        {"reference_doctype": "HD Ticket", "reference_name": ticket_name},
    )
    if existing_comm_count > 1:
        return

    ticket = frappe.db.get_value(
        "HD Ticket",
        ticket_name,
        ["name", "subject", "raised_by", "status", "is_merged"],
        as_dict=True,
    )
    if not ticket or ticket.is_merged:
        return

    # Only auto-merge when the subject signals this is a reply
    raw_subject = ticket.subject or ""
    if not re.match(r"^(RE|FW|FWD)\s*:", raw_subject, re.IGNORECASE):
        return

    base_subject = _normalize_subject(raw_subject)
    if len(base_subject) < _MIN_SUBJECT_LEN:
        return  # too short to match safely

    sender = ticket.raised_by
    if not sender:
        return

    # Find the earliest matching open ticket from the same sender
    candidates = frappe.db.get_all(
        "HD Ticket",
        filters={
            "name": ["!=", ticket_name],
            "raised_by": sender,
            "is_merged": 0,
            "status": ["!=", "Closed"],
            "creation": [">", frappe.utils.add_days(frappe.utils.now_datetime(), -90)],
        },
        fields=["name", "subject", "creation"],
        order_by="creation asc",
    )

    target_name = None
    for c in candidates:
        if _normalize_subject(c.subject) == base_subject:
            target_name = c.name
            break

    if not target_name:
        return

    # Move this communication to the existing (older) ticket
    frappe.db.set_value("Communication", doc.name, "reference_name", target_name)
    doc.reference_name = target_name

    # Close the duplicate ticket, bypassing the time_duration validation
    frappe.db.set_value(
        "HD Ticket",
        ticket_name,
        {"status": "Closed", "is_merged": 1, "merged_with": target_name},
        update_modified=False,
    )

    frappe.get_doc({
        "doctype": "HD Ticket Comment",
        "commented_by": frappe.session.user or "Administrator",
        "reference_ticket": target_name,
        "content": (
            f"New email from {sender} was automatically linked here from duplicate "
            f"ticket <a href='/helpdesk/tickets/{ticket_name}'>#{ticket_name}</a> "
            f"(subject match: '{base_subject}')."
        ),
    }).insert(ignore_permissions=True)

    frappe.logger().info(
        f"[auto-merge] Communication {doc.name} re-linked: "
        f"ticket {ticket_name} → {target_name} (sender={sender}, subject='{base_subject}')"
    )


# ---------------------------------------------------------------------------
# AUTO-SPLIT
# Fixes: client clicks Reply on old email, changes subject → different issue
#        lands in wrong ticket because In-Reply-To still matches original
# ---------------------------------------------------------------------------

def _auto_split_different_subject(doc):
    """
    When a received email is threaded (via In-Reply-To) into an existing HD Ticket
    but its subject is completely different from the ticket's subject, split it
    out into a new ticket automatically.

    Example: client replies to ticket "File 64026 - revert to Ongoing" but changes
    the subject to "File 62049 - Change of container ownership". These are different
    issues and should be separate tickets.
    """
    if doc.communication_type != "Communication":
        return
    if doc.sent_or_received != "Received":
        return
    if doc.reference_doctype != "HD Ticket" or not doc.reference_name:
        return
    # Only act when Frappe threaded this via In-Reply-To
    if not doc.in_reply_to:
        return

    ticket_name = doc.reference_name
    ticket_subject = frappe.db.get_value("HD Ticket", ticket_name, "subject") or ""

    email_subject = doc.subject or ""

    base_ticket = _normalize_subject(ticket_subject)
    base_email = _normalize_subject(email_subject)

    # Subjects match — same thread, no split needed
    if base_ticket == base_email:
        return

    # Too short to be safe
    if len(base_ticket) < _MIN_SUBJECT_LEN or len(base_email) < _MIN_SUBJECT_LEN:
        return

    # One subject contains the other (partial match = same topic, just reworded)
    if base_email in base_ticket or base_ticket in base_email:
        return

    # Subjects are completely different — split into a new ticket
    from helpdesk.helpdesk.doctype.hd_ticket.api import duplicate_ticket

    ticket_doc = frappe.get_doc("HD Ticket", ticket_name)
    new_ticket_name = duplicate_ticket(ticket_doc, email_subject)

    # Re-link only this single communication to the new ticket
    frappe.db.set_value(
        "Communication", doc.name, "reference_name", new_ticket_name, update_modified=False
    )
    doc.reference_name = new_ticket_name

    # Comment on the original ticket
    frappe.get_doc({
        "doctype": "HD Ticket Comment",
        "commented_by": frappe.session.user or "Administrator",
        "reference_ticket": ticket_name,
        "content": (
            f"An email with a different subject '<b>{email_subject}</b>' was automatically "
            f"split into a new ticket "
            f"<a href='/helpdesk/tickets/{new_ticket_name}'>#{new_ticket_name}</a>."
        ),
    }).insert(ignore_permissions=True)

    frappe.logger().info(
        f"[auto-split] Communication {doc.name} split: "
        f"ticket {ticket_name} ('{base_ticket}') → new ticket {new_ticket_name} ('{base_email}')"
    )
