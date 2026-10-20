# Copyright (c) 2026, Nawa Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from medic.billing import apply_discount, company
from medic.constants import AppointmentStatus


class PatientAppointment(Document):
	def ensure_invoice(self):
		"""Return the appointment's Sales Invoice, creating a draft one if missing. Idempotent."""
		if self.invoice:
			return self.invoice

		si = frappe.new_doc("Sales Invoice")
		si.customer = self.customer
		si.company = company()
		# Custom Link field on Sales Invoice; the payment and cancel paths use it to reach the PA.
		si.patient_appointment = self.name
		si.append("items", {"item_code": self.service, "qty": 1})
		if flt(self.get("discount_percentage")):
			apply_discount(si, flt(self.discount_percentage))
		si.insert()  # draft (docstatus 0)

		# invoice / appointment_status are read-only on a submitted doc; db_set bypasses that.
		self.db_set("invoice", si.name)
		if self.appointment_status == AppointmentStatus.PENDING:
			self.db_set("appointment_status", AppointmentStatus.UNCONFIRMED)
		return si.name

	@frappe.whitelist()
	def confirm_appointment(self):
		"""Create the draft Sales Invoice for a Pending appointment, which marks it Not Confirmed."""
		if self.docstatus != 1:
			frappe.throw(_("Appointment must be submitted before confirming."))
		if self.appointment_status != AppointmentStatus.PENDING:
			frappe.throw(_("Appointment is already confirmed."))
		return self.ensure_invoice()

	def check_in(self):
		"""Assign the per-doctor, per-day queue number when the patient arrives."""
		if self.queue:
			return self.queue  # already checked in
		if self.appointment_status == AppointmentStatus.CANCELLED:
			frappe.throw(_("Cancelled appointments cannot be checked in."))

		if self.treatment_plan:
			plan = frappe.get_doc("Treatment Plan", self.treatment_plan)
			is_last = cint(self.session_no) == cint(plan.total_sessions)
			if not plan.session_gate_ok(is_last):
				frappe.throw(_("Payment requirement for this session is not met yet."))
		elif self.appointment_status != AppointmentStatus.CONFIRMED:
			frappe.throw(_("Appointment must be paid before check-in."))

		self.db_set("queue", self._next_queue())
		# Queuing a session means its gate passed; reflect that on the appointment.
		# The session only counts toward the plan once the doctor completes it.
		if self.treatment_plan and self.appointment_status != AppointmentStatus.CONFIRMED:
			self.db_set("appointment_status", AppointmentStatus.CONFIRMED)
		return self.queue

	def complete(self):
		"""Mark a checked-in appointment as completed."""
		if self.docstatus != 1:
			frappe.throw(_("Appointment must be submitted."))
		if not self.queue:
			frappe.throw(_("Appointment must be checked in before completing."))
		# Count the treatment-plan session toward the plan on completion (once).
		if self.treatment_plan and self.appointment_status != AppointmentStatus.COMPLETED:
			plan = frappe.get_doc("Treatment Plan", self.treatment_plan)
			plan.db_set("completed_sessions", cint(plan.completed_sessions) + 1)
		self.db_set("appointment_status", AppointmentStatus.COMPLETED)

	def _next_queue(self):
		taken = frappe.get_all(
			"Patient Appointment",
			filters={"employee": self.employee, "appointment_date": self.appointment_date, "queue": [">", 0]},
			pluck="queue",
		)
		return (max(taken) + 1) if taken else 1
