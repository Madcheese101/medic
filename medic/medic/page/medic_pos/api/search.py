"""Link-field autocomplete for the SPA's search fields."""

import frappe
from frappe import _
from frappe.desk.search import build_for_autosuggest, sanitize_searchfield, search_widget

from medic.medic.page.medic_pos.api.patients import phone_like


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def customer_query(doctype, txt, searchfield, start, page_len, filters):
	"""Customer search that also matches the phone number, which search_widget skips (Phone fieldtype)."""
	or_filters = None
	if txt:
		or_filters = {
			"name": ["like", f"%{txt}%"],
			"customer_name": ["like", f"%{txt}%"],
			"phone_number": phone_like(txt),
		}

	return frappe.get_list(
		"Customer",
		filters={**(filters or {}), "disabled": 0},
		or_filters=or_filters,
		fields=["name", "customer_name", "phone_number"],
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)


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
	if doctype == "Customer" and not query:
		query = "medic.medic.page.medic_pos.api.search.customer_query"

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
