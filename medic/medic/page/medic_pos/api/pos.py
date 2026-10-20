"""Pharmacy / lab POS: item search, prescription carts and checkout."""

import frappe
from frappe import _
from frappe.utils import cint, flt, today

from medic.medic.page.medic_pos.api.lists import order_by
from medic.medic.page.medic_pos.api.patients import phone_like

# Each context maps to a Clinic Setup POS Profile + Item Group, so the same POS
# view and endpoints serve Pharmacy now and Test Lab later.
POS_CONTEXTS = {
	"pharmacy": {"profile_field": "pharmacy_pos_profile", "group_field": "pharmacy_item_group"},
	"test_lab": {"profile_field": "test_lab_pos_profile", "group_field": "test_lab_item_group"},
}


def _pos_config(context):
	cfg = POS_CONTEXTS.get(context)
	if not cfg:
		frappe.throw(_("Unknown POS context: {0}").format(context))

	cs = frappe.get_single("Clinic Setup")
	profile = cs.get(cfg["profile_field"])
	if not profile:
		frappe.throw(_("No POS Profile is configured for {0} in Clinic Setup.").format(context))

	return {"pos_profile": profile, "item_group": cs.get(cfg["group_field"])}


def _pos_item_lines(profile, item_codes):
	"""One POS cart line per code: price at stock UOM + available qty + the item's UOMs.
	Prices go through ERPNext's pricing one item at a time; the rest is fetched in one query each."""
	from erpnext.stock.get_item_details import get_price_list_rate_for

	codes = list(dict.fromkeys(item_codes))
	if not codes:
		return []

	items = {
		r.name: r
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", codes]},
			fields=["name", "item_name", "stock_uom", "is_stock_item"],
		)
	}
	stock = dict(
		frappe.get_all(
			"Bin",
			filters={"item_code": ["in", codes], "warehouse": profile.warehouse},
			fields=["item_code", "actual_qty"],
			as_list=True,
		)
	)
	uoms = {}
	for r in frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": ["in", codes]},
		fields=["parent", "uom", "conversion_factor"],
		order_by="idx asc",
	):
		uoms.setdefault(r.parent, []).append({"uom": r.uom, "conversion_factor": r.conversion_factor})

	rates = {
		code: flt(
			get_price_list_rate_for(
				frappe._dict(
					price_list=profile.selling_price_list,
					uom=items[code].stock_uom,
					qty=1,
					transaction_date=today(),
					conversion_factor=1,
				),
				code,
			)
		)
		for code in codes
	}

	lines = []
	for code in item_codes:
		stock_uom = items[code].stock_uom
		item_uoms = list(uoms.get(code, []))
		if not any(u["uom"] == stock_uom for u in item_uoms):
			item_uoms.insert(0, {"uom": stock_uom, "conversion_factor": 1})
		lines.append(
			{
				"item_code": code,
				"item_name": items[code].item_name,
				"stock_uom": stock_uom,
				"uom": stock_uom,
				"qty": 1,
				"conversion_factor": 1,
				"price_list_rate": rates[code],
				"rate": rates[code],
				"actual_qty": flt(stock.get(code)),
				"is_stock_item": items[code].is_stock_item,
				"uoms": item_uoms,
			}
		)
	return lines


@frappe.whitelist()
def get_pos_context(context):
	cfg = _pos_config(context)
	p = frappe.get_doc("POS Profile", cfg["pos_profile"])
	# type lets the pay dialog know which modes need a reference (bank/cheque).
	mode_types = dict(frappe.get_all("Mode of Payment", fields=["name", "type"], as_list=True))
	return {
		"pos_profile": p.name,
		"item_group": cfg["item_group"],
		"customer": p.customer,
		"price_list": p.selling_price_list,
		"warehouse": p.warehouse,
		"company": p.company,
		"currency": p.currency,
		"print_format": p.print_format,
		"payment_modes": [
			{
				"mode_of_payment": row.mode_of_payment,
				"default": row.default,
				"type": mode_types.get(row.mode_of_payment),
			}
			for row in p.payments
		],
	}


