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
	if not doc.patient_appointment and not doc.treatment_plan:
		return

	if doc.outstanding_amount > 0:
		return

	if doc.is_action_invoice:
		doctype = "Appointment Actions"
		filters = {"invoice": doc.name}
		field = "paid"
		value = 1
	else:
		doctype = "Patient Appointment"
		filters = {"invoice": doc.name, "appointment_status": ["!=", "مؤكد"]}
		field = "appointment_status"
		value = "مؤكد"

	exists = frappe.db.exists(doctype, filters)
	if exists:
		frappe.db.set_value(doctype, exists, field, value)
		return

def on_sales_invoice_cancel(doc, method=None):
	if not doc.patient_appointment and not doc.treatment_plan:
		return

	# Check if the sales invoice is linked to a patient appointment
	exists = frappe.db.exists("Patient Appointment", {"invoice": doc.name, "appointment_status": "مؤكد"})
	if exists:
		frappe.db.set_value("Patient Appointment", exists, "appointment_status", "غير مؤكد")
		return

	# action_exists = frappe.db.exists("Appointment Actions", {"invoice": doc.name})
	# if action_exists:
	# 	frappe.db.set_value("Appointment Actions", action_exists, "paid", 0)
