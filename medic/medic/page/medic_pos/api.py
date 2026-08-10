import frappe
from frappe import _
from frappe.desk.search import build_for_autosuggest, search_widget
from frappe.utils import today

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
):
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
	return build_for_autosuggest(results, doctype=doctype)
