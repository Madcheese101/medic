# Copyright (c) 2026, Nawa Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Prescription(Document):
	def validate(self):
		self.validate_schedule_fields()

	def validate_schedule_fields(self):
		"""Times/Per/For are required only for Pharma items that require a schedule."""
		for row in self.items:
			item_type, requires_schedule = frappe.db.get_value(
				"Item", row.item, ["item_type", "requires_schedule"]
			)
			if item_type != "Pharma" or not requires_schedule:
				continue

			if not row.times or not row.per or not row.get("for"):
				frappe.throw(
					_("Row #{0}: Times, Per and For are required for {1}.").format(
						row.idx, row.item
					)
				)
