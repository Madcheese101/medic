"""Invoices: listing, payments, discounts, and returns/refunds."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from medic.billing import (
	NON_DISCOUNTABLE_APPOINTMENT_TYPES,
	add_payments,
	apply_discount,
	company,
	company_currency,
	is_foreign,
	is_non_discountable_invoice,
	mode_account,
	mode_currency,
	validated_discount,
)
from medic.constants import AppointmentStatus, label
from medic.medic.page.medic_pos.api.lists import date_range, order_by


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
def record_payments(invoice, payments):
	"""Record one or more payments against an already-submitted Sales Invoice (partial allowed).
	`payments`: list of {mode_of_payment, amount, reference_no?, reference_date?, exchange_rate?}."""
	add_payments(invoice, frappe.parse_json(payments) or [])
	return {
		"invoice": invoice,
		"outstanding_amount": flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")),
	}


@frappe.whitelist()
def set_invoice_discount(invoice, discount_percentage):
	"""Discount a draft Sales Invoice. Once submitted, its total is final."""
	pct = validated_discount(discount_percentage)
	si = frappe.get_doc("Sales Invoice", invoice)
	if si.docstatus != 0:
		frappe.throw(_("A discount can only be added before the invoice is submitted."))
	if is_non_discountable_invoice(si):
		frappe.throw(
			_("{0}, {1} and {2} appointments cannot be discounted.").format(
				*(label(t, "Patient Appointment") for t in NON_DISCOUNTABLE_APPOINTMENT_TYPES)
			)
		)
	apply_discount(si, pct)
	si.save()
	return {"grand_total": si.grand_total, "discount_percentage": pct}


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
def get_sales_invoices(
	customer=None,
	status=None,
	from_date=None,
	to_date=None,
	start=0,
	page_length=20,
	sort_by=None,
	sort_order=None,
):
	"""One page of the company's Sales Invoices, filters applied on the DB."""
	filters = {"company": company()}
	if customer:
		filters["customer"] = customer
	if status:
		filters["status"] = status
	if dates := date_range(from_date, to_date):
		filters["posting_date"] = dates

	rows = frappe.qb.get_query(
		"Sales Invoice",
		fields=list(SALES_INVOICE_LIST_FIELDS),
		filters=filters,
		order_by=order_by(sort_by, sort_order, SALES_INVOICE_LIST_FIELDS, "posting_date desc, creation desc"),
		limit=cint(page_length),
		offset=cint(start),
	).run(as_dict=True)
	return {"rows": rows, "total": frappe.db.count("Sales Invoice", filters)}


@frappe.whitelist()
def get_sales_invoice(name):
	"""Header, line items and payment history for the invoice details dialog."""
	si = frappe.get_doc("Sales Invoice", name)
	data = {field: si.get(field) for field in SALES_INVOICE_LIST_FIELDS}
	# Source references so the details view can link back to its appointment / plan.
	data["patient_appointment"] = si.get("patient_appointment")
	data["treatment_plan"] = si.get("treatment_plan")
	data["discount_percentage"] = flt(si.additional_discount_percentage)
	data["can_discount"] = si.docstatus == 0 and not is_non_discountable_invoice(si)
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
		"currency": company_currency(),
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
	"""Refund Payment Entry against a credit note. Mirrors add_payments but the return invoice's
	negative outstanding makes get_payment_entry produce a `Pay` entry, so we override paid_from."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	# The credit note's outstanding is negative, so the allocation must be negative too;
	# get_payment_entry still produces a positive `Pay` paid_amount (abs of it).
	if is_foreign({"mode_of_payment": mode_of_payment}):
		frappe.throw(_("Refunds in a foreign currency are not supported."))
	pe = get_payment_entry("Sales Invoice", return_invoice, party_amount=-flt(amount))
	pe.mode_of_payment = mode_of_payment
	# Money leaves the mode's own account (the Pay-side counterpart of add_payments' paid_to).
	account = mode_account(mode_of_payment, pe.company)
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
			cn.name,
			p.get("amount"),
			p.get("mode_of_payment"),
			p.get("reference_no"),
			p.get("reference_date"),
		)

	# Close out the source record.
	if kind == "appointment":
		frappe.db.set_value(
			"Patient Appointment", si.patient_appointment, "appointment_status", AppointmentStatus.CANCELLED
		)
	else:
		frappe.db.set_value("Treatment Plan", si.treatment_plan, "status", "Completed")

	return {"credit_note": cn.name, "amount": amount}
