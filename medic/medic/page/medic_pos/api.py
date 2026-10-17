import frappe
from frappe import _
from frappe.desk.search import build_for_autosuggest, sanitize_searchfield, search_widget
from frappe.query_builder import Order
from frappe.utils import cint, flt, getdate, today

PATIENT_FIELDS = ("customer_name", "date_of_birth", "phone_number", "gender", "blood_type")


def _phone_like(mobile):
	"""Numbers are stored in E.164 (+218…), so drop the leading 0 of a locally-typed one."""
	return ["like", f"%{mobile.strip().lstrip('0')}%"]


def _company():
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


def _linked_employee():
	return frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user}, ["name", "employee_name"], as_dict=True
	)


def _default_pos_profile():
	"""Logged-in user's default POS Profile as a full doc, or None if none is configured."""
	from erpnext.stock.get_item_details import get_pos_profile

	company = _company()
	if not company:
		return None

	profile = get_pos_profile(company, user=frappe.session.user)
	if not profile:
		return None

	return frappe.get_doc("POS Profile", profile.get("name")).as_dict()


@frappe.whitelist()
def load_defaults():
	return {
		"pos_profile": _default_pos_profile(),
		"roles": frappe.get_roles(),
		"employee": _linked_employee(),
	}


# ---------------------------------------------------------------- patients


@frappe.whitelist()
def get_patients(customer_name=None, mobile=None, file_no=None, limit=100):
	"""Patient list with the filters applied on the DB, not in the browser."""
	filters = {}
	if customer_name:
		filters["customer_name"] = ["like", f"%{customer_name}%"]
	if mobile:
		filters["phone_number"] = _phone_like(mobile)
	if file_no:
		filters["name"] = ["like", f"%{file_no}%"]

	return frappe.qb.get_query(
		"Customer",
		fields=["name", *PATIENT_FIELDS],
		filters=filters,
		order_by="creation desc",
		limit=limit,
	).run(as_dict=True)


@frappe.whitelist()
def create_patient(customer_name, date_of_birth, phone_number, gender, blood_type=None):
	doc = frappe.new_doc("Customer")
	doc.update(
		{
			"customer_group": "Individual",
			"customer_name": customer_name,
			"date_of_birth": date_of_birth or None,
			"phone_number": phone_number,
			"gender": gender,
			"blood_type": blood_type,
		}
	)
	doc.insert()
	return doc.name


def _customer_balance(customer):
	"""Outstanding in company currency. Positive => the patient owes the clinic."""
	from erpnext.accounts.utils import get_balance_on

	company = _company()
	balance = get_balance_on(
		party_type="Customer", party=customer, company=company, date=today()
	)
	currency = frappe.db.get_value("Company", company, "default_currency") if company else None
	return {"balance": balance, "currency": currency}


def _medical_history(customer):
	name = frappe.db.exists("Medical History", {"customer": customer})
	if not name:
		return None

	doc = frappe.get_doc("Medical History", name)
	# Illness is named by illness_name, so the link value is already readable.
	return {
		"name": doc.name,
		"notes": doc.notes,
		"medical_history": [row.illness for row in doc.medical_history if row.illness],
		"skin_illness": [row.illness for row in doc.skin_illness if row.illness],
	}


@frappe.whitelist()
def get_patient(name):
	customer = frappe.get_doc("Customer", name)
	return {
		"customer": {"name": customer.name, **{f: customer.get(f) for f in PATIENT_FIELDS}},
		**_customer_balance(name),
		"medical_history": _medical_history(name),
	}


@frappe.whitelist()
def save_patient(name, customer_name, date_of_birth, phone_number, gender, blood_type=None):
	doc = frappe.get_doc("Customer", name)
	doc.update(
		{
			"customer_name": customer_name,
			"date_of_birth": date_of_birth or None,
			"phone_number": phone_number,
			"gender": gender,
			"blood_type": blood_type,
		}
	)
	doc.save()
	return doc.name


@frappe.whitelist()
def save_medical_history(customer, notes=None, medical_history=None, skin_illness=None):
	name = frappe.db.exists("Medical History", {"customer": customer})
	if name:
		doc = frappe.get_doc("Medical History", name)
	else:
		doc = frappe.new_doc("Medical History")
		doc.customer = customer

	doc.notes = notes
	for fieldname, rows in (("medical_history", medical_history), ("skin_illness", skin_illness)):
		doc.set(fieldname, [])
		for row in frappe.parse_json(rows) or []:
			illness = row.get("illness") if isinstance(row, dict) else row
			if illness:
				doc.append(fieldname, {"illness": illness})

	doc.save()
	return doc.name


# ---------------------------------------------------------------- schedule


@frappe.whitelist()
def get_my_schedule(employee):
	"""Doctor Schedule of the employee linked to the logged-in user."""
	employee = frappe.parse_json(employee)
	if not employee:
		return None

	name = frappe.db.exists("Doctor Schedule", {"employee": employee["name"]})
	if not name:
		return None

	return frappe.get_doc("Doctor Schedule", name).as_dict()


@frappe.whitelist()
def save_schedule(rows, employee):
	employee = frappe.parse_json(employee)
	if not employee:
		frappe.throw(_("No Employee is linked to your user."))

	name = frappe.db.exists("Doctor Schedule", {"employee": employee["name"]})
	if not name:
		frappe.throw(_("No Doctor Schedule found for {0}.").format(employee["employee_name"]))

	doc = frappe.get_doc("Doctor Schedule", name)
	incoming = {row.get("day"): row for row in frappe.parse_json(rows) or []}
	for row in doc.schedule:
		update = incoming.get(row.day)
		if update:
			row.is_active = update.get("is_active") or 0
			row.from_time = update.get("from_time")
			row.to_time = update.get("to_time")
			row.maximum_appointments = update.get("maximum_appointments")

	doc.save()
	return doc.name


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
		},
		fields=["appointment_date", "count(name) as n"],
		group_by="appointment_date",
	)
	for r in rows:
		booked[str(r.appointment_date)] = r.n

	return {"weekday_max": weekday_max, "booked": booked, "today": today()}


def _validate_appointment_date(employee, appointment_date, ignore=None):
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
	}
	if ignore:
		filters["name"] = ["!=", ignore]
	cap = cint(row.maximum_appointments)  # 0 = unlimited
	if cap and frappe.db.count("Patient Appointment", filters) >= cap:
		frappe.throw(_("The doctor is fully booked on {0}.").format(appointment_date))


# ---------------------------------------------------------------- profile


@frappe.whitelist()
def get_my_profile():
	user = frappe.get_doc("User", frappe.session.user)
	return {
		"name": user.name,
		"full_name": user.full_name,
		"language": user.language,
		"user_image": user.user_image,
		"languages": frappe.get_all("Language", fields=["name", "language_name"], order_by="name"),
	}


@frappe.whitelist()
def save_profile(language=None, user_image=None, new_password=None):
	user = frappe.get_doc("User", frappe.session.user)
	user.language = language
	if user_image is not None:
		user.user_image = user_image
	if new_password:
		user.new_password = new_password

	user.save(ignore_permissions=True)
	return {"language": user.language, "user_image": user.user_image}


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


@frappe.whitelist()
def get_appointments(
	customer=None, employee=None, appointment_date=None, appointment_status=None, limit=100
):
	"""Appointment list with filters applied on the DB."""
	filters = {}
	if customer:
		filters["customer"] = customer
	if employee:
		filters["employee"] = employee
	if appointment_date:
		filters["appointment_date"] = appointment_date
	if appointment_status:
		filters["appointment_status"] = appointment_status

	return frappe.qb.get_query(
		"Patient Appointment",
		fields=list(APPOINTMENT_LIST_FIELDS),
		filters=filters,
		order_by="appointment_date desc, creation desc",
		limit=limit,
	).run(as_dict=True)


