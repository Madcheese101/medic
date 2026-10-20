import unittest

import frappe
from frappe.utils import flt

from medic.constants import AppointmentStatus, AppointmentType
from medic.tests.utils import MedicTestCase, appointment_status, call


class TestInvoiceReturns(MedicTestCase):
	def test_appointment_refund_is_capped_at_what_was_paid(self):
		name, invoice = self.make_paid_appointment()
		info = call("billing.get_invoice_return_info", invoice=invoice)
		self.assertEqual(info["kind"], "appointment")
		self.assertEqual(info["max_refund"], 100)
		self.assertRaises(
			frappe.ValidationError,
			call,
			"billing.create_invoice_return",
			invoice=invoice,
			amount=150,
			payments=[self.cash(150)],
		)

		result = call("billing.create_invoice_return", invoice=invoice, amount=100, payments=[self.cash(100)])
		credit_note = frappe.get_doc("Sales Invoice", result["credit_note"])
		self.assertEqual(credit_note.is_return, 1)
		self.assertEqual(credit_note.return_against, invoice)
		self.assertEqual(flt(credit_note.grand_total), -100)
		self.assertEqual(appointment_status(name), AppointmentStatus.CANCELLED)

		info = call("billing.get_invoice_return_info", invoice=invoice)
		self.assertEqual(info["refunded"], 100)
		self.assertIsNone(info["kind"])  # fully refunded

	@unittest.expectedFailure
	def test_partial_appointment_refund(self):
		# Known bug: 40 of 100 becomes qty -0.4, which a "Must be Whole Number" UOM rejects.
		_, invoice = self.make_paid_appointment()
		call("billing.create_invoice_return", invoice=invoice, amount=40, payments=[self.cash(40)])

	def test_refund_payments_must_add_up_to_the_amount(self):
		_, invoice = self.make_paid_appointment(AppointmentType.REVIEW)
		self.assertRaises(
			frappe.ValidationError,
			call,
			"billing.create_invoice_return",
			invoice=invoice,
			amount=40,
			payments=[self.cash(30)],
		)

	def test_unpaid_invoice_is_not_returnable(self):
		name = self.make_appointment(AppointmentType.REVIEW)
		invoice = call("appointments.confirm_appointment_invoice", name=name)["invoice"]
		info = call("billing.get_invoice_return_info", invoice=invoice)
		self.assertIsNone(info["kind"])

	def test_plan_refund_keeps_the_completed_sessions_share(self):
		plan = self.make_plan(4)  # 4 x 100
		invoice = call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(300)])
		frappe.db.set_value("Treatment Plan", plan, "completed_sessions", 1)

		info = call("billing.get_invoice_return_info", invoice=invoice)
		self.assertEqual(info["kind"], "treatment_plan")
		self.assertEqual(info["per_session"], 100)
		self.assertEqual(info["refundable"], 200)
		self.assertRaises(
			frappe.ValidationError,
			call,
			"billing.create_invoice_return",
			invoice=invoice,
			amount=100,
			payments=[self.cash(100)],
		)

		result = call("billing.create_invoice_return", invoice=invoice, amount=200, payments=[self.cash(200)])
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice", result["credit_note"], "grand_total")), -200
		)
		self.assertEqual(frappe.db.get_value("Treatment Plan", plan, "status"), "Completed")

	@unittest.expectedFailure
	def test_plan_refund_of_part_of_a_session(self):
		# Known bug: 150 becomes qty -1.5, which a "Must be Whole Number" UOM (like Nos) rejects.
		plan = self.make_plan(4)
		invoice = call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(250)])
		frappe.db.set_value("Treatment Plan", plan, "completed_sessions", 1)
		call("billing.create_invoice_return", invoice=invoice, amount=150, payments=[self.cash(150)])
