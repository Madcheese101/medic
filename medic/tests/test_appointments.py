import frappe
from frappe.utils import add_days, flt, today

from medic.constants import ActionType, AppointmentStatus, AppointmentType
from medic.tests.utils import MedicTestCase, appointment_status, call, make_doctor


class TestAppointmentLifecycle(MedicTestCase):
	def test_paid_consultation_checks_in_and_completes(self):
		name = self.make_appointment()
		self.assertEqual(appointment_status(name), AppointmentStatus.PENDING)

		fin = call("appointments.confirm_appointment_invoice", name=name)
		self.assertEqual(fin["grand_total"], 100)
		self.assertEqual(fin["outstanding_amount"], 100)
		self.assertEqual(appointment_status(name), AppointmentStatus.UNCONFIRMED)

		result = call("appointments.pay_appointment", name=name, payments=[self.cash(100)])
		self.assertEqual(result["outstanding_amount"], 0)
		self.assertEqual(appointment_status(name), AppointmentStatus.CONFIRMED)
		si = frappe.get_doc("Sales Invoice", fin["invoice"])
		self.assertEqual(si.docstatus, 1)
		# The first payment is collected on the invoice, under the cashier's POS Profile.
		self.assertEqual(si.pos_profile, self.fx.pos_profile)

		queue = call("appointments.check_in", appointment=name)
		self.assertEqual(call("appointments.check_in", appointment=name), queue)  # already checked in

		call("appointments.complete_appointment", name=name)
		self.assertEqual(appointment_status(name), AppointmentStatus.COMPLETED)

	def test_queue_numbers_follow_check_in_order(self):
		first, _ = self.make_paid_appointment()
		second, _ = self.make_paid_appointment()
		queue = call("appointments.check_in", appointment=first)
		self.assertEqual(call("appointments.check_in", appointment=second), queue + 1)

	def test_confirm_creates_a_draft_invoice_once(self):
		name = self.make_appointment()
		invoice = call("appointments.confirm_appointment", name=name)["invoice"]
		self.assertEqual(frappe.db.get_value("Sales Invoice", invoice, "docstatus"), 0)
		self.assertEqual(call("appointments.confirm_appointment_invoice", name=name)["invoice"], invoice)
		self.assertRaises(frappe.ValidationError, call, "appointments.confirm_appointment", name=name)

	def test_unpaid_appointment_cannot_check_in(self):
		name = self.make_appointment()
		call("appointments.confirm_appointment_invoice", name=name)
		self.assertRaises(frappe.ValidationError, call, "appointments.check_in", appointment=name)

	def test_appointment_must_be_checked_in_before_completing(self):
		name, _ = self.make_paid_appointment()
		self.assertRaises(frappe.ValidationError, call, "appointments.complete_appointment", name=name)

	def test_cancelled_appointment_frees_its_slot(self):
		doctor = make_doctor(maximum_appointments=1)
		first = self._book(doctor)
		self.assertRaises(frappe.ValidationError, self._book, doctor)

		# A refund cancels the appointment this way, leaving it submitted.
		frappe.db.set_value("Patient Appointment", first, "appointment_status", AppointmentStatus.CANCELLED)
		self._book(doctor)
		booked = call("appointments.get_doctor_availability", employee=doctor)["booked"]
		self.assertEqual(booked[today()], 1)

	def _book(self, doctor):
		return call(
			"appointments.create_appointment",
			appointment_type=AppointmentType.CONSULTATION,
			customer=self.make_patient(),
			employee=doctor,
			appointment_date=today(),
			service_type=self.fx.consult_group,
			service=self.fx.consult_item,
		)


