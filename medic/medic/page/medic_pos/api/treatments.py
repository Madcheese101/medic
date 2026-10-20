"""Treatment plans: one invoice for the whole plan, and its sessions as appointments."""

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import cint, flt, today

from medic.billing import (
	apply_discount,
	cashier_rates,
	company,
	company_currency,
	invoice_financials,
	pos_pay,
	validated_discount,
)
from medic.constants import AppointmentStatus, AppointmentType
from medic.medic.page.medic_pos.api.appointments import validate_appointment_date


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
		.left_join(cust)
		.on(cust.name == tp.customer)
		.left_join(emp)
		.on(emp.name == tp.employee)
		.left_join(item)
		.on(item.name == tp.service)
		.left_join(si)
		.on(si.name == tp.invoice)
		.select(
			tp.name,
			tp.status,
			tp.customer,
			cust.customer_name.as_("customer_name"),
			tp.employee,
			emp.employee_name.as_("doctor_name"),
			tp.service,
			item.item_name.as_("service_name"),
			tp.total_sessions,
			tp.completed_sessions,
			tp.invoice,
			tp.discount_percentage,
			si.grand_total.as_("grand_total"),
			si.outstanding_amount.as_("outstanding_amount"),
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


def _estimated_total(rate, total_sessions, discount_percentage=0):
	"""Plan price before its invoice exists, so the deposit dialog has a target total."""
	return flt(flt(rate) * cint(total_sessions) * (1 - flt(discount_percentage) / 100), 2)


@frappe.whitelist()
def set_treatment_plan_discount(name, discount_percentage):
	"""The plan's invoice is submitted as soon as it is created, so its discount is set on the
	plan beforehand and applied when the invoice is made."""
	pct = validated_discount(discount_percentage)
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
	pct = validated_discount(discount_percentage) if flt(discount_percentage) else 0

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
	si.company = company()
	# Custom Link field on Sales Invoice recording which plan this invoice belongs to.
	si.treatment_plan = plan.name
	si.append("items", {"item_code": plan.service, "qty": plan.total_sessions})
	if flt(plan.discount_percentage):
		apply_discount(si, flt(plan.discount_percentage))

	if payments:
		pos_pay(si, payments)  # cashier POS invoice carrying the initial deposit
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


@frappe.whitelist()
def get_treatment_plans(customer):
	currency = company_currency()
	rows = _treatment_plans_query({"customer": customer, "docstatus": 1}, order_by_creation=True).run(
		as_dict=True
	)
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
	# Deposit target for plans that have no invoice yet.
	rates = cashier_rates(r.service for r in rows if not r.grand_total)
	for r in rows:
		r["estimated_total"] = flt(r.grand_total) or _estimated_total(
			rates.get(r.service), r.total_sessions, r.discount_percentage
		)
		_apply_financials(r)
	return rows


@frappe.whitelist()
def get_treatment_plan(name):
	plan = frappe.get_doc("Treatment Plan", name)
	data = plan.as_dict()
	data["service_name"] = frappe.db.get_value("Item", plan.service, "item_name")
	data["customer_name"] = frappe.db.get_value("Customer", plan.customer, "customer_name")
	data["doctor_name"] = frappe.db.get_value("Employee", plan.employee, "employee_name")
	data.update(invoice_financials(plan.invoice))
	# Target for the "create invoice + deposit" dialog when there is no invoice yet.
	data["estimated_total"] = data.get("grand_total") or _estimated_total(
		cashier_rates([plan.service]).get(plan.service), plan.total_sessions, plan.discount_percentage
	)
	data["currency"] = company_currency()
	data["sessions"] = frappe.get_all(
		"Patient Appointment",
		filters={"treatment_plan": name},  # Data match on the plan name
		fields=["name", "appointment_date", "session_no", "appointment_status", "queue", "docstatus"],
		order_by="session_no asc",
	)
	return data


@frappe.whitelist()
def create_session(treatment_plan, appointment_date=None):
	plan = frappe.get_doc("Treatment Plan", treatment_plan)
	if not plan.invoice:
		frappe.throw(_("Create the plan invoice before adding sessions."))

	appointment_date = appointment_date or today()
	validate_appointment_date(plan.employee, appointment_date)

	session_no = frappe.db.count("Patient Appointment", {"treatment_plan": treatment_plan}) + 1
	if session_no > cint(plan.total_sessions):
		frappe.throw(_("All sessions for this plan have already been created."))

	is_last = session_no == cint(plan.total_sessions)
	gate_ok = plan.session_gate_ok(is_last)
	if is_last and not gate_ok:
		frappe.throw(_("The plan invoice must be fully paid before the last session."))

	doc = frappe.new_doc("Patient Appointment")
	doc.update(
		{
			"naming_series": "APP-.YY.-",
			"appointment_type": AppointmentType.TREATMENT,
			"customer": plan.customer,
			"employee": plan.employee,
			"appointment_date": appointment_date,
			"service_type": frappe.db.get_value("Item", plan.service, "item_group"),
			"service": plan.service,
			"treatment_plan": plan.name,
			"session_no": session_no,
			# A session that already meets the plan's payment gate is ready to serve.
			"appointment_status": AppointmentStatus.CONFIRMED if gate_ok else AppointmentStatus.PENDING,
		}
	)
	doc.insert()
	doc.submit()
	return doc.name