@frappe.whitelist()
def create_appointment(
	appointment_type, customer, employee, appointment_date, service_type, service, notes=None,
	discount_percentage=None,
):
	_validate_appointment_date(employee, appointment_date)
	pct = 0
	if flt(discount_percentage):
		if appointment_type in NON_DISCOUNTABLE_APPOINTMENT_TYPES:
			frappe.throw(_("{0} appointments cannot be discounted.").format(appointment_type))
		pct = _validated_discount(discount_percentage)
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
			"appointment_status": "انتظار",
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
	currency = _company_currency()
	for row in data.get("actions") or []:
		# Resolve the row's Sales Invoice: direct for service actions, via the Test Request for
		# lab actions. Prescription rows are not billable and carry no invoice.
		invoice = None
		if row.get("invoice_type") == "Sales Invoice":
			invoice = row.get("invoice")
		elif row.get("invoice_type") == "Test Request":
			invoice = frappe.db.get_value("Test Request", row.get("invoice"), "sales_invoice")
			# Reflect the linked invoice's payment state on the action row.
			row["paid"] = 1 if invoice and _invoice_financials(invoice)["outstanding_amount"] <= 0 else 0
		fin = _invoice_financials(invoice)
		row["grand_total"] = fin["grand_total"]
		row["outstanding_amount"] = fin["outstanding_amount"]
		row["currency"] = currency
	return data


def _company_currency():
	company = _company()
	return frappe.db.get_value("Company", company, "default_currency") if company else None


def _cashier_profile():
	"""The Cashier POS Profile that front-desk collections (appointments, plan deposits) post under."""
	name = frappe.db.get_single_value("Clinic Setup", "cashier_pos_profile")
	if not name:
		frappe.throw(_("Set the Cashier POS Profile in Clinic Setup."))
	return frappe.get_cached_doc("POS Profile", name)


def _mode_account(mode_of_payment, company=None):
	return frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": company or _company()},
		"default_account",
	)


def mode_currency(mode_of_payment, company=None):
	"""Currency of the mode's account (e.g. a USD cash box); None when the mode has no account."""
	from erpnext.accounts.utils import get_account_currency

	account = _mode_account(mode_of_payment, company)
	return get_account_currency(account) if account else None


def _is_foreign(p):
	currency = mode_currency(p["mode_of_payment"])
	return bool(currency) and currency != _company_currency()


def _base_amount(p):
	"""A payment row's value in company currency. Foreign rows carry the cashier's rate of the day."""
	if not _is_foreign(p):
		return flt(p.get("amount"))
	if flt(p.get("exchange_rate")) <= 0:
		frappe.throw(_("Enter the exchange rate for {0}.").format(p["mode_of_payment"]))
	return flt(flt(p.get("amount")) * flt(p.get("exchange_rate")), 2)


def _rounding_slack(payments):
	"""Foreign cash is counted in its own cents, so its company-currency value may overshoot a
	little; allow half a foreign cent per foreign row (add_payment absorbs it into the rate)."""
	return 0.01 + sum(flt(p.get("exchange_rate")) * 0.005 for p in payments if _is_foreign(p))


def _pos_pay(si, payments):
	"""Turn a (new or draft) Sales Invoice into a cashier POS invoice paid by `payments`, then submit.
	The payment lands on the invoice itself, so the cashier's POS Profile owns the collection.
	POS payment rows only hold company currency, so foreign-currency rows become Payment Entries."""
	local = [p for p in payments if not _is_foreign(p)]
	foreign = [p for p in payments if _is_foreign(p)]
	if local:
		profile = _cashier_profile()
		si.is_pos = 1
		si.pos_profile = profile.name
		for p in local:
			si.append("payments", {"mode_of_payment": p["mode_of_payment"], "amount": flt(p["amount"])})
	si.save()  # inserts when new; persists is_pos/pos_profile/payments on a draft
	si.submit()
	for p in foreign:
		add_payment(
			si.name, p.get("amount"), p.get("mode_of_payment"),
			p.get("reference_no"), p.get("reference_date"), p.get("exchange_rate"),
		)
	return si.name


def _ensure_appointment_invoice(pa):
	"""Return the appointment's Sales Invoice, creating a draft one if missing. Idempotent."""
	if pa.invoice:
		return pa.invoice

	si = frappe.new_doc("Sales Invoice")
	si.customer = pa.customer
	si.company = _company()
	# Custom Link field on Sales Invoice; the after_submit event uses it to reach the PA.
	si.patient_appointment = pa.name
	si.append("items", {"item_code": pa.service, "qty": 1})
	if flt(pa.get("discount_percentage")):
		_apply_discount(si, flt(pa.discount_percentage))
	si.insert()  # draft (docstatus 0)

	# invoice / appointment_status are read-only on a submitted doc; db_set bypasses that.
	pa.db_set("invoice", si.name)
	if pa.appointment_status == "انتظار":
		pa.db_set("appointment_status", "غير مؤكد")
	return si.name


@frappe.whitelist()
def confirm_appointment(name):
	"""Create the draft Sales Invoice for a Pending appointment and mark it Not Confirmed."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted before confirming."))
	if pa.appointment_status != "انتظار":
		frappe.throw(_("Appointment is already confirmed."))

	invoice = _ensure_appointment_invoice(pa)
	return {"invoice": invoice, "appointment_status": "غير مؤكد"}


@frappe.whitelist()
def confirm_appointment_invoice(name):
	"""Ensure the appointment has an invoice; return its money snapshot for the pay dialog."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted before confirming."))

	invoice = _ensure_appointment_invoice(pa)
	si = frappe.get_doc("Sales Invoice", invoice)
	grand = flt(si.grand_total)
	# outstanding_amount is only populated once the invoice is submitted; a draft owes it all.
	outstanding = grand if si.docstatus == 0 else flt(si.outstanding_amount)
	return {
		"invoice": invoice,
		"grand_total": grand,
		"outstanding_amount": outstanding,
		"paid": grand - outstanding,
		"currency": _company_currency(),
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

	invoice = _ensure_appointment_invoice(pa)
	si = frappe.get_doc("Sales Invoice", invoice)

	# A كشف must be settled in full in one go; partial payments are not allowed.
	if pa.appointment_type == "كشف":
		# On a draft the outstanding is not yet posted, so gate against the still-owed amount.
		owed = flt(si.grand_total) if si.docstatus == 0 else flt(si.outstanding_amount)
		total_paying = sum(_base_amount(p) for p in payments)
		if total_paying + 0.01 < owed:
			frappe.throw(_("A كشف appointment must be paid in full."))

	if si.docstatus == 0:
		# Initial payment: capture it inside a cashier POS invoice.
		_pos_pay(si, payments)
	else:
		# Top-up on an already-submitted invoice: record as Payment Entries.
		for p in payments:
			add_payment(
				invoice, p.get("amount"), p.get("mode_of_payment"),
				p.get("reference_no"), p.get("reference_date"), p.get("exchange_rate"),
			)

	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))
	if outstanding <= 0 and pa.appointment_status != "مؤكد":
		pa.db_set("appointment_status", "مؤكد")
	return {
		"invoice": invoice,
		"outstanding_amount": outstanding,
		"appointment_status": "مؤكد" if outstanding <= 0 else pa.appointment_status,
	}


