import frappe
from frappe import _
from frappe.desk.search import build_for_autosuggest, sanitize_searchfield, search_widget
from frappe.utils import cint, flt, today

PATIENT_FIELDS = ("customer_name", "date_of_birth", "custom_phone_number", "gender", "blood_type")


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
		filters["custom_phone_number"] = ["like", f"%{mobile}%"]
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
def create_patient(customer_name, date_of_birth, custom_phone_number, gender, blood_type=None):
	doc = frappe.new_doc("Customer")
	doc.update(
		{
			"customer_group": "Individual",
			"customer_name": customer_name,
			"date_of_birth": date_of_birth,
			"custom_phone_number": custom_phone_number,
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
def save_patient(name, customer_name, date_of_birth, custom_phone_number, gender, blood_type=None):
	doc = frappe.get_doc("Customer", name)
	doc.update(
		{
			"customer_name": customer_name,
			"date_of_birth": date_of_birth,
			"custom_phone_number": custom_phone_number,
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
	appointment_type, customer, employee, appointment_date, service_type, service, notes=None
):
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
	# Each action row carries its own invoice's totals so the table/pay dialog have amounts.
	currency = _company_currency()
	for row in data.get("actions") or []:
		fin = _invoice_financials(row.get("invoice"))
		row["grand_total"] = fin["grand_total"]
		row["outstanding_amount"] = fin["outstanding_amount"]
		row["currency"] = currency
	return data


def _company_currency():
	company = _company()
	return frappe.db.get_value("Company", company, "default_currency") if company else None


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
def pay_appointment(name, amount, mode_of_payment, reference_no=None, reference_date=None):
	"""Submit the appointment's invoice (if draft) and record a payment; confirm when fully paid."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted before paying."))

	invoice = _ensure_appointment_invoice(pa)
	si = frappe.get_doc("Sales Invoice", invoice)
	if si.docstatus == 0:
		# Submitting unpaid leaves the status غير مؤكد (the events hook returns early);
		# the payment below reduces the outstanding, and we flip to مؤكد once it clears.
		si.submit()

	add_payment(invoice, amount, mode_of_payment, reference_no, reference_date)

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
	pa.db_set("appointment_status", "مكتمل")
	return {"appointment_status": "مكتمل"}


@frappe.whitelist()
def create_appointment_action(name, service, action_type):
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
	si.insert()  # draft (docstatus 0)

	pa.append(
		"actions",
		{"invoice": si.name, "invoice_type": "Sales Invoice", "action_type": action_type, "paid": 0},
	)
	pa.save()
	return si.name


@frappe.whitelist()
def pay_appointment_action(invoice, mode_of_payment, reference_no=None, reference_date=None):
	"""Pay an action invoice IN FULL (submit it if draft), then mark its action row paid."""
	si = frappe.get_doc("Sales Invoice", invoice)
	if si.docstatus == 0:
		si.submit()

	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))
	if outstanding > 0:
		add_payment(invoice, outstanding, mode_of_payment, reference_no, reference_date)

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


# Shared by the list endpoints. The invoice.* fields LEFT JOIN the plan's Sales Invoice
TREATMENT_PLAN_JOIN_FIELDS = (
	"name", "status", "customer", "customer.customer_name as customer_name",
	"employee", "employee.employee_name as doctor_name",
	"service", "total_sessions", "completed_sessions", "invoice",
	"invoice.grand_total as grand_total", "invoice.outstanding_amount as outstanding_amount",
)


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


@frappe.whitelist()
def create_treatment_plan(customer, employee, service, total_sessions, notes=None):
	total_sessions = cint(total_sessions)
	if total_sessions < 1:
		frappe.throw(_("Total sessions must be at least 1."))

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
		}
	)
	plan.insert()
	plan.submit()
	return plan.name


@frappe.whitelist()
def create_treatment_plan_invoice(name):
	"""Create the plan's Sales Invoice on demand; one invoice carries the whole plan."""
	plan = frappe.get_doc("Treatment Plan", name)
	if plan.invoice:
		frappe.throw(_("This plan already has an invoice."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = plan.customer
	si.company = _company()
	# Custom Link field on Sales Invoice recording which plan this invoice belongs to.
	si.treatment_plan = plan.name
	si.append("items", {"item_code": plan.service, "qty": plan.total_sessions})
	si.insert()
	si.submit()

	plan.db_set("invoice", si.name)
	if plan.status == "Pending":
		plan.db_set("status", "Active")
	return si.name


def _plan_dict(plan):
	data = plan.as_dict() if hasattr(plan, "as_dict") else dict(plan)
	data.update(_invoice_financials(data.get("invoice")))
	company = _company()
	data["currency"] = frappe.db.get_value("Company", company, "default_currency") if company else None
	return data


@frappe.whitelist()
def get_treatment_plans(customer):
	currency = _company_currency()
	rows = frappe.qb.get_query(
		"Treatment Plan",
		fields=list(TREATMENT_PLAN_JOIN_FIELDS),
		filters={"customer": customer, "docstatus": 1},
		order_by="creation desc",
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

	rows = frappe.qb.get_query(
		"Treatment Plan",
		fields=list(TREATMENT_PLAN_JOIN_FIELDS),
		filters=filters,
	).run(as_dict=True)
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

	rows = frappe.qb.get_query(
		"Treatment Plan",
		fields=list(TREATMENT_PLAN_JOIN_FIELDS),
		filters=filters,
		order_by="creation desc",
		limit=limit,
	).run(as_dict=True)
	for r in rows:
		_apply_financials(r)
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
	"""Enabled Modes of Payment with their type, so the dialog knows when to require a reference."""
	return frappe.get_all(
		"Mode of Payment", filters={"enabled": 1}, fields=["name", "type"], order_by="name"
	)


@frappe.whitelist()
def add_payment(invoice, amount, mode_of_payment, reference_no=None, reference_date=None):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	pe = get_payment_entry("Sales Invoice", invoice, party_amount=flt(amount))
	pe.mode_of_payment = mode_of_payment
	# get_payment_entry defaults paid_to to the company account, which may be a Bank type and
	# would then demand a reference. Use the mode's own account so a Cash mode stays Cash.
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": pe.company}, "default_account"
	)
	if account:
		pe.paid_to = account
	# Bank-type modes require a reference; the dialog collects it for those.
	if reference_no:
		pe.reference_no = reference_no
	if reference_date:
		pe.reference_date = reference_date
	pe.insert()
	pe.submit()
	_update_appointment_status(invoice)
	return pe.name

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
def create_session(treatment_plan):
	plan = frappe.get_doc("Treatment Plan", treatment_plan)
	if not plan.invoice:
		frappe.throw(_("Create the plan invoice before adding sessions."))

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
			"appointment_date": today(),
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
		plan.db_set("completed_sessions", cint(plan.completed_sessions) + 1)
		# Queuing the session means its gate passed; reflect that on the appointment.
		if appt.appointment_status != "مؤكد":
			appt.db_set("appointment_status", "مؤكد")
	return q


# ---------------------------------------------------------------- search


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
	data["payments"] = payments
	return data
