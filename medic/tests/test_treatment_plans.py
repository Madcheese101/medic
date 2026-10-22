import frappe
from frappe.utils import flt

from medic.constants import AppointmentStatus
from medic.tests.utils import MedicTestCase, appointment_status, call


class TestTreatmentPlans(MedicTestCase):
	def test_discount_is_applied_to_estimate_and_invoice(self):
		patient = self.make_patient()
		plan = self.make_plan(5, patient=patient, discount_percentage=10)

		self.assertEqual(call("treatments.get_treatment_plan", name=plan)["estimated_total"], 450)
		listed = next(
			r for r in call("treatments.list_treatment_plans", customer=patient)["rows"] if r["name"] == plan
		)
		self.assertEqual(listed["estimated_total"], 450)

		invoice = call("treatments.create_treatment_plan_invoice", name=plan)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice, "grand_total")), 450)
		self.assertEqual(frappe.db.get_value("Treatment Plan", plan, "status"), "Active")

	def test_intermediate_session_needs_the_deposit(self):
		plan = self.make_plan(5)
		invoice = call("treatments.create_treatment_plan_invoice", name=plan)  # 500, nothing paid

		session = call("treatments.create_session", treatment_plan=plan)
		self.assertEqual(appointment_status(session), AppointmentStatus.PENDING)
		self.assertRaises(frappe.ValidationError, call, "appointments.check_in", appointment=session)

		call("billing.record_payments", invoice=invoice, payments=[self.cash(100)])  # 20%
		call("appointments.check_in", appointment=session)
		self.assertEqual(appointment_status(session), AppointmentStatus.CONFIRMED)

	def test_deposit_paid_with_the_invoice_confirms_sessions(self):
		plan = self.make_plan(5)
		invoice = call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(100)])
		self.assertEqual(frappe.db.get_value("Sales Invoice", invoice, "pos_profile"), self.fx.pos_profile)

		session = call("treatments.create_session", treatment_plan=plan)
		self.assertEqual(appointment_status(session), AppointmentStatus.CONFIRMED)

	def test_skip_deposit_waives_the_deposit(self):
		plan = self.make_plan(5)
		frappe.db.set_value("Treatment Plan", plan, "skip_deposit", 1)
		call("treatments.create_treatment_plan_invoice", name=plan)
		session = call("treatments.create_session", treatment_plan=plan)
		self.assertEqual(appointment_status(session), AppointmentStatus.CONFIRMED)

	def test_last_session_needs_full_payment_unless_credit_is_allowed(self):
		patient = self.make_patient()
		plan = self.make_plan(1, patient=patient)
		call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(50)])
		self.assertRaises(frappe.ValidationError, call, "treatments.create_session", treatment_plan=plan)

		frappe.db.set_value("Customer", patient, "allow_credit", 1)
		session = call("treatments.create_session", treatment_plan=plan)
		self.assertEqual(appointment_status(session), AppointmentStatus.CONFIRMED)

	def test_completed_session_counts_toward_the_plan(self):
		plan = self.make_plan(2)
		call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(200)])
		session = call("treatments.create_session", treatment_plan=plan)
		self.assertEqual(frappe.db.get_value("Patient Appointment", session, "session_no"), 1)

		call("appointments.check_in", appointment=session)
		self.assertEqual(frappe.db.get_value("Treatment Plan", plan, "completed_sessions"), 0)
		call("appointments.complete_appointment", name=session)
		self.assertEqual(frappe.db.get_value("Treatment Plan", plan, "completed_sessions"), 1)

	def test_no_more_sessions_than_planned(self):
		plan = self.make_plan(1)
		call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(100)])
		call("treatments.create_session", treatment_plan=plan)
		self.assertRaises(frappe.ValidationError, call, "treatments.create_session", treatment_plan=plan)

	def test_closed_plan_takes_no_sessions(self):
		plan = self.make_plan(3)
		call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(300)])
		# A refund closes the plan this way.
		frappe.db.set_value("Treatment Plan", plan, "status", "Completed")
		self.assertRaises(frappe.ValidationError, call, "treatments.create_session", treatment_plan=plan)

	def test_cancelled_session_is_booked_again_under_its_number(self):
		plan = self.make_plan(3)
		call("treatments.create_treatment_plan_invoice", name=plan, payments=[self.cash(300)])
		first = call("treatments.create_session", treatment_plan=plan)
		call("treatments.create_session", treatment_plan=plan)
		frappe.db.set_value("Patient Appointment", first, "appointment_status", AppointmentStatus.CANCELLED)

		numbers = [
			frappe.db.get_value(
				"Patient Appointment", call("treatments.create_session", treatment_plan=plan), "session_no"
			)
			for _ in range(2)
		]
		self.assertEqual(numbers, [1, 3])
		self.assertRaises(frappe.ValidationError, call, "treatments.create_session", treatment_plan=plan)

	def test_added_sessions_are_free(self):
		plan = self.make_plan(2)
		invoice = call("treatments.create_treatment_plan_invoice", name=plan)
		self.assertEqual(call("treatments.add_treatment_sessions", name=plan, sessions=2), 4)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice, "grand_total")), 200)
