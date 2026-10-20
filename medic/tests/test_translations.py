import frappe
from frappe.tests.utils import FrappeTestCase

from medic.constants import label

# Select fields whose stored English values are shown to users through medic/translations.
LABELLED_FIELDS = (
	("Patient Appointment", "appointment_status"),
	("Patient Appointment", "appointment_type"),
	("Appointment Actions", "action_type"),
	("Illness", "illness_type"),
)


class TestSelectLabels(FrappeTestCase):
	def test_every_option_has_an_arabic_label(self):
		self.addCleanup(setattr, frappe.local, "lang", frappe.local.lang)
		frappe.local.lang = "ar"
		for doctype, fieldname in LABELLED_FIELDS:
			for value in filter(None, frappe.get_meta(doctype).get_field(fieldname).options.split("\n")):
				with self.subTest(doctype=doctype, value=value):
					self.assertNotEqual(label(value, doctype), value)
