# Copyright (c) 2026, Nawa Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from medic.billing import invoice_financials

DEPOSIT_PCT = 0.2


class TreatmentPlan(Document):
	def session_gate_ok(self, is_last):
		"""Whether a session may proceed. Intermediate sessions need DEPOSIT_PCT of the plan invoice
		paid, the last one all of it. Two waivers: per-plan skip_deposit, per-customer allow_credit."""
		# No invoice means no payment can have been made, so the gate stays shut.
		if not self.invoice:
			return False
		fin = invoice_financials(self.invoice)
		if is_last:
			if fin["outstanding_amount"] <= 0:
				return True
			return bool(frappe.db.get_value("Customer", self.customer, "allow_credit"))
		if self.skip_deposit:
			return True
		return fin["paid_pct"] >= DEPOSIT_PCT
