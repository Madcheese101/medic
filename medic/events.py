import frappe


def on_employee_create(doc, method=None):
	doctor_default_designation = frappe.db.get_value("Clinic Setup", None, "doctors_default_designation")
	if doc.designation == doctor_default_designation:
		create_doctor_schedule(doc.name)

def create_doctor_schedule(doctor):
	if not frappe.db.exists("Doctor Schedule", {"employee": doctor}):
		schedule = frappe.new_doc("Doctor Schedule")
		schedule.update({
			"doctype": "Doctor Schedule",
			"employee": doctor,
			"schedule": []
		})
		schedule.fill_table()
		schedule.save()

def on_customer_create(doc, method=None):
	if not frappe.db.exists("Medical History", {"customer": doc.name}):
		patient = frappe.new_doc("Medical History")
		patient.update({
			"customer": doc.name
		})
		patient.save()

def on_sales_invoice_submit(doc, method=None):
	if not doc.patient_appointment:
		return

	if doc.outstanding_amount > 0:
		return

	# Check if the sales invoice is linked to a patient appointment
	exists = frappe.db.exists("Patient Appointment", {"invoice": doc.name, "appointment_status": ["!=", "مؤكد"]})
	if exists:
		confirm_appointment(doc)
		return

	action_exists = frappe.db.exists("Appointment Actions", {"invoice": doc.name})
	if action_exists:
		frappe.db.set_value("Appointment Actions", action_exists, "paid", 1)

def confirm_appointment(doc):
	# Queue is assigned at check-in (medic.api.check_in), not on payment.
	pa_doc = frappe.get_doc("Patient Appointment", doc.patient_appointment)
	pa_doc.db_set("appointment_status", "مؤكد")
