"""Doctor availability, appointment booking and lifecycle, and the actions added to an appointment
(extra services, prescriptions, lab tests)."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from medic.billing import (
	NON_DISCOUNTABLE_APPOINTMENT_TYPES,
	add_payments,
	apply_discount,
	base_amount,
	company,
	company_currency,
	invoice_financials,
	pos_pay,
	rounding_slack,
	validated_discount,
)
from medic.constants import ActionType, AppointmentStatus, AppointmentType, label
from medic.medic.page.medic_pos.api.lists import date_range, order_by

# ---------------------------------------------------------------- availability

# JS Date.getDay() convention: Sunday=0 .. Saturday=6.
DAY_INDEX = {
	"Sunday": 0,
	"Monday": 1,
	"Tuesday": 2,
	"Wednesday": 3,
	"Thursday": 4,
	"Friday": 5,
	"Saturday": 6,
}


@frappe.whitelist()
def get_doctor_availability(employee):
	"""Active weekday capacities + future booked counts to drive the date picker."""
	weekday_max = {}
	name = frappe.db.exists("Doctor Schedule", {"employee": employee})
	if name:
		doc = frappe.get_doc("Doctor Schedule", name)
		for row in doc.schedule:
			idx = DAY_INDEX.get(row.day)
			if row.is_active and idx is not None:
				weekday_max[idx] = cint(row.maximum_appointments)

	booked = {}
	rows = frappe.get_all(
		"Patient Appointment",
		filters={
			"employee": employee,
			"appointment_date": [">=", today()],
			"docstatus": ["<", 2],
			# A refund cancels an appointment but leaves it submitted; it no longer takes a slot.
			"appointment_status": ["!=", AppointmentStatus.CANCELLED],
		},
		fields=["appointment_date", "count(name) as n"],
		group_by="appointment_date",
	)
	for r in rows:
		booked[str(r.appointment_date)] = r.n

	return {"weekday_max": weekday_max, "booked": booked, "today": today()}


def validate_appointment_date(employee, appointment_date, ignore=None):
	"""Enforce no-backdate + doctor's active weekday + daily capacity."""
	if getdate(appointment_date) < getdate(today()):
		frappe.throw(_("Cannot book an appointment in the past."))

	name = frappe.db.exists("Doctor Schedule", {"employee": employee})
	if not name:
		frappe.throw(_("This doctor has no availability schedule."))

	doc = frappe.get_doc("Doctor Schedule", name)
	day_name = getdate(appointment_date).strftime("%A")
	row = next((r for r in doc.schedule if r.day == day_name and r.is_active), None)
	if not row:
		frappe.throw(_("The doctor is not available on {0}.").format(day_name))

	filters = {
		"employee": employee,
		"appointment_date": appointment_date,
		"docstatus": ["<", 2],
		"appointment_status": ["!=", AppointmentStatus.CANCELLED],
	}
	if ignore:
		filters["name"] = ["!=", ignore]
	cap = cint(row.maximum_appointments)  # 0 = unlimited
	if cap and frappe.db.count("Patient Appointment", filters) >= cap:
		frappe.throw(_("The doctor is fully booked on {0}.").format(appointment_date))


# ---------------------------------------------------------------- appointments

APPOINTMENT_LIST_FIELDS = (
	"name",
	"appointment_date",
	"appointment_type",
	"customer",
	"customer_name",
	"employee",
	"employee.employee_name as doctor_name",
	"service",
	"service.item_name as service_name",
	"appointment_status",
	"invoice",
	"treatment_plan",
	"queue",
	"docstatus",
)
# The doctor and service names come from joined tables, so the list can't sort on them.
APPOINTMENT_SORTABLE = (
	"name",
	"appointment_date",
	"appointment_type",
	"customer_name",
	"appointment_status",
	"queue",
)


