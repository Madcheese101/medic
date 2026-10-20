"""Money helpers shared by the page API and the doctype controllers."""

import frappe
from frappe import _
from frappe.utils import flt

from medic.constants import AppointmentStatus, AppointmentType

DISCOUNT_ROLES = ("Doctor", "Cashier")
NON_DISCOUNTABLE_APPOINTMENT_TYPES = (
	AppointmentType.CONSULTATION,
	AppointmentType.REVIEW,
	AppointmentType.FOLLOW_UP,
)


def company():
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


def company_currency():
	co = company()
	return frappe.db.get_value("Company", co, "default_currency") if co else None


def financials(grand_total, outstanding_amount):
	grand = flt(grand_total)
	outstanding = flt(outstanding_amount)
	paid = grand - outstanding
	return {
		"grand_total": grand,
		"paid": paid,
		"outstanding_amount": outstanding,
		"paid_pct": (paid / grand) if grand else 1.0,
	}


def invoice_financials(invoice):
	"""Money snapshot for a Sales Invoice. No invoice => nothing billed or paid yet."""
	if not invoice:
		return {"grand_total": 0.0, "paid": 0.0, "outstanding_amount": 0.0, "paid_pct": 0.0}
	si = frappe.db.get_value("Sales Invoice", invoice, ["grand_total", "outstanding_amount"], as_dict=True)
	return financials(si.grand_total, si.outstanding_amount)


def cashier_rates(item_codes):
	"""{item_code: rate} for totals shown before an invoice exists. Priced off the cashier POS
	Profile's price list, falling back to the item's standard rate."""
	codes = list(set(item_codes))
	if not codes:
		return {}

	rates = {}
	profile = frappe.db.get_single_value("Clinic Setup", "cashier_pos_profile")
	price_list = frappe.db.get_value("POS Profile", profile, "selling_price_list") if profile else None
	if price_list:
		for code, rate in frappe.get_all(
			"Item Price",
			filters={"item_code": ["in", codes], "price_list": price_list, "selling": 1},
			fields=["item_code", "price_list_rate"],
			as_list=True,
		):
			rates.setdefault(code, rate)

	missing = [code for code in codes if not rates.get(code)]
	if missing:
		rates.update(
			frappe.get_all(
				"Item", filters={"name": ["in", missing]}, fields=["name", "standard_rate"], as_list=True
			)
		)
	return {code: flt(rates.get(code)) for code in codes}


# ---------------------------------------------------------------- discounts


def validated_discount(discount_percentage):
	"""Doctors and cashiers may discount up to Clinic Setup's cap; an unset cap allows none."""
	if not set(DISCOUNT_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("Only doctors and cashiers can add a discount."), frappe.PermissionError)
	pct = flt(discount_percentage)
	max_pct = flt(frappe.db.get_single_value("Clinic Setup", "doctor_max_discount_percentage"))
	if pct < 0 or pct > max_pct:
		frappe.throw(_("Discount must be between 0% and {0}%.").format(max_pct))
	return pct


def apply_discount(si, pct):
	si.apply_discount_on = "Grand Total"
	si.additional_discount_percentage = pct
	# Recomputed from the percentage; reset so clearing the percentage clears the amount too.
	si.discount_amount = 0


def is_non_discountable_invoice(si):
	"""The appointment's own invoice for a consultation, review or follow-up (its action invoices
	are separate services)."""
	return (
		bool(si.get("patient_appointment"))
		and not si.get("is_action_invoice")
		and frappe.db.get_value("Patient Appointment", si.patient_appointment, "appointment_type")
		in NON_DISCOUNTABLE_APPOINTMENT_TYPES
	)


# ---------------------------------------------------------------- payments


def cashier_profile():
	"""The Cashier POS Profile that front-desk collections (appointments, plan deposits) post under."""
	name = frappe.db.get_single_value("Clinic Setup", "cashier_pos_profile")
	if not name:
		frappe.throw(_("Set the Cashier POS Profile in Clinic Setup."))
	return frappe.get_cached_doc("POS Profile", name)


