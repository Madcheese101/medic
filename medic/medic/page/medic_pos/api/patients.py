"""Patients (ERPNext Customers) and their Medical History."""

import frappe
from frappe.utils import cint, today

from medic.billing import company
from medic.events import e164
from medic.medic.page.medic_pos.api.lists import order_by

PATIENT_FIELDS = ("customer_name", "date_of_birth", "phone_number", "gender", "blood_type")


def phone_like(mobile):
	"""Numbers are stored in E.164 (+218…), so drop the leading 0 of a locally-typed one."""
	return ["like", f"%{mobile.strip().lstrip('0')}%"]


@frappe.whitelist()
def get_patients(
	customer_name=None, mobile=None, file_no=None, start=0, page_length=20, sort_by=None, sort_order=None
):
	"""One page of the patient list, with the filters applied on the DB, not in the browser."""
	filters = {}
	if customer_name:
		filters["customer_name"] = ["like", f"%{customer_name}%"]
	if mobile:
		filters["phone_number"] = phone_like(mobile)
	if file_no:
		filters["name"] = ["like", f"%{file_no}%"]

	rows = frappe.qb.get_query(
		"Customer",
		fields=["name", *PATIENT_FIELDS],
		filters=filters,
		order_by=order_by(sort_by, sort_order, ("name", *PATIENT_FIELDS), "creation desc"),
		limit=cint(page_length),
		offset=cint(start),
	).run(as_dict=True)
	return {"rows": rows, "total": frappe.db.count("Customer", filters)}


@frappe.whitelist()
def patients_with_phone(phone_number, exclude=None):
	"""Other patients registered with this mobile number, so the forms can warn about a duplicate.
	Numbers are stored in E.164, so the typed one is converted the same way first."""
	number = e164(phone_number)
	if not number:
		return []
	filters = {"phone_number": number}
	if exclude:
		filters["name"] = ["!=", exclude]
	return frappe.get_all("Customer", filters=filters, fields=["name", "customer_name"], limit=5)


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

	co = company()
	balance = get_balance_on(party_type="Customer", party=customer, company=co, date=today())
	currency = frappe.db.get_value("Company", co, "default_currency") if co else None
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