@frappe.whitelist()
def get_appointments(
	customer=None,
	employee=None,
	from_date=None,
	to_date=None,
	appointment_status=None,
	start=0,
	page_length=20,
	sort_by=None,
	sort_order=None,
):
	"""One page of the appointment list, with filters applied on the DB."""
	filters = {}
	if customer:
		filters["customer"] = customer
	if employee:
		filters["employee"] = employee
	if dates := date_range(from_date, to_date):
		filters["appointment_date"] = dates
	if appointment_status:
		filters["appointment_status"] = appointment_status

	rows = frappe.qb.get_query(
		"Patient Appointment",
		fields=list(APPOINTMENT_LIST_FIELDS),
		filters=filters,
		order_by=order_by(sort_by, sort_order, APPOINTMENT_SORTABLE, "appointment_date desc, creation desc"),
		limit=cint(page_length),
		offset=cint(start),
	).run(as_dict=True)
	return {"rows": rows, "total": frappe.db.count("Patient Appointment", filters)}


@frappe.whitelist()
def create_appointment(
	appointment_type,
	customer,
	employee,
	appointment_date,
	service_type,
	service,
	notes=None,
	discount_percentage=None,
):
	validate_appointment_date(employee, appointment_date)
	pct = 0
	if flt(discount_percentage):
		if appointment_type in NON_DISCOUNTABLE_APPOINTMENT_TYPES:
			frappe.throw(
				_("{0} appointments cannot be discounted.").format(
					label(appointment_type, "Patient Appointment")
				)
			)
		pct = validated_discount(discount_percentage)
	doc = frappe.new_doc("Patient Appointment")
	doc.update(
		{
			"naming_series": "APP-.YY.-",
			"appointment_type": appointment_type,
			"customer": customer,
			"employee": employee,
			"appointment_date": appointment_date,
			"service_type": service_type,
			"service": service,
			"notes": notes,
			# Applied to the invoice, which is only created when the appointment is confirmed.
			"discount_percentage": pct,
			# appointment_status is not allow_on_submit, so set it before submitting.
			"appointment_status": AppointmentStatus.PENDING,
		}
	)
	doc.insert()
	doc.submit()
	return doc.name


@frappe.whitelist()
def get_appointment(name):
	doc = frappe.get_doc("Patient Appointment", name)
	data = doc.as_dict()
	data["doctor_name"] = frappe.db.get_value("Employee", doc.employee, "employee_name")
	data["service_name"] = frappe.db.get_value("Item", doc.service, "item_name")
	# Each action row carries its own invoice's totals so the table/pay dialog have amounts.
	currency = company_currency()
	for row in data.get("actions") or []:
		# Resolve the row's Sales Invoice: direct for service actions, via the Test Request for
		# lab actions. Prescription rows are not billable and carry no invoice.
		invoice = None
		if row.get("invoice_type") == "Sales Invoice":
			invoice = row.get("invoice")
		elif row.get("invoice_type") == "Test Request":
			invoice = frappe.db.get_value("Test Request", row.get("invoice"), "sales_invoice")
			# Reflect the linked invoice's payment state on the action row.
			row["paid"] = 1 if invoice and invoice_financials(invoice)["outstanding_amount"] <= 0 else 0
		row["sales_invoice"] = invoice
		fin = invoice_financials(invoice)
		row["grand_total"] = fin["grand_total"]
		row["outstanding_amount"] = fin["outstanding_amount"]
		row["currency"] = currency
	return data


@frappe.whitelist()
def confirm_appointment(name):
	"""Create the draft Sales Invoice for a Pending appointment and mark it Not Confirmed."""
	invoice = frappe.get_doc("Patient Appointment", name).confirm_appointment()
	return {"invoice": invoice, "appointment_status": AppointmentStatus.UNCONFIRMED}