@frappe.whitelist()
def complete_appointment(name):
	"""Mark a checked-in appointment as completed (مكتمل)."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted."))
	if not pa.queue:
		frappe.throw(_("Appointment must be checked in before completing."))
	# Count the treatment-plan session toward the plan on completion (once).
	if pa.treatment_plan and pa.appointment_status != "مكتمل":
		plan = frappe.get_doc("Treatment Plan", pa.treatment_plan)
		plan.db_set("completed_sessions", cint(plan.completed_sessions) + 1)
	pa.db_set("appointment_status", "مكتمل")
	return {"appointment_status": "مكتمل"}


@frappe.whitelist()
def create_appointment_action(name, service, action_type, discount_percentage=None):
	"""Draft Sales Invoice for an extra service (a different item group than the appointment's),
	recorded as an action on the appointment and paid separately."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted."))
	if pa.appointment_status == "مكتمل":
		frappe.throw(_("Appointment is already completed."))

	if frappe.db.get_value("Item", service, "item_group") == pa.service_type:
		frappe.throw(_("Choose a service from a different type than the appointment's service."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = pa.customer
	si.company = _company()
	# Reaches the PA via the events hook; is_action_invoice marks it separate from the main one.
	si.patient_appointment = pa.name
	si.is_action_invoice = 1
	si.append("items", {"item_code": service, "qty": 1})
	if flt(discount_percentage):
		if action_type != "علاج":
			frappe.throw(_("Only علاج actions can be discounted."))
		_apply_discount(si, _validated_discount(discount_percentage))
	si.insert()  # draft (docstatus 0)

	pa.append(
		"actions",
		{"invoice": si.name, "invoice_type": "Sales Invoice", "action_type": action_type, "paid": 0},
	)
	pa.save()
	return si.name


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

	pa = frappe.get_doc("Patient Appointment", appointment)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted."))
	if pa.appointment_status == "مكتمل":
		frappe.throw(_("Appointment is already completed."))

	doc = frappe.new_doc("Prescription")
	doc.posting_date = today()
	doc.patient = pa.customer
	doc.appointment = pa.name
	_set_prescription_items(doc, items)
	doc.insert()

	# Nothing to collect on a prescription, so the row is born paid.
	pa.append(
		"actions",
		{"invoice": doc.name, "invoice_type": "Prescription", "action_type": "وصفة طبية", "paid": 1},
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
def pay_appointment_action(invoice, payments):
	"""Pay an action invoice IN FULL (submit it if draft), split across one or more payment
	methods, then mark its action row paid. `payments` is a list of
	{mode_of_payment, amount, reference_no?, reference_date?, exchange_rate?}."""
	payments = frappe.parse_json(payments) or []
	si = frappe.get_doc("Sales Invoice", invoice)
	if si.docstatus == 0:
		si.submit()

	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))
	total = sum(_base_amount(p) for p in payments)
	if total + 0.01 < outstanding or total > outstanding + _rounding_slack(payments):
		frappe.throw(_("Payments must total the full amount ({0}).").format(outstanding))

	# Each method becomes its own Payment Entry allocated to the invoice.
	for p in payments:
		add_payment(
			invoice, p.get("amount"), p.get("mode_of_payment"),
			p.get("reference_no"), p.get("reference_date"), p.get("exchange_rate"),
		)

	# We submitted it unpaid, so the events hook's fully-paid branch was skipped; flip it here.
	row = frappe.db.exists("Appointment Actions", {"invoice": invoice})
	if row:
		frappe.db.set_value("Appointment Actions", row, "paid", 1)

	return {"invoice": invoice, "outstanding_amount": 0.0}


@frappe.whitelist()
def save_appointment_notes(name, notes=None):
	# notes is allow_on_submit, so it can change on the submitted appointment.
	doc = frappe.get_doc("Patient Appointment", name)
	doc.notes = notes
	doc.save()
	return doc.name


# ---------------------------------------------------------------- treatment plans

DEPOSIT_PCT = 0.2


def _invoice_financials(invoice):
	"""Money snapshot for a plan's Sales Invoice. No invoice => nothing billed or paid yet."""
	if not invoice:
		return {"grand_total": 0.0, "paid": 0.0, "outstanding_amount": 0.0, "paid_pct": 0.0}
	si = frappe.db.get_value(
		"Sales Invoice", invoice, ["grand_total", "outstanding_amount"], as_dict=True
	)
	grand = flt(si.grand_total)
	outstanding = flt(si.outstanding_amount)
	paid = grand - outstanding
	return {
		"grand_total": grand,
		"paid": paid,
		"outstanding_amount": outstanding,
		"paid_pct": (paid / grand) if grand else 1.0,
	}


# Shared by the list endpoints. `invoice` is a plain Data field (not a Link), so it can't
# be auto-joined via get_query's dotted fetch — build the joins explicitly instead.
def _treatment_plans_query(filters, order_by_creation=False, limit=None):
	tp = frappe.qb.DocType("Treatment Plan")
	cust = frappe.qb.DocType("Customer")
	emp = frappe.qb.DocType("Employee")
	item = frappe.qb.DocType("Item")
	si = frappe.qb.DocType("Sales Invoice")

	q = (
		frappe.qb.from_(tp)
		.left_join(cust).on(cust.name == tp.customer)
		.left_join(emp).on(emp.name == tp.employee)
		.left_join(item).on(item.name == tp.service)
		.left_join(si).on(si.name == tp.invoice)
		.select(
			tp.name, tp.status, tp.customer, cust.customer_name.as_("customer_name"),
			tp.employee, emp.employee_name.as_("doctor_name"),
			tp.service, item.item_name.as_("service_name"),
			tp.total_sessions, tp.completed_sessions, tp.invoice, tp.discount_percentage,
			si.grand_total.as_("grand_total"), si.outstanding_amount.as_("outstanding_amount"),
		)
	)
	for field, value in filters.items():
		q = q.where(tp[field] == value)
	if order_by_creation:
		q = q.orderby(tp.creation, order=Order.desc)
	if limit:
		q = q.limit(limit)
	return q


def _apply_financials(row):
	"""Derive paid/paid_pct from the joined invoice totals. No invoice => NULLs => zeros."""
	grand = flt(row.get("grand_total"))
	outstanding = flt(row.get("outstanding_amount"))
	row["grand_total"] = grand
	row["outstanding_amount"] = outstanding
	row["paid"] = grand - outstanding
	row["paid_pct"] = ((grand - outstanding) / grand) if grand else 0.0
	return row


def _session_gate_ok(plan, is_last):
	"""Two waivers live here: per-plan skip_deposit and per-customer allow_credit."""
	# No invoice means no payment can have been made, so the gate stays shut.
	if not plan.invoice:
		return False
	fin = _invoice_financials(plan.invoice)
	if is_last:
		if fin["outstanding_amount"] <= 0:
			return True
		return bool(frappe.db.get_value("Customer", plan.customer, "allow_credit"))
	if plan.skip_deposit:
		return True
	return fin["paid_pct"] >= DEPOSIT_PCT


DISCOUNT_ROLES = ("Doctor", "Cashier")


def _validated_discount(discount_percentage):
	"""Doctors and cashiers may discount up to Clinic Setup's cap; an unset cap allows none."""
	if not set(DISCOUNT_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("Only doctors and cashiers can add a discount."), frappe.PermissionError)
	pct = flt(discount_percentage)
	max_pct = flt(frappe.db.get_single_value("Clinic Setup", "doctor_max_discount_percentage"))
	if pct < 0 or pct > max_pct:
		frappe.throw(_("Discount must be between 0% and {0}%.").format(max_pct))
	return pct


def _apply_discount(si, pct):
	si.apply_discount_on = "Grand Total"
	si.additional_discount_percentage = pct
	# Recomputed from the percentage; reset so clearing the percentage clears the amount too.
	si.discount_amount = 0


NON_DISCOUNTABLE_APPOINTMENT_TYPES = ("كشف", "مراجعة", "متابعة دورية")


def _is_non_discountable_invoice(si):
	"""The appointment's own invoice for a كشف, مراجعة or متابعة دورية (its action invoices are separate services)."""
	return (
		bool(si.get("patient_appointment"))
		and not si.get("is_action_invoice")
		and frappe.db.get_value("Patient Appointment", si.patient_appointment, "appointment_type")
		in NON_DISCOUNTABLE_APPOINTMENT_TYPES
	)


@frappe.whitelist()
def set_invoice_discount(invoice, discount_percentage):
	"""Discount a draft Sales Invoice. Once submitted, its total is final."""
	pct = _validated_discount(discount_percentage)
	si = frappe.get_doc("Sales Invoice", invoice)
	if si.docstatus != 0:
		frappe.throw(_("A discount can only be added before the invoice is submitted."))
	if _is_non_discountable_invoice(si):
		frappe.throw(_("كشف, مراجعة and متابعة دورية appointments cannot be discounted."))
	_apply_discount(si, pct)
	si.save()
	return {"grand_total": si.grand_total, "discount_percentage": pct}


@frappe.whitelist()
def set_treatment_plan_discount(name, discount_percentage):
	"""The plan's invoice is submitted as soon as it is created, so its discount is set on the
	plan beforehand and applied when the invoice is made."""
	pct = _validated_discount(discount_percentage)
	plan = frappe.get_doc("Treatment Plan", name)
	if plan.invoice:
		frappe.throw(_("A discount can only be added before the plan is invoiced."))
	plan.db_set("discount_percentage", pct)
	return pct


@frappe.whitelist()
def create_treatment_plan(customer, employee, service, total_sessions, notes=None, discount_percentage=None):
	total_sessions = cint(total_sessions)
	if total_sessions < 1:
		frappe.throw(_("Total sessions must be at least 1."))
	pct = _validated_discount(discount_percentage) if flt(discount_percentage) else 0

	plan = frappe.new_doc("Treatment Plan")
	plan.update(
		{
			# Stays Pending until its invoice is created, which activates it.
			"status": "Pending",
			"customer": customer,
			"employee": employee,
			"service": service,
			"total_sessions": total_sessions,
			"notes": notes,
			"discount_percentage": pct,
		}
	)
	plan.insert()
	plan.submit()
	return plan.name


@frappe.whitelist()
def create_treatment_plan_invoice(name, payments=None):
	"""Create the plan's Sales Invoice on demand; one invoice carries the whole plan.
	With `payments`, the initial deposit is collected on a cashier POS invoice."""
	plan = frappe.get_doc("Treatment Plan", name)
	if plan.invoice:
		frappe.throw(_("This plan already has an invoice."))
	payments = frappe.parse_json(payments) or []

	si = frappe.new_doc("Sales Invoice")
	si.customer = plan.customer
	si.company = _company()
	# Custom Link field on Sales Invoice recording which plan this invoice belongs to.
	si.treatment_plan = plan.name
	si.append("items", {"item_code": plan.service, "qty": plan.total_sessions})
	if flt(plan.discount_percentage):
		_apply_discount(si, flt(plan.discount_percentage))

	if payments:
		_pos_pay(si, payments)  # cashier POS invoice carrying the initial deposit
	else:
		si.insert()
		si.submit()

	plan.db_set("invoice", si.name)
	if plan.status == "Pending":
		plan.db_set("status", "Active")
	return si.name


@frappe.whitelist()
def add_treatment_sessions(name, sessions):
	"""Raise a plan's session count. Once the plan is invoiced the extra sessions are free:
	the invoice is not touched, so its total is spread over more sessions."""
	sessions = cint(sessions)
	if sessions < 1:
		frappe.throw(_("Sessions to add must be at least 1."))
	plan = frappe.get_doc("Treatment Plan", name)
	if plan.docstatus != 1 or plan.status not in ("Pending", "Active"):
		frappe.throw(_("Sessions can only be added to a pending or active plan."))
	# total_sessions is not allow-on-submit; db_set bypasses that, as for the other plan counters.
	plan.db_set("total_sessions", cint(plan.total_sessions) + sessions)
	return plan.total_sessions


def _estimated_total(service, total_sessions, discount_percentage=0):
	"""Plan price before its invoice exists, so the deposit dialog has a target total.
	Priced off the cashier POS Profile's price list, falling back to the item's standard rate."""
	price_list = None
	profile = frappe.db.get_single_value("Clinic Setup", "cashier_pos_profile")
	if profile:
		price_list = frappe.db.get_value("POS Profile", profile, "selling_price_list")
	rate = None
	if price_list:
		rate = frappe.db.get_value(
			"Item Price", {"item_code": service, "price_list": price_list, "selling": 1}, "price_list_rate"
		)
	if not rate:
		rate = frappe.db.get_value("Item", service, "standard_rate")
	return flt(flt(rate) * cint(total_sessions) * (1 - flt(discount_percentage) / 100), 2)


def _plan_dict(plan):
	data = plan.as_dict() if hasattr(plan, "as_dict") else dict(plan)
	data["service_name"] = frappe.db.get_value("Item", data.get("service"), "item_name")
	data["customer_name"] = frappe.db.get_value("Customer", data.get("customer"), "customer_name")
	data["doctor_name"] = frappe.db.get_value("Employee", data.get("employee"), "employee_name")
	data.update(_invoice_financials(data.get("invoice")))
	# Target for the "create invoice + deposit" dialog when there is no invoice yet.
	data["estimated_total"] = data.get("grand_total") or _estimated_total(
		data.get("service"), data.get("total_sessions"), data.get("discount_percentage")
	)
	company = _company()
	data["currency"] = frappe.db.get_value("Company", company, "default_currency") if company else None
	return data


@frappe.whitelist()
def get_treatment_plans(customer):
	currency = _company_currency()
	rows = _treatment_plans_query(
		{"customer": customer, "docstatus": 1}, order_by_creation=True
	).run(as_dict=True)
	for r in rows:
		_apply_financials(r)
		r["currency"] = currency
	return rows


@frappe.whitelist()
def get_active_treatment_plans(customer=None):
	filters = {"status": "Active", "docstatus": 1}
	if customer:
		filters["customer"] = customer

	rows = _treatment_plans_query(filters).run(as_dict=True)
	out = []
	for r in rows:
		if cint(r.get("completed_sessions")) >= cint(r.get("total_sessions")):
			continue  # no sessions left to book
		_apply_financials(r)
		out.append(r)
	return out


@frappe.whitelist()
def list_treatment_plans(customer=None, employee=None, status=None, limit=100):
	"""Standalone Treatments view list, filters applied on the DB."""
	filters = {"docstatus": 1}
	if customer:
		filters["customer"] = customer
	if employee:
		filters["employee"] = employee
	if status:
		filters["status"] = status

	rows = _treatment_plans_query(filters, order_by_creation=True, limit=limit).run(as_dict=True)
	for r in rows:
		_apply_financials(r)
		# Deposit target for plans that have no invoice yet.
		r["estimated_total"] = r.get("grand_total") or _estimated_total(
			r.get("service"), r.get("total_sessions"), r.get("discount_percentage")
		)
	return rows


@frappe.whitelist()
def get_treatment_plan(name):
	plan = frappe.get_doc("Treatment Plan", name)
	data = _plan_dict(plan)
	data["sessions"] = frappe.get_all(
		"Patient Appointment",
		filters={"treatment_plan": name},  # Data match on the plan name
		fields=["name", "appointment_date", "session_no", "appointment_status", "queue", "docstatus"],
		order_by="session_no asc",
	)
	return data


@frappe.whitelist()
def get_payment_modes():
	"""Enabled Modes of Payment with their type, so the dialog knows when to require a reference,
	and their account currency, so it knows when to ask for an exchange rate."""
	modes = frappe.get_all(
		"Mode of Payment", filters={"enabled": 1}, fields=["name", "type"], order_by="name"
	)
	for m in modes:
		m["currency"] = mode_currency(m["name"])
	return modes


@frappe.whitelist()
def add_payment(invoice, amount, mode_of_payment, reference_no=None, reference_date=None, exchange_rate=None):
	"""`amount` is in the mode's account currency; a foreign one is converted at `exchange_rate`."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	from erpnext.accounts.utils import get_account_currency

	company = frappe.db.get_value("Sales Invoice", invoice, "company")
	account = _mode_account(mode_of_payment, company)
	account_currency = get_account_currency(account) if account else None
	foreign = bool(account_currency) and account_currency != frappe.get_cached_value(
		"Company", company, "default_currency"
	)

	amount = flt(amount)
	party_amount = amount
	if foreign:
		rate = flt(exchange_rate)
		if rate <= 0:
			frappe.throw(_("Enter the exchange rate for {0}.").format(mode_of_payment))
		party_amount = flt(amount * rate, 2)
		# A sub-cent overshoot from rounding the foreign amount is folded into the rate rather
		# than left on the patient's account as a tiny advance.
		outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))
		if outstanding < party_amount <= outstanding + rate * 0.005 + 0.01:
			party_amount = outstanding
			rate = party_amount / amount

	pe = get_payment_entry("Sales Invoice", invoice, party_amount=party_amount)
	pe.mode_of_payment = mode_of_payment
	# get_payment_entry defaults paid_to to the company account, which may be a Bank type and
	# would then demand a reference. Use the mode's own account so a Cash mode stays Cash.
	if account:
		pe.paid_to = account
	if foreign:
		# Debtor is credited in company currency; the cash box receives the foreign amount.
		pe.paid_to_account_currency = account_currency
		pe.target_exchange_rate = rate
		pe.received_amount = amount
	# Bank-type modes require a reference; the dialog collects it for those.
	if reference_no:
		pe.reference_no = reference_no
	if reference_date:
		pe.reference_date = reference_date
	pe.insert()
	pe.submit()
	_update_appointment_status(invoice)
	return pe.name


@frappe.whitelist()
def record_payments(invoice, payments):
	"""Record one or more payments against an already-submitted Sales Invoice (partial allowed).
	`payments`: list of {mode_of_payment, amount, reference_no?, reference_date?, exchange_rate?}."""
	payments = frappe.parse_json(payments) or []
	for p in payments:
		add_payment(
			invoice, p.get("amount"), p.get("mode_of_payment"),
			p.get("reference_no"), p.get("reference_date"), p.get("exchange_rate"),
		)
	return {"invoice": invoice, "outstanding_amount": flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))}


def _update_appointment_status(sales_invoice):
	"""Update the appointment status based on the invoice's payment status."""
	pa_name, outstanding = frappe.db.get_value("Sales Invoice", sales_invoice, "patient_appointment, outstanding_amount")
	if not pa_name:
		return
	try:
		pa = frappe.get_doc("Patient Appointment", pa_name)
	except frappe.DoesNotExistError:
		return
	if pa.appointment_status == "مؤكد" or pa.treatment_plan: return
	if outstanding == 0 and pa.appointment_status == "غير مؤكد":
		pa.db_set("appointment_status", "مؤكد")

@frappe.whitelist()
def create_session(treatment_plan, appointment_date=None):
	plan = frappe.get_doc("Treatment Plan", treatment_plan)
	if not plan.invoice:
		frappe.throw(_("Create the plan invoice before adding sessions."))

	appointment_date = appointment_date or today()
	_validate_appointment_date(plan.employee, appointment_date)

	session_no = frappe.db.count("Patient Appointment", {"treatment_plan": treatment_plan}) + 1
	if session_no > cint(plan.total_sessions):
		frappe.throw(_("All sessions for this plan have already been created."))

	is_last = session_no == cint(plan.total_sessions)
	gate_ok = _session_gate_ok(plan, is_last)
	if is_last and not gate_ok:
		frappe.throw(_("The plan invoice must be fully paid before the last session."))

	doc = frappe.new_doc("Patient Appointment")
	doc.update(
		{
			"naming_series": "APP-.YY.-",
			"appointment_type": "علاج",
			"customer": plan.customer,
			"employee": plan.employee,
			"appointment_date": appointment_date,
			"service_type": frappe.db.get_value("Item", plan.service, "item_group"),
			"service": plan.service,
			"treatment_plan": plan.name,
			"session_no": session_no,
			# A session that already meets the plan's payment gate is ready to serve.
			"appointment_status": "مؤكد" if gate_ok else "انتظار",
		}
	)
	doc.insert()
	doc.submit()
	return doc.name


def _next_queue(employee, appointment_date):

	taken = frappe.get_all(
		"Patient Appointment",
		filters={"employee": employee, "appointment_date": appointment_date, "queue": [">", 0]},
		pluck="queue",
	)
	return (max(taken) + 1) if taken else 1


@frappe.whitelist()
def check_in(appointment):
	"""Assign the per-doctor, per-day queue number when the patient arrives."""
	appt = frappe.get_doc("Patient Appointment", appointment)
	if appt.queue:
		return appt.queue  # already checked in
	if appt.appointment_status == "ملغي":
		frappe.throw(_("Cancelled appointments cannot be checked in."))

	if appt.treatment_plan:
		plan = frappe.get_doc("Treatment Plan", appt.treatment_plan)
		is_last = cint(appt.session_no) == cint(plan.total_sessions)
		if not _session_gate_ok(plan, is_last):
			frappe.throw(_("Payment requirement for this session is not met yet."))
	else:
		if appt.appointment_status != "مؤكد":
			frappe.throw(_("Appointment must be paid before check-in."))

	q = _next_queue(appt.employee, appt.appointment_date)
	appt.db_set("queue", q)
	if appt.treatment_plan:
		# Queuing the session means its gate passed; reflect that on the appointment.
		# The session only counts toward the plan once the doctor completes it.
		if appt.appointment_status != "مؤكد":
			appt.db_set("appointment_status", "مؤكد")
	return q


# ---------------------------------------------------------------- search


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def customer_query(doctype, txt, searchfield, start, page_len, filters):
	"""Customer search that also matches the phone number, which search_widget skips (Phone fieldtype)."""
	or_filters = None
	if txt:
		or_filters = {
			"name": ["like", f"%{txt}%"],
			"customer_name": ["like", f"%{txt}%"],
			"phone_number": _phone_like(txt),
		}

	return frappe.get_list(
		"Customer",
		filters={**(filters or {}), "disabled": 0},
		or_filters=or_filters,
		fields=["name", "customer_name", "phone_number"],
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def custom_search_link(
	doctype: str,
	txt: str,
	query: str | None = None,
	filters: str | dict | list | None = None,
	page_length: int = 10,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
	label_fieldname: str | None = None,
):
	"""Link search. With `label_fieldname`, each row also carries that field's value as `label`."""
	if doctype == "Customer" and not query:
		query = "medic.medic.page.medic_pos.api.customer_query"

	results = search_widget(
		doctype,
		txt.strip(),
		query,
		searchfield=searchfield,
		page_length=page_length,
		filters=filters,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
	)

	rows = build_for_autosuggest(results, doctype=doctype)

	if not label_fieldname:
		return rows

	sanitize_searchfield(label_fieldname)

	meta = frappe.get_meta(doctype)
	if label_fieldname != "name" and not meta.has_field(label_fieldname):
		frappe.throw(_("Invalid label field {0}").format(label_fieldname))

	names = [row.get("value") for row in rows if row.get("value")]
	if not names:
		return rows

	if label_fieldname == "name":
		labels = {name: name for name in names}
	else:
		# search_widget already applied permissions, so the labels are fetched for `names` as-is.
		labels = dict(
			frappe.get_all(
				doctype,
				filters={"name": ["in", names]},
				fields=["name", label_fieldname],
				limit_page_length=0,
				as_list=True,
			)
		)

	for row in rows:
		value = row.get("value")
		if value in labels:
			row["label"] = labels[value]

	return rows


# ---------------------------------------------------------------- sales invoices

SALES_INVOICE_LIST_FIELDS = (
	"name",
	"customer",
	"customer_name",
	"posting_date",
	"grand_total",
	"outstanding_amount",
	"status",
	"currency",
	"is_action_invoice",
)


@frappe.whitelist()
def get_sales_invoices(customer=None, status=None, from_date=None, to_date=None, limit=100):
	"""Sales Invoice list for the company, filters applied on the DB."""
	filters = {"company": _company()}
	if customer:
		filters["customer"] = customer
	if status:
		filters["status"] = status
	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["posting_date"] = [">=", from_date]
	elif to_date:
		filters["posting_date"] = ["<=", to_date]

	return frappe.qb.get_query(
		"Sales Invoice",
		fields=list(SALES_INVOICE_LIST_FIELDS),
		filters=filters,
		order_by="posting_date desc, creation desc",
		limit=limit,
	).run(as_dict=True)


@frappe.whitelist()
def get_sales_invoice(name):
	"""Header, line items and payment history for the invoice details dialog."""
	si = frappe.get_doc("Sales Invoice", name)
	data = {field: si.get(field) for field in SALES_INVOICE_LIST_FIELDS}
	# Source references so the details view can link back to its appointment / plan.
	data["patient_appointment"] = si.get("patient_appointment")
	data["treatment_plan"] = si.get("treatment_plan")
	data["discount_percentage"] = flt(si.additional_discount_percentage)
	data["can_discount"] = si.docstatus == 0 and not _is_non_discountable_invoice(si)
	data["items"] = [
		{
			"item_code": row.item_code,
			"item_name": row.item_name,
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
		}
		for row in si.items
	]

	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": "Sales Invoice", "reference_name": name, "docstatus": 1},
		fields=["parent", "allocated_amount"],
	)
	payments = []
	for ref in refs:
		pe = frappe.db.get_value(
			"Payment Entry", ref.parent, ["posting_date", "mode_of_payment"], as_dict=True
		)
		payments.append(
			{
				"posting_date": pe.posting_date if pe else None,
				"mode_of_payment": pe.mode_of_payment if pe else None,
				"allocated_amount": ref.allocated_amount,
			}
		)

	# POS collections are recorded on the invoice itself, not as Payment Entries.
	for row in si.get("payments") or []:
		if flt(row.amount) > 0:
			payments.append(
				{
					"posting_date": si.posting_date,
					"mode_of_payment": row.mode_of_payment,
					"allocated_amount": flt(row.amount),
				}
			)

	data["payments"] = payments
	return data


# ---------------------------------------------------------------- returns / refunds


def _return_kind(si):
	"""Which return case an invoice qualifies for, or (None, reason).
	Case 1 (appointment): a paid appointment invoice that is not an action or a plan invoice.
	Case 2 (treatment_plan): any treatment-plan invoice."""
	if si.get("treatment_plan"):
		return "treatment_plan", None
	if si.get("is_action_invoice"):
		return None, _("Action invoices cannot be returned here.")
	if not si.get("patient_appointment"):
		return None, _("Only appointment or treatment-plan invoices can be returned.")
	if flt(si.outstanding_amount) >= flt(si.grand_total):
		return None, _("Nothing has been paid on this invoice.")
	return "appointment", None


def _refunded_total(invoice):
	"""Sum already refunded via submitted credit notes against this invoice (positive)."""
	rows = frappe.get_all(
		"Sales Invoice",
		filters={"return_against": invoice, "docstatus": 1},
		fields=["grand_total"],
	)
	return -sum(flt(r.grand_total) for r in rows)  # credit-note totals are negative


@frappe.whitelist()
def get_invoice_return_info(invoice):
	"""What the return dialog needs to decide the case and the refundable amount."""
	si = frappe.get_doc("Sales Invoice", invoice)
	grand = flt(si.grand_total)
	outstanding = flt(si.outstanding_amount)
	paid = grand - outstanding
	refunded = _refunded_total(invoice)
	info = {
		"invoice": invoice,
		"currency": _company_currency(),
		"grand_total": grand,
		"outstanding": outstanding,
		"paid": paid,
		"refunded": refunded,
	}

	kind, reason = _return_kind(si)
	info["kind"] = kind
	if not kind:
		info["reason"] = reason
		return info

	if kind == "appointment":
		max_refund = max(paid - refunded, 0.0)
		if max_refund <= 0.01:
			info["kind"] = None
			info["reason"] = _("This invoice has already been fully refunded.")
			return info
		info["max_refund"] = max_refund
		return info

	# treatment_plan: only the completed sessions' share is owed; refund the rest of what was paid.
	plan = frappe.get_doc("Treatment Plan", si.treatment_plan)
	total_sessions = cint(plan.total_sessions)
	completed = cint(plan.completed_sessions)
	per_session = grand / total_sessions if total_sessions else 0.0
	completed_share = per_session * completed
	info.update(
		{
			"total_sessions": total_sessions,
			"completed_sessions": completed,
			"per_session": per_session,
			"completed_share": completed_share,
			"refundable": max(paid - completed_share - refunded, 0.0),
			"shortfall": max(completed_share - paid, 0.0),
		}
	)
	return info


def _add_refund(return_invoice, amount, mode_of_payment, reference_no=None, reference_date=None):
	"""Refund Payment Entry against a credit note. Mirrors add_payment but the return invoice's
	negative outstanding makes get_payment_entry produce a `Pay` entry, so we override paid_from."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	# The credit note's outstanding is negative, so the allocation must be negative too;
	# get_payment_entry still produces a positive `Pay` paid_amount (abs of it).
	if _is_foreign({"mode_of_payment": mode_of_payment}):
		frappe.throw(_("Refunds in a foreign currency are not supported."))
	pe = get_payment_entry("Sales Invoice", return_invoice, party_amount=-flt(amount))
	pe.mode_of_payment = mode_of_payment
	# Money leaves the mode's own account (the Pay-side counterpart of add_payment's paid_to).
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": pe.company}, "default_account"
	)
	if account:
		pe.paid_from = account
	if reference_no:
		pe.reference_no = reference_no
	if reference_date:
		pe.reference_date = reference_date
	pe.insert()
	pe.submit()
	return pe.name


@frappe.whitelist()
def create_invoice_return(invoice, amount, payments):
	"""Issue a credit note for `amount` against `invoice` and refund it through `payments`.
	The original invoice's outstanding is left untouched."""
	amount = flt(amount)
	payments = frappe.parse_json(payments) or []
	si = frappe.get_doc("Sales Invoice", invoice)

	kind, reason = _return_kind(si)
	if not kind:
		frappe.throw(reason)

	grand = flt(si.grand_total)
	paid = grand - flt(si.outstanding_amount)
	refunded = _refunded_total(invoice)

	if amount <= 0:
		frappe.throw(_("Return amount must be greater than zero."))
	if kind == "appointment":
		if amount > paid - refunded + 0.01:
			frappe.throw(_("Return amount cannot exceed the refundable amount."))
	else:
		plan = frappe.get_doc("Treatment Plan", si.treatment_plan)
		total_sessions = cint(plan.total_sessions)
		per_session = grand / total_sessions if total_sessions else 0.0
		completed_share = per_session * cint(plan.completed_sessions)
		refundable = max(paid - completed_share - refunded, 0.0)
		if refundable <= 0:
			frappe.throw(_("This plan has no refundable amount."))
		if abs(amount - refundable) > 0.01:
			frappe.throw(_("Return amount must equal the refundable amount."))

	if abs(sum(flt(p.get("amount")) for p in payments) - amount) > 0.01:
		frappe.throw(_("Refund payments must add up to the return amount."))

	# Credit note: one line tied to the original invoice row. Keep the original rate (ERPNext
	# rejects a return rate above it) and carry the amount via a fractional negative qty.
	src = si.items[0]
	rate = flt(src.rate)
	qty = -(amount / rate) if rate else -1
	cn = frappe.new_doc("Sales Invoice")
	cn.customer = si.customer
	cn.company = si.company
	cn.is_return = 1
	cn.return_against = invoice
	cn.append(
		"items",
		{"item_code": src.item_code, "sales_invoice_item": src.name, "qty": qty, "rate": rate or amount},
	)
	cn.insert()
	cn.submit()

	# Refund the credit note's actual total (guards against any qty*rate rounding drift).
	if abs(-flt(cn.grand_total) - amount) > 0.01:
		frappe.throw(_("Could not build a credit note for exactly {0}.").format(amount))

	for p in payments:
		_add_refund(
			cn.name, p.get("amount"), p.get("mode_of_payment"),
			p.get("reference_no"), p.get("reference_date"),
		)

	# Close out the source record.
	if kind == "appointment":
		frappe.db.set_value("Patient Appointment", si.patient_appointment, "appointment_status", "ملغي")
	else:
		frappe.db.set_value("Treatment Plan", si.treatment_plan, "status", "Completed")

	return {"credit_note": cn.name, "amount": amount}


# ---------------------------------------------------------------- pharmacy / POS

# Each context maps to a Clinic Setup POS Profile + Item Group, so the same POS
# view and endpoints serve Pharmacy now and Test Lab later.
POS_CONTEXTS = {
	"pharmacy": {"profile_field": "pharmacy_pos_profile", "group_field": "pharmacy_item_group"},
	"test_lab": {"profile_field": "test_lab_pos_profile", "group_field": "test_lab_item_group"},
}


def _pos_config(context):
	cfg = POS_CONTEXTS.get(context)
	if not cfg:
		frappe.throw(_("Unknown POS context: {0}").format(context))

	cs = frappe.get_single("Clinic Setup")
	profile = cs.get(cfg["profile_field"])
	if not profile:
		frappe.throw(_("No POS Profile is configured for {0} in Clinic Setup.").format(context))

	return {"pos_profile": profile, "item_group": cs.get(cfg["group_field"])}


def _item_uoms(item_code, stock_uom):
	uoms = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code},
		fields=["uom", "conversion_factor"],
	)
	if not any(u["uom"] == stock_uom for u in uoms):
		uoms.insert(0, {"uom": stock_uom, "conversion_factor": 1})
	return uoms


