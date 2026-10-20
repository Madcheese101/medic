import frappe

from medic.constants import AppointmentStatus


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

def on_customer_before_validate(doc, method=None):
	"""Store locally-typed phone numbers in E.164 so the Phone field validation accepts them."""
	import phonenumbers

	number = (doc.phone_number or "").strip()
	if not number:
		return

	country = frappe.db.get_single_value("Global Defaults", "country")
	region = frappe.db.get_value("Country", country, "code") if country else None
	if not region:
		return

	try:
		parsed = phonenumbers.parse(number, region.upper())
	except phonenumbers.NumberParseException:
		# Not a phone number at all; let the built-in validation reject what was typed.
		return

	doc.phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

def on_customer_create(doc, method=None):
	if not frappe.db.exists("Medical History", {"customer": doc.name}):
		patient = frappe.new_doc("Medical History")
		patient.update({
			"customer": doc.name
		})
		patient.save()

def on_sales_invoice_cancel(doc, method=None):
	if not doc.patient_appointment and not doc.treatment_plan:
		return

	# Check if the sales invoice is linked to a patient appointment
	exists = frappe.db.exists(
		"Patient Appointment", {"invoice": doc.name, "appointment_status": AppointmentStatus.CONFIRMED}
	)
	if exists:
		frappe.db.set_value(
			"Patient Appointment", exists, "appointment_status", AppointmentStatus.UNCONFIRMED
		)
		return

	# action_exists = frappe.db.exists("Appointment Actions", {"invoice": doc.name})
	# if action_exists:
	# 	frappe.db.set_value("Appointment Actions", action_exists, "paid", 0)


def on_test_request_invoice_submit(doc, method=None):
	"""Seed a Test Request's result table from its invoiced Lab Test items on submit."""
	tr_name = frappe.db.get_value("Test Request", {"sales_invoice": doc.name}, "name")
	if not tr_name:
		return

	tr = frappe.get_doc("Test Request", tr_name)
	existing = {r.item for r in tr.result}
	added = False
	for item in doc.items:
		if item.item_code in existing:
			continue
		meta = frappe.db.get_value(
			"Item", item.item_code, ["item_type", "stock_uom", "reference_range"], as_dict=True
		)
		if not meta or meta.item_type != "Lab Test":
			continue
		tr.append(
			"result",
			{"item": item.item_code, "uom": meta.stock_uom, "reference_range": meta.reference_range},
		)
		existing.add(item.item_code)
		added = True

	if added:
		# The cashier who submits the invoice has no write access to Test Request.
		tr.save(ignore_permissions=True)