@frappe.whitelist()
def confirm_appointment_invoice(name):
	"""Ensure the appointment has an invoice; return its money snapshot for the pay dialog."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted before confirming."))

	invoice = pa.ensure_invoice()
	si = frappe.get_doc("Sales Invoice", invoice)
	grand = flt(si.grand_total)
	# outstanding_amount is only populated once the invoice is submitted; a draft owes it all.
	outstanding = grand if si.docstatus == 0 else flt(si.outstanding_amount)
	return {
		"invoice": invoice,
		"grand_total": grand,
		"outstanding_amount": outstanding,
		"paid": grand - outstanding,
		"currency": company_currency(),
		"appointment_status": pa.appointment_status,
	}


@frappe.whitelist()
def pay_appointment(name, payments):
	"""Submit the appointment's invoice (if draft) and record one or more payments; confirm when
	fully paid. `payments`: list of {mode_of_payment, amount, reference_no?, reference_date?, exchange_rate?}."""
	payments = frappe.parse_json(payments) or []
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted before paying."))

	invoice = pa.ensure_invoice()
	si = frappe.get_doc("Sales Invoice", invoice)

	# A consultation must be settled in full in one go; partial payments are not allowed.
	if pa.appointment_type == AppointmentType.CONSULTATION:
		# On a draft the outstanding is not yet posted, so gate against the still-owed amount.
		owed = flt(si.grand_total) if si.docstatus == 0 else flt(si.outstanding_amount)
		total_paying = sum(base_amount(p) for p in payments)
		if total_paying + 0.01 < owed:
			frappe.throw(
				_("A {0} appointment must be paid in full.").format(
					label(AppointmentType.CONSULTATION, "Patient Appointment")
				)
			)

	if si.docstatus == 0:
		# Initial payment: capture it inside a cashier POS invoice.
		pos_pay(si, payments)
	else:
		# Top-up on an already-submitted invoice: record as Payment Entries.
		add_payments(invoice, payments)

	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))
	if outstanding <= 0 and pa.appointment_status != AppointmentStatus.CONFIRMED:
		# notify: open appointment lists refresh once this commits.
		pa.db_set("appointment_status", AppointmentStatus.CONFIRMED, notify=True)
	return {
		"invoice": invoice,
		"outstanding_amount": outstanding,
		"appointment_status": AppointmentStatus.CONFIRMED if outstanding <= 0 else pa.appointment_status,
	}


@frappe.whitelist()
def check_in(appointment):
	return frappe.get_doc("Patient Appointment", appointment).check_in()


@frappe.whitelist()
def complete_appointment(name):
	frappe.get_doc("Patient Appointment", name).complete()
	return {"appointment_status": AppointmentStatus.COMPLETED}


@frappe.whitelist()
def save_appointment_notes(name, notes=None):
	# notes is allow_on_submit, so it can change on the submitted appointment.
	doc = frappe.get_doc("Patient Appointment", name)
	doc.notes = notes
	doc.save()
	return doc.name


# ---------------------------------------------------------------- appointment actions


def _open_appointment(name):
	"""The appointment an action is being added to: submitted and not yet completed."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted."))
	if pa.appointment_status == AppointmentStatus.COMPLETED:
		frappe.throw(_("Appointment is already completed."))
	return pa


