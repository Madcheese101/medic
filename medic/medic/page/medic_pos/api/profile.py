"""The logged-in user: linked employee, profile and availability schedule."""

import frappe
from frappe import _


def _linked_employee():
	return frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user}, ["name", "employee_name"], as_dict=True
	)


@frappe.whitelist()
def load_defaults():
	return {"employee": _linked_employee()}


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
