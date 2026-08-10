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
	return data


@frappe.whitelist()
def confirm_appointment(name):
	"""Create the draft Sales Invoice for a Pending appointment and mark it Not Confirmed."""
	pa = frappe.get_doc("Patient Appointment", name)
	if pa.docstatus != 1:
		frappe.throw(_("Appointment must be submitted before confirming."))
	if pa.appointment_status != "انتظار":
		frappe.throw(_("Appointment is already confirmed."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = pa.customer
	si.company = _company()
	# Custom Link field on Sales Invoice; the after_submit event uses it to reach the PA.
	si.patient_appointment = pa.name
	si.append("items", {"item_code": pa.service, "qty": 1})
	si.insert()  # draft (docstatus 0)

	# invoice / appointment_status are read-only on a submitted doc; db_set bypasses that.
	pa.db_set("invoice", si.name)
	pa.db_set("appointment_status", "غير مؤكد")
	return {"invoice": si.name, "appointment_status": "غير مؤكد"}


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
	"""Money snapshot for a plan's Sales Invoice. No invoice => treated as fully paid."""
	if not invoice:
		return {"grand_total": 0.0, "paid": 0.0, "outstanding_amount": 0.0, "paid_pct": 1.0}
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


def _session_gate_ok(plan, is_last):
	"""Two waivers live here: per-plan skip_deposit and per-customer allow_credit."""
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
			"status": "Active",
			"customer": customer,
			"employee": employee,
			"service": service,
			"total_sessions": total_sessions,
			"notes": notes,
		}
	)
	plan.insert()
	plan.submit()

	# One submitted invoice for the whole plan; payments ride on it as Payment Entries.
	si = frappe.new_doc("Sales Invoice")
	si.customer = customer
	si.company = _company()
	si.append("items", {"item_code": service, "qty": total_sessions})
	si.insert()
	si.submit()

	plan.db_set("invoice", si.name)
	return plan.name


def _plan_dict(plan):
	data = plan.as_dict() if hasattr(plan, "as_dict") else dict(plan)
	data.update(_invoice_financials(data.get("invoice")))
	company = _company()
	data["currency"] = frappe.db.get_value("Company", company, "default_currency") if company else None
	return data


@frappe.whitelist()
def get_treatment_plans(customer):
	plans = frappe.get_all(
		"Treatment Plan",
		filters={"customer": customer, "docstatus": 1},
		fields=[
			"name", "status", "service", "employee",
			"total_sessions", "completed_sessions", "invoice",
		],
		order_by="creation desc",
	)
	return [_plan_dict(p) for p in plans]


@frappe.whitelist()
def get_active_treatment_plans(customer=None):
	filters = {"status": "Active", "docstatus": 1}
	if customer:
		filters["customer"] = customer

	out = []
	for p in frappe.get_all(
		"Treatment Plan",
		filters=filters,
		fields=[
			"name", "customer", "employee", "service",
			"total_sessions", "completed_sessions", "invoice",
		],
	):
		if cint(p.completed_sessions) >= cint(p.total_sessions):
			continue  # no sessions left to book
		p["customer_name"] = frappe.db.get_value("Customer", p.customer, "customer_name")
		p.update(_invoice_financials(p.invoice))
		out.append(p)
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
		fields=[
			"name", "customer", "customer.customer_name as customer_name",
			"employee", "employee.employee_name as doctor_name",
			"service", "status", "total_sessions", "completed_sessions", "invoice",
		],
		filters=filters,
		order_by="creation desc",
		limit=limit,
	).run(as_dict=True)
	for r in rows:
		r.update(_invoice_financials(r.get("invoice")))
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
def add_payment(invoice, amount, mode_of_payment, reference_no=None, reference_date=None):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Sales Invoice", invoice, party_amount=flt(amount))
	pe.mode_of_payment = mode_of_payment
	# Bank-type modes require a reference; the dialog collects it for those.
	if reference_no:
		pe.reference_no = reference_no
	if reference_date:
		pe.reference_date = reference_date
	pe.insert()
	pe.submit()
	return pe.name


@frappe.whitelist()
def create_session(treatment_plan):
	plan = frappe.get_doc("Treatment Plan", treatment_plan)
	session_no = frappe.db.count("Patient Appointment", {"treatment_plan": treatment_plan}) + 1
	if session_no > cint(plan.total_sessions):
		frappe.throw(_("All sessions for this plan have already been created."))

	is_last = session_no == cint(plan.total_sessions)
	if is_last and not _session_gate_ok(plan, is_last=True):
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
			"appointment_status": "انتظار",
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
