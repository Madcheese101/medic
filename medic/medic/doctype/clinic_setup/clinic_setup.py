# Copyright (c) 2026, Nawa Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ClinicSetup(Document):
	def validate(self):
		if self.enable_pharmacy and not self.pharmacy_item_group:
			frappe.throw(_("Please select a Pharmacy Item Group if Pharmacy is enabled."))
		if self.enable_test_lab and not self.test_lab_item_group:
			frappe.throw(_("Please select a Test Lab Item Group if Test Lab is enabled."))