class TestAppointmentPayments(MedicTestCase):
	def test_consultation_must_be_paid_in_full(self):
		name = self.make_appointment(AppointmentType.CONSULTATION)
		call("appointments.confirm_appointment_invoice", name=name)
		self.assertRaises(
			frappe.ValidationError, call, "appointments.pay_appointment", name=name, payments=[self.cash(40)]
		)

	def test_review_can_be_paid_in_parts(self):
		name = self.make_appointment(AppointmentType.REVIEW)
		call("appointments.confirm_appointment_invoice", name=name)

		result = call("appointments.pay_appointment", name=name, payments=[self.cash(40)])
		self.assertEqual(result["outstanding_amount"], 60)
		self.assertEqual(appointment_status(name), AppointmentStatus.UNCONFIRMED)

		# Top-up on the now-submitted invoice goes through a Payment Entry.
		result = call("appointments.pay_appointment", name=name, payments=[self.cash(60)])
		self.assertEqual(result["outstanding_amount"], 0)
		self.assertEqual(appointment_status(name), AppointmentStatus.CONFIRMED)

	def test_split_local_and_foreign_payment(self):
		name = self.make_appointment()
		invoice = call("appointments.confirm_appointment_invoice", name=name)["invoice"]
		call("appointments.pay_appointment", name=name, payments=[self.cash(40), self.foreign(20, 3)])

		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")), 0)
		self.assertEqual(appointment_status(name), AppointmentStatus.CONFIRMED)
		pe = frappe.get_doc("Payment Entry", _payment_entry_for(invoice))
		self.assertEqual(pe.paid_to_account_currency, self.fx.foreign_currency)
		self.assertEqual(flt(pe.received_amount), 20)
		self.assertEqual(flt(pe.paid_amount), 60)

	def test_foreign_overshoot_is_folded_into_the_rate(self):
		# 30.01 at 3.333 is 100.02 against 100 owed; the 0.02 must not stay as an advance.
		name = self.make_appointment()
		invoice = call("appointments.confirm_appointment_invoice", name=name)["invoice"]
		call("appointments.pay_appointment", name=name, payments=[self.foreign(30.01, 3.333)])

		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")), 0)
		pe = frappe.get_doc("Payment Entry", _payment_entry_for(invoice))
		self.assertEqual(flt(pe.paid_amount), 100)
		self.assertEqual(flt(pe.unallocated_amount), 0)

	def test_foreign_payment_needs_an_exchange_rate(self):
		name = self.make_appointment()
		call("appointments.confirm_appointment_invoice", name=name)
		self.assertRaises(
			frappe.ValidationError,
			call,
			"appointments.pay_appointment",
			name=name,
			payments=[{"mode_of_payment": self.fx.foreign, "amount": 30}],
		)

	def test_action_invoice_is_paid_in_full_and_marks_the_row_paid(self):
		name, _ = self.make_paid_appointment()
		invoice = call(
			"appointments.create_appointment_action",
			name=name,
			service=self.fx.session_item,
			action_type=ActionType.TREATMENT,
		)
		self.assertRaises(
			frappe.ValidationError,
			call,
			"appointments.pay_appointment_action",
			invoice=invoice,
			payments=[self.cash(50)],
		)
		call("appointments.pay_appointment_action", invoice=invoice, payments=[self.cash(100)])
		row = next(
			r for r in call("appointments.get_appointment", name=name)["actions"] if r["invoice"] == invoice
		)
		self.assertEqual(row["paid"], 1)
		self.assertEqual(row["outstanding_amount"], 0)


class TestLists(MedicTestCase):
	def test_appointments_page_and_filter_by_date_range(self):
		patient = self.make_patient()
		names = {self.make_appointment(patient=patient) for _ in range(3)}

		first = call(
			"appointments.get_appointments",
			customer=patient,
			from_date=today(),
			to_date=today(),
			page_length=2,
		)
		self.assertEqual(first["total"], 3)
		self.assertEqual(len(first["rows"]), 2)
		rest = call("appointments.get_appointments", customer=patient, start=2, page_length=2)
		self.assertEqual({r["name"] for r in first["rows"] + rest["rows"]}, names)

		tomorrow = add_days(today(), 1)
		listed = call("appointments.get_appointments", customer=patient, from_date=tomorrow, to_date=tomorrow)
		self.assertEqual(listed, {"rows": [], "total": 0})

	def test_lists_sort_only_on_their_own_columns(self):
		patient = self.make_patient()
		older = self.make_appointment(patient=patient)
		newer = self.make_appointment(patient=patient)

		rows = call(
			"appointments.get_appointments", customer=patient, sort_by="name", sort_order="asc"
		)["rows"]
		self.assertEqual([r["name"] for r in rows], sorted([older, newer]))
		# Anything else keeps the default order (newest first) instead of reaching the SQL.
		rows = call(
			"appointments.get_appointments", customer=patient, sort_by="name; select 1", sort_order="asc"
		)["rows"]
		self.assertEqual([r["name"] for r in rows], [newer, older])

	def test_outstanding_invoices_are_the_submitted_ones_still_owing(self):
		patient = self.make_patient()
		call("appointments.confirm_appointment_invoice", name=self.make_appointment(patient=patient))  # draft
		paid = self.make_appointment(patient=patient)
		call("appointments.confirm_appointment_invoice", name=paid)
		call("appointments.pay_appointment", name=paid, payments=[self.cash(100)])
		part = self.make_appointment(AppointmentType.REVIEW, patient=patient)
		owing = call("appointments.confirm_appointment_invoice", name=part)["invoice"]
		call("appointments.pay_appointment", name=part, payments=[self.cash(40)])

		self.assertEqual(call("billing.get_sales_invoices", customer=patient)["total"], 3)
		listed = call("billing.get_sales_invoices", customer=patient, outstanding_only=1)
		self.assertEqual([(r["name"], r["outstanding_amount"]) for r in listed["rows"]], [(owing, 60)])


def _payment_entry_for(invoice):
	return frappe.db.get_value(
		"Payment Entry Reference",
		{"reference_doctype": "Sales Invoice", "reference_name": invoice, "docstatus": 1},
		"parent",
	)
