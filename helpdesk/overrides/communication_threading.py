import frappe


def ensure_email_threading(doc, method):
    """
    Ensure correct email threading for sent communications.

    IMPORTANT: Communication.message_id MUST be stored WITHOUT angle brackets.
    Frappe's inbound mail handler extracts the In-Reply-To header value by
    stripping brackets (get_string_between("<", value, ">")), then does:
        Communication.find_one_by_filters(message_id=bare_value)
    If we store message_id WITH brackets the lookup never matches → new ticket.
    """
    try:
        if doc.communication_type != "Communication":
            return

        # --- Incoming emails ---
        # Frappe's receive.py already strips brackets before storing message_id.
        # Strip here too as a safety net, never add them.
        if doc.sent_or_received == "Received" and doc.message_id:
            doc.message_id = _strip_brackets(doc.message_id)

        # --- Outgoing emails linked to HD Ticket ---
        # reply_via_agent() already sets in_reply_to to the parent Communication
        # doc name. This block is a safety net for any other send path that may
        # not set it.
        if (
            doc.sent_or_received == "Sent"
            and doc.reference_doctype == "HD Ticket"
            and not doc.in_reply_to
        ):
            last_received = frappe.get_all(
                "Communication",
                filters={
                    "reference_doctype": "HD Ticket",
                    "reference_name": doc.reference_name,
                    "sent_or_received": "Received",
                    "message_id": ["is", "set"],
                },
                fields=["name"],
                order_by="creation desc",
                limit=1,
            )
            if last_received:
                doc.in_reply_to = last_received[0].name

        # Ensure outgoing message_id is also stored without brackets
        if doc.sent_or_received == "Sent" and doc.message_id:
            doc.message_id = _strip_brackets(doc.message_id)

    except Exception as e:
        frappe.log_error("ensure_email_threading error: {}".format(str(e)))


def _strip_brackets(value: str) -> str:
    """Return message_id without surrounding angle brackets."""
    if not value:
        return value
    return value.strip().strip("<>").strip()


def add_threading_headers(doc, method):
    """
    Inject References, Thread-Topic, and Thread-Index headers into outgoing
    emails so Gmail/Outlook group them into the same thread.

    Runs as Email Queue before_insert hook.
    """
    import base64
    import hashlib
    import re
    import struct
    import time

    try:
        if not doc.message:
            return

        # Resolve the Communication linked to this Email Queue entry
        comm_name = None
        if hasattr(doc, "communication") and doc.communication:
            comm_name = doc.communication

        if not comm_name or not frappe.db.exists("Communication", comm_name):
            return

        ref_doctype = frappe.db.get_value("Communication", comm_name, "reference_doctype")
        ref_name = frappe.db.get_value("Communication", comm_name, "reference_name")

        if ref_doctype != "HD Ticket" or not ref_name:
            return

        # Build References from every message_id in this ticket thread
        all_comms = frappe.get_all(
            "Communication",
            filters={
                "reference_doctype": "HD Ticket",
                "reference_name": ref_name,
                "message_id": ["is", "set"],
            },
            fields=["message_id"],
            order_by="creation asc",
        )

        if not all_comms:
            return

        # References header needs angle-bracketed message ids
        references = []
        for c in all_comms:
            msg_id = _strip_brackets(c.message_id)
            if msg_id:
                references.append("<{}>".format(msg_id))

        if not references:
            return

        references_str = " ".join(references)

        # Thread-Topic: subject without Re:/Fwd: prefix (Outlook uses this)
        ticket_subject = frappe.db.get_value("HD Ticket", ref_name, "subject") or ""
        thread_topic = re.sub(r"^(Re|Fwd|FW|RE)\s*:\s*", "", ticket_subject, flags=re.IGNORECASE).strip()

        # Thread-Index: deterministic from the first message id (Outlook)
        first_msg_id = _strip_brackets(all_comms[0].message_id)
        guid = hashlib.md5(first_msg_id.encode()).digest()
        ft = int((time.time() + 11644473600) * 10000000)
        ts_bytes = struct.pack(">Q", ft)[:6]
        thread_index = base64.b64encode(ts_bytes + guid).decode()

        # Patch the raw email message string
        import email as email_lib
        msg = email_lib.message_from_string(doc.message)

        if not msg.get("References"):
            msg["References"] = references_str

        if not msg.get("Thread-Topic"):
            msg["Thread-Topic"] = thread_topic

        if not msg.get("Thread-Index"):
            msg["Thread-Index"] = thread_index

        # Ensure In-Reply-To is angle-bracketed (email header convention)
        in_reply_to = msg.get("In-Reply-To")
        if in_reply_to:
            bare = _strip_brackets(in_reply_to)
            if bare:
                del msg["In-Reply-To"]
                msg["In-Reply-To"] = "<{}>".format(bare)

        doc.message = msg.as_string()

    except Exception as e:
        frappe.log_error("add_threading_headers error: {}".format(str(e)))