def _pos_item_line(profile, item_code, qty=1):
	"""One POS cart line: price at stock UOM + available qty + the item's UOMs."""
	from erpnext.stock.get_item_details import get_bin_details, get_price_list_rate_for

	item = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
	stock_uom = item.stock_uom
	rate = get_price_list_rate_for(
		frappe._dict(
			price_list=profile.selling_price_list,
			uom=stock_uom,
			qty=qty,
			transaction_date=today(),
			conversion_factor=1,
		),
		item_code,
	)
	bin_details = get_bin_details(item_code, profile.warehouse)
	return {
		"item_code": item_code,
		"item_name": item.item_name,
		"stock_uom": stock_uom,
		"uom": stock_uom,
		"qty": qty,
		"conversion_factor": 1,
		"price_list_rate": flt(rate),
		"rate": flt(rate),
		"actual_qty": flt(bin_details.get("actual_qty")),
		"uoms": _item_uoms(item_code, stock_uom),
	}


@frappe.whitelist()
def get_pos_context(context):
	cfg = _pos_config(context)
	p = frappe.get_doc("POS Profile", cfg["pos_profile"])
	# type lets the pay dialog know which modes need a reference (bank/cheque).
	mode_types = dict(
		frappe.get_all("Mode of Payment", fields=["name", "type"], as_list=True)
	)
	return {
		"pos_profile": p.name,
		"item_group": cfg["item_group"],
		"customer": p.customer,
		"price_list": p.selling_price_list,
		"warehouse": p.warehouse,
		"company": p.company,
		"currency": p.currency,
		"print_format": p.print_format,
		"payment_modes": [
			{
				"mode_of_payment": row.mode_of_payment,
				"default": row.default,
				"type": mode_types.get(row.mode_of_payment),
			}
			for row in p.payments
		],
	}


