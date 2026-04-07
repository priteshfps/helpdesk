import frappe
from bs4 import BeautifulSoup

from helpdesk.utils import agent_only


@frappe.whitelist()
def get_agent_signature():
    """
    Return the email signature for the current logged-in user as clean HTML.

    Frappe's TextEditor stores signatures wrapped in a ql-editor div:
      <div class="ql-editor read-mode"><p>--</p><p>Regards</p>...</div>

    We extract the inner HTML as-is (preserving the <p> tags) so the
    frontend can inject it directly without any additional wrapping.
    """
    raw = frappe.db.get_value("User", frappe.session.user, "email_signature")
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    ql_div = soup.find("div", class_=lambda c: c and "ql-editor" in c)
    if ql_div:
        # decode_contents() returns the inner HTML string with all child tags intact
        return str(ql_div.decode_contents())
    return raw


@frappe.whitelist()
@agent_only
def sent_invites(emails: list[str], send_welcome_mail_to_user: bool = True):
    for email in emails:
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)
        else:
            user = frappe.get_doc(
                {"doctype": "User", "email": email, "first_name": email.split("@")[0]}
            ).insert()

            if send_welcome_mail_to_user:
                user.send_welcome_mail_to_user()

        frappe.get_doc(
            {
                "doctype": "HD Agent",
                "ID": email,
                "user": user.name,
                "agent_name": user.full_name,
                "user_image": user.user_image,
            }
        ).insert()
    return
