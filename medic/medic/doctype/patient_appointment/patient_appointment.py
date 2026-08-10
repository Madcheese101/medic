# Copyright (c) 2026, Nawa Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PatientAppointment(Document):
	@frappe.whitelist()
	def create_sales_invoice(self, service, discount):
		# Implementation for creating a sales invoice
		pass
	@frappe.whitelist()
	def create_procedure_appointment(self, service, discount):
		# Implementation for creating a procedure appointment
		pass

	@frappe.whitelist()
	def confirm_appointment(self):
		# it creates a draft sales invoice with the appointment's service
		pass