@frappe.whitelist()
def pos_search_items(context, txt=""):
	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	filters = {"disabled": 0, "is_sales_item": 1}
	if cfg["item_group"]:
		filters["item_group"] = cfg["item_group"]

	or_filters = None
	if txt:
		or_filters = {"item_code": ["like", f"%{txt}%"], "item_name": ["like", f"%{txt}%"]}

	items = frappe.get_all(
		"Item", filters=filters, or_filters=or_filters, pluck="name", limit=40, order_by="item_name asc"
	)
	return [_pos_item_line(profile, code) for code in items]


@frappe.whitelist()
def pos_item_price(context, item_code, uom):
	from erpnext.stock.get_item_details import get_conversion_factor, get_price_list_rate_for

	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	conversion_factor = flt(get_conversion_factor(item_code, uom).get("conversion_factor")) or 1
	rate = get_price_list_rate_for(
		frappe._dict(
			price_list=profile.selling_price_list,
			uom=uom,
			qty=1,
			transaction_date=today(),
			conversion_factor=conversion_factor,
		),
		item_code,
	)
	return {"price_list_rate": flt(rate), "conversion_factor": conversion_factor}


@frappe.whitelist()
def get_prescription_cart(context, prescription):
	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	pr = frappe.get_doc("Prescription", prescription)
	return {
		"customer": pr.patient,
		"items": [_pos_item_line(profile, row.item) for row in pr.items],
	}


