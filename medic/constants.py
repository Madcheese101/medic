# Stored values of Medic's Select fields. Keep in sync with the doctype JSON options and
# medic/medic/page/medic_pos/constants.js.

from frappe import _


def label(value, doctype):
	"""A stored Select value as the user reads it. Its translation is keyed by the doctype, the
	context Frappe's own formatter uses, so it can differ from the word's meaning elsewhere."""
	return _(value, context=doctype)


class AppointmentStatus:
	PENDING = "Pending"
	UNCONFIRMED = "Unconfirmed"
	CONFIRMED = "Confirmed"
	COMPLETED = "Completed"
	CANCELLED = "Cancelled"


class AppointmentType:
	CONSULTATION = "Consultation"
	TREATMENT = "Treatment"
	REVIEW = "Review"
	FOLLOW_UP = "Follow-up"


class ActionType:
	TREATMENT = "Treatment"
	LAB_TEST = "Lab Test"
	PRESCRIPTION = "Prescription"


class IllnessType:
	OTHER = "Other"
	SKIN = "Skin"