@frappe.whitelist()
def create_appointment_action(name, service, action_type, discount_percentage=None):
	"""Draft Sales Invoice for an extra service (a different item group than the appointment's),
	recorded as an action on the appointment and paid separately."""
	pa = _open_appointment(name)
	if frappe.db.get_value("Item", service, "item_group") == pa.service_type:
		frappe.throw(_("Choose a service from a different type than the appointment's service."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = pa.customer
	si.company = company()
	# is_action_invoice marks it separate from the appointment's main invoice.
	si.patient_appointment = pa.name
	si.is_action_invoice = 1
	si.append("items", {"item_code": service, "qty": 1})
	if flt(discount_percentage):
		if action_type != ActionType.TREATMENT:
			frappe.throw(
				_("Only {0} actions can be discounted.").format(
					label(ActionType.TREATMENT, "Appointment Actions")
				)
			)
		apply_discount(si, validated_discount(discount_percentage))
	si.insert()  # draft (docstatus 0)

	pa.append(
		"actions",
		{"invoice": si.name, "invoice_type": "Sales Invoice", "action_type": action_type, "paid": 0},
	)
	pa.save()
	return si.name


@frappe.whitelist()
def pay_appointment_action(invoice, payments):
	"""Pay an action invoice IN FULL (submit it if draft), split across one or more payment
	methods, then mark its action row paid. `payments` is a list of
	{mode_of_payment, amount, reference_no?, reference_date?, exchange_rate?}."""
	payments = frappe.parse_json(payments) or []
	si = frappe.get_doc("Sales Invoice", invoice)
	if si.docstatus == 0:
		si.submit()

	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))
	total = sum(base_amount(p) for p in payments)
	if total + 0.01 < outstanding or total > outstanding + rounding_slack(payments):
		frappe.throw(_("Payments must total the full amount ({0}).").format(outstanding))

	# Each method becomes its own Payment Entry allocated to the invoice.
	add_payments(invoice, payments)

	row = frappe.db.exists("Appointment Actions", {"invoice": invoice})
	if row:
		frappe.db.set_value("Appointment Actions", row, "paid", 1)

	return {"invoice": invoice, "outstanding_amount": 0.0}


def _set_prescription_items(doc, items):
	doc.set("items", [])
	for row in items:
		doc.append(
			"items",
			{
				"item": row.get("item"),
				"route": row.get("route"),
				"times": cint(row.get("times")),
				"per": row.get("per"),
				"for": cint(row.get("for")),
			},
		)


@frappe.whitelist()
def create_prescription(appointment, items):
	"""Prescription for the appointment's patient, recorded as a non-billable action row.
	`items`: list of {item, route, times, per, for}."""
	items = frappe.parse_json(items) or []
	if not items:
		frappe.throw(_("Add at least one item."))

	pa = _open_appointment(appointment)
	doc = frappe.new_doc("Prescription")
	doc.posting_date = today()
	doc.patient = pa.customer
	doc.appointment = pa.name
	_set_prescription_items(doc, items)
	doc.insert()

	# Nothing to collect on a prescription, so the row is born paid.
	pa.append(
		"actions",
		{
			"invoice": doc.name,
			"invoice_type": "Prescription",
			"action_type": ActionType.PRESCRIPTION,
			"paid": 1,
		},
	)
	pa.save()
	return doc.name


@frappe.whitelist()
def get_prescription(name):
	return frappe.get_doc("Prescription", name).as_dict()


@frappe.whitelist()
def update_prescription(name, items):
	"""Replace a prescription's items. Locked once the pharmacy has invoiced it."""
	items = frappe.parse_json(items) or []
	if not items:
		frappe.throw(_("Add at least one item."))

	doc = frappe.get_doc("Prescription", name)
	if doc.invoice_created:
		frappe.throw(_("This prescription has been invoiced and can no longer be edited."))

	_set_prescription_items(doc, items)
	doc.save()
	return doc.name


@frappe.whitelist()
def create_appointment_test_request(appointment, items):
	"""Test Request for the appointment's patient, recorded as an action row like a prescription."""
	items = frappe.parse_json(items) or []
	items = [i for i in items if i]
	if not items:
		frappe.throw(_("Add at least one test."))

	pa = _open_appointment(appointment)
	tr = frappe.new_doc("Test Request")
	tr.posting_date = today()
	tr.patient = pa.customer
	tr.appointment = pa.name
	for code in items:
		tr.append("items", {"item": code})
	tr.insert()
	tr.submit()

	# Billable, so the row starts unpaid; its paid flag tracks the test's invoice.
	pa.append(
		"actions",
		{"invoice": tr.name, "invoice_type": "Test Request", "action_type": ActionType.LAB_TEST, "paid": 0},
	)
	pa.save()
	return tr.name
