"""Fixtures for Medic's API tests.

Everything is created inside the test class's transaction, which FrappeTestCase rolls back
when the class finishes, so the tests can run on a site that holds real data. Run them with
`--skip-before-tests --skip-test-records`: ERPNext's before_tests hook deletes every Item Price.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today
from frappe.utils.nestedset import get_root_of

from medic.constants import AppointmentType

P = "_Test Medic"
API = "medic.medic.page.medic_pos.api"


def call(method, **kwargs):
	"""Call an SPA endpoint by the dotted name the frontend uses, checking it is whitelisted."""
	fn = frappe.get_attr(f"{API}.{method}")
	frappe.is_whitelisted(fn)
	return fn(**kwargs)


def company():
	# Mirrors how the API picks the company.
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


def appointment_status(name):
	return frappe.db.get_value("Patient Appointment", name, "appointment_status")


class MedicTestCase(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.fx = make_fixtures()

	def cash(self, amount):
		return {"mode_of_payment": self.fx.cash, "amount": amount}

	def foreign(self, amount, rate):
		return {"mode_of_payment": self.fx.foreign, "amount": amount, "exchange_rate": rate}

	def make_patient(self):
		return call(
			"patients.create_patient",
			customer_name=f"{P} Patient {frappe.generate_hash(length=6)}",
			date_of_birth="1990-01-01",
			phone_number="+218912345678",
			gender="Male",
		)

	def make_appointment(self, appointment_type=AppointmentType.CONSULTATION, patient=None):
		return call(
			"appointments.create_appointment",
			appointment_type=appointment_type,
			customer=patient or self.make_patient(),
			employee=self.fx.doctor,
			appointment_date=today(),
			service_type=self.fx.consult_group,
			service=self.fx.consult_item,
		)

	def make_paid_appointment(self, appointment_type=AppointmentType.CONSULTATION):
		name = self.make_appointment(appointment_type)
		invoice = call("appointments.confirm_appointment_invoice", name=name)["invoice"]
		call("appointments.pay_appointment", name=name, payments=[self.cash(100)])
		return name, invoice

	def make_plan(self, total_sessions, patient=None, **kwargs):
		return call(
			"treatments.create_treatment_plan",
			customer=patient or self.make_patient(),
			employee=self.fx.doctor,
			service=self.fx.session_item,
			total_sessions=total_sessions,
			**kwargs,
		)


def make_fixtures():
	co = company()
	currency = frappe.get_cached_value("Company", co, "default_currency")
	cash_account = frappe.get_cached_value("Company", co, "default_cash_account")
	# Appointment and plan invoices are made without a price list, so they fall back to the
	# Selling Settings default; price the test items there.
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")

	foreign_currency = "EUR" if currency == "USD" else "USD"
	foreign_account = _insert(
		"Account",
		account_name=f"{P} {foreign_currency} Cash",
		parent_account=frappe.get_cached_value("Account", cash_account, "parent_account"),
		company=co,
		account_type="Cash",
		account_currency=foreign_currency,
	).name
	cash = _mode_of_payment(f"{P} Cash", co, cash_account)
	foreign = _mode_of_payment(f"{P} Foreign Cash", co, foreign_account)

	warehouse = _insert("Warehouse", warehouse_name=f"{P} Store", company=co).name
	pos_profile = _insert(
		"POS Profile",
		__newname=f"{P} Cashier",
		company=co,
		currency=currency,
		warehouse=warehouse,
		selling_price_list=price_list,
		write_off_account=frappe.get_cached_value("Company", co, "write_off_account"),
		write_off_cost_center=frappe.get_cached_value("Company", co, "cost_center"),
		write_off_limit=0,
		update_stock=1,
		payments=[{"mode_of_payment": cash, "default": 1}],
	).name

	services = _item_group(f"{P} Services", is_group=1)
	consult_group = _item_group(f"{P} Consultations", parent=services, items_type="Service")
	procedure_group = _item_group(f"{P} Procedures", parent=services, items_type="Service")
	lab_group = _item_group(f"{P} Lab", items_type="Lab Test")
	pharmacy_group = _item_group(f"{P} Pharmacy", items_type="Pharma")

	designation = _insert("Designation", designation_name=f"{P} Doctor").name
	frappe.db.set_single_value(
		"Clinic Setup",
		{
			"service_parent_item_group": services,
			"doctors_default_designation": designation,
			"cashier_pos_profile": pos_profile,
			"doctor_max_discount_percentage": 25,
			"enable_pharmacy": 1,
			"pharmacy_item_group": pharmacy_group,
			"pharmacy_pos_profile": pos_profile,
		},
	)

	return frappe._dict(
		company=co,
		currency=currency,
		price_list=price_list,
		cash=cash,
		foreign=foreign,
		foreign_currency=foreign_currency,
		warehouse=warehouse,
		pos_profile=pos_profile,
		consult_group=consult_group,
		procedure_group=procedure_group,
		consult_item=_item(f"{P} Consult", consult_group, 100, price_list),
		session_item=_item(f"{P} Laser Session", procedure_group, 100, price_list),
		lab_items=[
			_item(f"{P} CBC", lab_group, 30, price_list),
			_item(f"{P} Glucose", lab_group, 20, price_list),
		],
		drug=_item(f"{P} Paracetamol", pharmacy_group, 5, price_list, stock=True),
		doctor=make_doctor(),
	)


def make_doctor(maximum_appointments=0):
	"""A doctor open every day, taking up to `maximum_appointments` a day (0 = no cap)."""
	doctor = _insert(
		"Employee",
		# Doctor Schedule is named after the doctor, so each one needs a name of its own.
		first_name=f"{P} Doctor {frappe.generate_hash(length=6)}",
		gender="Male",
		date_of_birth="1980-01-01",
		date_of_joining="2020-01-01",
		company=company(),
		status="Active",
		designation=frappe.db.get_single_value("Clinic Setup", "doctors_default_designation"),
	).name
	# on_employee_create made the schedule with every day off.
	schedule = frappe.get_doc("Doctor Schedule", {"employee": doctor})
	for row in schedule.schedule:
		row.update(
			{
				"is_active": 1,
				"from_time": "08:00:00",
				"to_time": "20:00:00",
				"maximum_appointments": maximum_appointments,
			}
		)
	schedule.save()
	return doctor


def _insert(doctype, **fields):
	# A site may add its own mandatory custom fields to these masters; they don't matter here.
	return frappe.get_doc({"doctype": doctype, **fields}).insert(ignore_mandatory=True)


def _mode_of_payment(name, co, account):
	return _insert(
		"Mode of Payment",
		mode_of_payment=name,
		type="Cash",
		enabled=1,
		accounts=[{"company": co, "default_account": account}],
	).name


def _item_group(name, parent=None, is_group=0, items_type=None):
	return _insert(
		"Item Group",
		item_group_name=name,
		parent_item_group=parent or get_root_of("Item Group"),
		is_group=is_group,
		items_type=items_type,
	).name


def _item(code, item_group, rate, price_list, stock=False):
	# item_type is fetched from the group's items_type.
	_insert(
		"Item",
		item_code=code,
		item_name=code,
		item_group=item_group,
		stock_uom="Nos",
		is_stock_item=int(stock),
		include_item_in_manufacturing=0,
	)
	_insert("Item Price", item_code=code, price_list=price_list, price_list_rate=rate)
	return code