@frappe.whitelist()
def create_pos_invoice(context, customer, items, payments, prescription=None):
	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	items = frappe.parse_json(items) or []
	payments = frappe.parse_json(payments) or []
	if not items:
		frappe.throw(_("Add at least one item before checkout."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = customer
	si.company = profile.company
	si.pos_profile = profile.name
	si.is_pos = 1
	si.update_stock = 1
	si.selling_price_list = profile.selling_price_list
	si.set_warehouse = profile.warehouse
	for it in items:
		si.append(
			"items",
			{
				"item_code": it["item_code"],
				"qty": flt(it["qty"]),
				"uom": it.get("uom"),
				"conversion_factor": flt(it.get("conversion_factor")) or 1,
				"rate": flt(it["rate"]),
				"warehouse": profile.warehouse,
			},
		)
	for p in payments:
		si.append("payments", {"mode_of_payment": p["mode_of_payment"], "amount": flt(p["amount"])})
	si.insert()

	# Prescription invoices are always paid in full.
	if prescription and abs(sum(flt(p["amount"]) for p in payments) - flt(si.grand_total)) > 0.005:
		frappe.throw(_("A prescription invoice must be paid in full."))

	si.submit()

	if prescription:
		pr = frappe.get_doc("Prescription", prescription)
		pr.db_set("invoice_created", 1)
		pr.db_set("sales_invoice", si.name)

	return {"name": si.name, "grand_total": flt(si.grand_total)}


@frappe.whitelist()
def list_prescriptions(customer=None, mobile=None, include_invoiced=0):
	filters = {}
	if customer:
		filters["patient"] = customer
	if not cint(include_invoiced):
		filters["invoice_created"] = 0
	if mobile:
		matches = frappe.get_all(
			"Customer", filters={"phone_number": _phone_like(mobile)}, pluck="name"
		)
		filters["patient"] = ["in", matches or [""]]

	return frappe.qb.get_query(
		"Prescription",
		fields=[
			"name",
			"patient",
			"patient.customer_name as customer_name",
			"patient.phone_number as mobile",
			"posting_date",
			"invoice_created",
			"sales_invoice",
		],
		filters=filters,
		order_by="creation desc",
	).run(as_dict=True)


# ---------------------------------------------------------------------------
# Test Requests (Lab)
# ---------------------------------------------------------------------------
def _test_request_total(items):
	"""Sum the price of the given Lab Test item codes (qty 1 each) for the deposit target.
	Priced off the cashier POS Profile's price list, falling back to the item's standard rate."""
	price_list = None
	profile = frappe.db.get_single_value("Clinic Setup", "cashier_pos_profile")
	if profile:
		price_list = frappe.db.get_value("POS Profile", profile, "selling_price_list")
	total = 0.0
	for code in items:
		rate = None
		if price_list:
			rate = frappe.db.get_value(
				"Item Price", {"item_code": code, "price_list": price_list, "selling": 1}, "price_list_rate"
			)
		if not rate:
			rate = frappe.db.get_value("Item", code, "standard_rate")
		total += flt(rate)
	return total


def _test_request_row(tr):
	"""List/detail dict: patient name, item codes, and the invoice money snapshot."""
	data = tr.as_dict() if hasattr(tr, "as_dict") else dict(tr)
	data["patient_name"] = frappe.db.get_value("Customer", data.get("patient"), "customer_name")
	item_codes = [d.item for d in tr.items]
	data["item_count"] = len(item_codes)
	data.update(_invoice_financials(data.get("sales_invoice")))
	if not data.get("sales_invoice"):
		data["estimated_total"] = _test_request_total(item_codes)
	else:
		data["estimated_total"] = data.get("grand_total")
	data["currency"] = _company_currency()
	return data


@frappe.whitelist()
def list_test_requests(customer=None, status=None, limit=100):
	"""Standalone Lab Tests list, filters applied on the DB."""
	filters = {"docstatus": 1}
	if customer:
		filters["patient"] = customer
	if status:
		filters["status"] = status

	names = frappe.get_all(
		"Test Request", filters=filters, pluck="name", order_by="creation desc", limit=cint(limit)
	)
	return [_test_request_row(frappe.get_doc("Test Request", n)) for n in names]


@frappe.whitelist()
def get_test_request(name):
	tr = frappe.get_doc("Test Request", name)
	data = _test_request_row(tr)
	data["items"] = [
		{"item": d.item, "item_name": frappe.db.get_value("Item", d.item, "item_name")} for d in tr.items
	]
	data["result"] = [
		{"item": r.item, "item_name": frappe.db.get_value("Item", r.item, "item_name"),
		 "uom": r.uom, "reference_range": r.reference_range, "result": r.result}
		for r in tr.result
	]
	return data


@frappe.whitelist()
def create_test_request(patient, items, appointment=None):
	"""Standalone Test Request created and submitted by the lab tech. `items`: list of item codes."""
	items = frappe.parse_json(items) or []
	items = [i for i in items if i]
	if not items:
		frappe.throw(_("Add at least one test."))

	tr = frappe.new_doc("Test Request")
	tr.posting_date = today()
	tr.patient = patient
	tr.appointment = appointment
	for code in items:
		tr.append("items", {"item": code})
	tr.insert()
	tr.submit()
	return tr.name


@frappe.whitelist()
def create_test_request_invoice(name, items=None):
	"""Create a DRAFT Sales Invoice for the chosen items. The cashier sets the payment method
	and submits it later; submitting seeds the result table (events.on_test_request_invoice_submit)."""
	tr = frappe.get_doc("Test Request", name)
	if tr.sales_invoice:
		existing = frappe.db.get_value("Sales Invoice", tr.sales_invoice, "docstatus")
		if existing in (0, 1):
			frappe.throw(_("This request already has an invoice."))

	requested = frappe.parse_json(items) if items else [d.item for d in tr.items]
	requested = [i for i in requested if i]
	valid = {d.item for d in tr.items}
	requested = [i for i in requested if i in valid]
	if not requested:
		frappe.throw(_("Select at least one item to invoice."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = tr.patient
	si.company = _company()
	# Separately-collected invoice: the cashier pays and submits it from the invoice view.
	si.is_action_invoice = 1
	for code in requested:
		si.append("items", {"item_code": code, "qty": 1})
	si.insert()  # draft (docstatus 0)

	# Link now so the on_submit hook that seeds the result table can find this request.
	tr.db_set("sales_invoice", si.name)
	return si.name


@frappe.whitelist()
def save_test_results(name, results):
	"""Lab tech saves result values (partially or fully). Editable only while Ongoing."""
	results = frappe.parse_json(results) or []
	by_item = {r.get("item"): r.get("result") for r in results}
	tr = frappe.get_doc("Test Request", name)
	for row in tr.result:
		if row.item in by_item:
			row.result = by_item[row.item]
	tr.save()
	return get_test_request(name)


@frappe.whitelist()
def start_test_request(name):
	tr = frappe.get_doc("Test Request", name)
	tr.status = "Ongoing"
	tr.save()
	return tr.status


@frappe.whitelist()
def complete_test_request(name):
	tr = frappe.get_doc("Test Request", name)
	tr.status = "Completed"
	tr.save()
	return tr.status


@frappe.whitelist()
def create_appointment_test_request(appointment, items):
	"""Test Request for the appointment's patient, recorded as an action row like a prescription."""
	items = frappe.parse_json(items) or []
	items = [i for i in items if i]
	if not items:
		frappe.throw(_("Add at least one test."))

	pa = frappe.get_doc("Patient Appointment", appointment)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted."))
	if pa.appointment_status == "مكتمل":
		frappe.throw(_("Appointment is already completed."))

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
		{"invoice": tr.name, "invoice_type": "Test Request", "action_type": "تحليل", "paid": 0},
	)
	pa.save()
	return tr.name
