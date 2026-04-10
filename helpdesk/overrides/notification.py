import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import (
	NotificationLog,
	send_notification_email,
	set_notifications_as_unseen,
)
from frappe.desk.doctype.notification_settings.notification_settings import (
	is_email_notifications_enabled_for_type,
)


class CustomNotificationLog(NotificationLog):
	def after_insert(self):
		frappe.publish_realtime("notification", after_commit=True, user=self.for_user)
		set_notifications_as_unseen(self.for_user)

		# Suppress assignment emails for HD Ticket — agents receive in-app notifications only
		if self.type == "Assignment" and self.document_type == "HD Ticket":
			return

		if is_email_notifications_enabled_for_type(self.for_user, self.type):
			try:
				send_notification_email(self)
			except frappe.OutgoingEmailError:
				self.log_error(_("Failed to send notification email"))

