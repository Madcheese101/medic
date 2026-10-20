"""Test Requests (lab). Invoicing and the status flow live in the Test Request doctype module,
shared with its desk form."""

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import cint, today

from medic.billing import cashier_rates, company_currency, financials, invoice_financials
from medic.medic.doctype.test_request.test_request import complete_test, make_sales_invoice, start_test
from medic.medic.page.medic_pos.api.lists import order_by


def _test_request_row(tr):
	"""Detail dict: patient name, item codes, and the invoice money snapshot."""
	data = tr.as_dict()
	data["patient_name"] = frappe.db.get_value("Customer", data.get("patient"), "customer_name")
	item_codes = [d.item for d in tr.items]
	data["item_count"] = len(item_codes)
	data.update(invoice_financials(data.get("sales_invoice")))
	if not data.get("sales_invoice"):
		rates = cashier_rates(item_codes)
		data["estimated_total"] = sum(rates[code] for code in item_codes)
	else:
		data["estimated_total"] = data.get("grand_total")
	data["currency"] = company_currency()
	return data


@frappe.whitelist()
def list_test_requests(customer=None, status=None, start=0, page_length=20, sort_by=None, sort_order=None):
	"""One page of the standalone Lab Tests list, filters applied on the DB."""
	filters = {"docstatus": 1}
	if customer:
		filters["patient"] = customer
	if status:
		filters["status"] = status
	sort_field, direction = order_by(
		sort_by, sort_order, ("name", "posting_date", "status", "sales_invoice"), "creation desc"
	).split()

	tr = frappe.qb.DocType("Test Request")
	cust = frappe.qb.DocType("Customer")
	si = frappe.qb.DocType("Sales Invoice")
	q = (
		frappe.qb.from_(tr)
		.left_join(cust)
		.on(cust.name == tr.patient)
		.left_join(si)
		.on(si.name == tr.sales_invoice)
		.select(
			tr.name,
			tr.patient,
			cust.customer_name.as_("patient_name"),
			tr.posting_date,
			tr.status,
			tr.appointment,
			tr.sales_invoice,
			tr.docstatus,
			si.grand_total.as_("grand_total"),
			si.outstanding_amount.as_("outstanding_amount"),
		)
		.orderby(tr[sort_field], order=Order[direction])
		.limit(cint(page_length))
		.offset(cint(start))
	)
	for field, value in filters.items():
		q = q.where(tr[field] == value)
	rows = q.run(as_dict=True)

	items = {}
	if rows:
		for parent, item in frappe.get_all(
			"Test Request Item",
			filters={"parent": ["in", [r.name for r in rows]], "parenttype": "Test Request"},
			fields=["parent", "item"],
			as_list=True,
		):
			items.setdefault(parent, []).append(item)
	rates = cashier_rates(code for r in rows if not r.sales_invoice for code in items.get(r.name, []))

	currency = company_currency()
	for r in rows:
		codes = items.get(r.name, [])
		r["item_count"] = len(codes)
		if r.sales_invoice:
			r.update(financials(r.grand_total, r.outstanding_amount))
			r["estimated_total"] = r.grand_total
		else:
			r.update(invoice_financials(None))
			r["estimated_total"] = sum(rates[code] for code in codes)
		r["currency"] = currency
	return {"rows": rows, "total": frappe.db.count("Test Request", filters)}


@frappe.whitelist()
def get_test_request(name):
	tr = frappe.get_doc("Test Request", name)
	data = _test_request_row(tr)
	data["items"] = [
		{"item": d.item, "item_name": frappe.db.get_value("Item", d.item, "item_name")} for d in tr.items
	]
	data["result"] = [
		{
			"item": r.item,
			"item_name": frappe.db.get_value("Item", r.item, "item_name"),
			"uom": r.uom,
			"reference_range": r.reference_range,
			"result": r.result,
		}
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
	and submits it later; submitting seeds the result table."""
	return make_sales_invoice(name, items)


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
	return start_test(name)


@frappe.whitelist()
def complete_test_request(name):
	return complete_test(name)
