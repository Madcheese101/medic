# Copyright (c) 2026, Nawa Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DoctorSchedule(Document):
	def before_save(self):
		for row in self.schedule:
			if row.is_active:
				continue
			row.from_time = None
			row.to_time = None
			row.maximum_appointments = 0

	@frappe.whitelist()
	def fill_table(self):
		days = ["Saturday", "Sunday", "Monday",
			"Tuesday", "Wednesday", "Thursday", "Friday"]
		for day in days:
			self.append("schedule", {"day": day})