def mode_account(mode_of_payment, co=None):
	return frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": co or company()},
		"default_account",
	)


def mode_currency(mode_of_payment, co=None):
	"""Currency of the mode's account (e.g. a USD cash box); None when the mode has no account."""
	from erpnext.accounts.utils import get_account_currency

	account = mode_account(mode_of_payment, co)
	return get_account_currency(account) if account else None


def is_foreign(p):
	currency = mode_currency(p["mode_of_payment"])
	return bool(currency) and currency != company_currency()


def base_amount(p):
	"""A payment row's value in company currency. Foreign rows carry the cashier's rate of the day."""
	if not is_foreign(p):
		return flt(p.get("amount"))
	if flt(p.get("exchange_rate")) <= 0:
		frappe.throw(_("Enter the exchange rate for {0}.").format(p["mode_of_payment"]))
	return flt(flt(p.get("amount")) * flt(p.get("exchange_rate")), 2)


def rounding_slack(payments):
	"""Foreign cash is counted in its own cents, so its company-currency value may overshoot a
	little; allow half a foreign cent per foreign row (add_payments absorbs it into the rate)."""
	return 0.01 + sum(flt(p.get("exchange_rate")) * 0.005 for p in payments if is_foreign(p))


def pos_pay(si, payments):
	"""Turn a (new or draft) Sales Invoice into a cashier POS invoice paid by `payments`, then submit.
	The payment lands on the invoice itself, so the cashier's POS Profile owns the collection.
	POS payment rows only hold company currency, so foreign-currency rows become Payment Entries."""
	local = [p for p in payments if not is_foreign(p)]
	foreign = [p for p in payments if is_foreign(p)]
	if local:
		profile = cashier_profile()
		si.is_pos = 1
		si.pos_profile = profile.name
		for p in local:
			si.append("payments", {"mode_of_payment": p["mode_of_payment"], "amount": flt(p["amount"])})
	si.save()  # inserts when new; persists is_pos/pos_profile/payments on a draft
	si.submit()
	add_payments(si.name, foreign)
	return si.name


def add_payments(invoice, payments):
	"""One Payment Entry per row of `payments`:
	{mode_of_payment, amount, reference_no?, reference_date?, exchange_rate?}."""
	for p in payments:
		_add_payment(invoice, p)


def _add_payment(invoice, p):
	"""`amount` is in the mode's account currency; a foreign one is converted at `exchange_rate`."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	from erpnext.accounts.utils import get_account_currency

	mode_of_payment = p.get("mode_of_payment")
	co = frappe.db.get_value("Sales Invoice", invoice, "company")
	account = mode_account(mode_of_payment, co)
	account_currency = get_account_currency(account) if account else None
	foreign = bool(account_currency) and account_currency != frappe.get_cached_value(
		"Company", co, "default_currency"
	)

	amount = flt(p.get("amount"))
	party_amount = amount
	if foreign:
		rate = flt(p.get("exchange_rate"))
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
	if p.get("reference_no"):
		pe.reference_no = p.get("reference_no")
	if p.get("reference_date"):
		pe.reference_date = p.get("reference_date")
	pe.insert()
	pe.submit()
	_update_appointment_status(invoice)
	return pe.name


def _update_appointment_status(sales_invoice):
	"""Confirm the invoice's appointment once the invoice is fully paid."""
	pa_name, outstanding = frappe.db.get_value(
		"Sales Invoice", sales_invoice, ["patient_appointment", "outstanding_amount"]
	)
	if not pa_name:
		return
	try:
		pa = frappe.get_doc("Patient Appointment", pa_name)
	except frappe.DoesNotExistError:
		return
	if pa.appointment_status == AppointmentStatus.CONFIRMED or pa.treatment_plan:
		return
	if outstanding == 0 and pa.appointment_status == AppointmentStatus.UNCONFIRMED:
		pa.db_set("appointment_status", AppointmentStatus.CONFIRMED)