@frappe.whitelist()
def pos_search_items(context, txt=""):
	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	filters = {"disabled": 0, "is_sales_item": 1}
	if cfg["item_group"]:
		filters["item_group"] = cfg["item_group"]

	or_filters = None
	scanned = []
	if txt:
		or_filters = {"item_code": ["like", f"%{txt}%"], "item_name": ["like", f"%{txt}%"]}
		# A scanned barcode is an exact match, so its item leads the results: Enter adds the first one.
		scanned = frappe.get_all("Item Barcode", filters={"barcode": txt}, pluck="parent")
		if scanned:
			or_filters["name"] = ["in", scanned]

	items = frappe.get_all(
		"Item", filters=filters, or_filters=or_filters, pluck="name", limit=40, order_by="item_name asc"
	)
	items.sort(key=lambda code: code not in scanned)
	return _pos_item_lines(profile, items)


@frappe.whitelist()
def pos_item_price(context, item_code, uom):
	from erpnext.stock.get_item_details import get_conversion_factor, get_price_list_rate_for

	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	conversion_factor = flt(get_conversion_factor(item_code, uom).get("conversion_factor")) or 1
	rate = get_price_list_rate_for(
		frappe._dict(
			price_list=profile.selling_price_list,
			uom=uom,
			qty=1,
			transaction_date=today(),
			conversion_factor=conversion_factor,
		),
		item_code,
	)
	return {"price_list_rate": flt(rate), "conversion_factor": conversion_factor}


@frappe.whitelist()
def get_prescription_cart(context, prescription):
	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	pr = frappe.get_doc("Prescription", prescription)
	return {
		"customer": pr.patient,
		"items": _pos_item_lines(profile, [row.item for row in pr.items]),
	}


@frappe.whitelist()
def create_pos_invoice(context, customer, items, payments, prescription=None):
	cfg = _pos_config(context)
	profile = frappe.get_doc("POS Profile", cfg["pos_profile"])
	items = frappe.parse_json(items) or []
	payments = frappe.parse_json(payments) or []
	if not items:
		frappe.throw(_("Add at least one item before checkout."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = customer
	si.company = profile.company
	si.pos_profile = profile.name
	si.is_pos = 1
	si.update_stock = 1
	si.selling_price_list = profile.selling_price_list
	si.set_warehouse = profile.warehouse
	for it in items:
		si.append(
			"items",
			{
				"item_code": it["item_code"],
				"qty": flt(it["qty"]),
				"uom": it.get("uom"),
				"conversion_factor": flt(it.get("conversion_factor")) or 1,
				"rate": flt(it["rate"]),
				"warehouse": profile.warehouse,
			},
		)
	for p in payments:
		si.append("payments", {"mode_of_payment": p["mode_of_payment"], "amount": flt(p["amount"])})
	si.insert()

	# Prescription invoices are always paid in full.
	if prescription and abs(sum(flt(p["amount"]) for p in payments) - flt(si.grand_total)) > 0.005:
		frappe.throw(_("A prescription invoice must be paid in full."))

	si.submit()

	if prescription:
		pr = frappe.get_doc("Prescription", prescription)
		pr.db_set("invoice_created", 1)
		pr.db_set("sales_invoice", si.name)

	return {"name": si.name, "grand_total": flt(si.grand_total)}


@frappe.whitelist()
def list_prescriptions(
	customer=None, mobile=None, include_invoiced=0, start=0, page_length=20, sort_by=None, sort_order=None
):
	"""One page of the prescriptions list. The patient's name and mobile come from the joined
	Customer, so the list can't sort on them."""
	filters = {}
	if customer:
		filters["patient"] = customer
	if not cint(include_invoiced):
		filters["invoice_created"] = 0
	if mobile:
		matches = frappe.get_all("Customer", filters={"phone_number": phone_like(mobile)}, pluck="name")
		filters["patient"] = ["in", matches or [""]]

	rows = frappe.qb.get_query(
		"Prescription",
		fields=[
			"name",
			"patient",
			"patient.customer_name as customer_name",
			"patient.phone_number as mobile",
			"posting_date",
			"appointment",
			"invoice_created",
			"sales_invoice",
		],
		filters=filters,
		order_by=order_by(sort_by, sort_order, ("name", "posting_date", "invoice_created"), "creation desc"),
		limit=cint(page_length),
		offset=cint(start),
	).run(as_dict=True)
	return {"rows": rows, "total": frappe.db.count("Prescription", filters)}
