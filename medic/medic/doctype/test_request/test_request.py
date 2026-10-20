# Copyright (c) 2026, Nawa Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from medic.billing import company


class TestRequest(Document):
	def validate(self):
		if not self.status:
			self.status = "Pending"
		self.validate_status_flow()
		self.validate_results()

	# Status changes and result entry all happen after submit, where Frappe runs
	# before_update_after_submit instead of validate.
	def before_update_after_submit(self):
		self.validate_status_flow()
		self.validate_results()

	def validate_status_flow(self):
		"""Guard the Pending -> Ongoing -> Completed transitions."""
		before = self.get_doc_before_save()
		old = before.status if before else None
		if old == self.status:
			return

		if self.status == "Ongoing":
			if old not in (None, "Pending"):
				frappe.throw(_("A test can only be started from the Pending state."))
			if not self.is_invoice_paid():
				frappe.throw(
					_("Cannot start the test: its Sales Invoice must be submitted and fully paid.")
				)
		elif self.status == "Completed":
			if old != "Ongoing":
				frappe.throw(_("A test can only be completed from the Ongoing state."))
			self.validate_results_filled()

	def validate_results(self):
		"""Results are entered only while Ongoing, and frozen once Completed."""
		before = self.get_doc_before_save()
		# Completed is terminal: the result table can no longer change.
		if before and before.status == "Completed":
			frappe.throw(_("This test is completed and can no longer be edited."))
		# Result values may only be filled once the test has started.
		if self.status not in ("Ongoing", "Completed"):
			if any((r.result or "").strip() for r in self.result):
				frappe.throw(_("Start the test before entering results."))

	def validate_results_filled(self):
		if not self.result:
			frappe.throw(_("There are no results to complete."))
		missing = [r.item for r in self.result if not (r.result or "").strip()]
		if missing:
			frappe.throw(
				_("Enter a result for every test before completing: {0}").format(", ".join(missing))
			)

	def is_invoice_paid(self):
		"""True when the linked Sales Invoice is submitted and has nothing outstanding."""
		if not self.sales_invoice:
			return False
		si = frappe.db.get_value(
			"Sales Invoice", self.sales_invoice, ["docstatus", "outstanding_amount"], as_dict=True
		)
		return bool(si and si.docstatus == 1 and flt(si.outstanding_amount) <= 0)


@frappe.whitelist()
def make_sales_invoice(test_request, items=None):
	"""Build a draft Sales Invoice for all, or a chosen subset, of the request's items."""
	tr = frappe.get_doc("Test Request", test_request)
	if tr.docstatus != 1:
		frappe.throw(_("Submit the Test Request before invoicing."))
	_check_no_active_invoice(tr)

	selected = frappe.parse_json(items) if items else [d.item for d in tr.items]
	selected = [i for i in selected if i]
	if not selected:
		frappe.throw(_("Select at least one item to invoice."))

	valid = {d.item for d in tr.items}
	unknown = [i for i in selected if i not in valid]
	if unknown:
		frappe.throw(_("These items are not on the request: {0}").format(", ".join(unknown)))

	si = frappe.new_doc("Sales Invoice")
	si.customer = tr.patient
	si.company = company()
	# Separately-collected invoice: the cashier pays and submits it later; submitting seeds the
	# result table (events.on_test_request_invoice_submit).
	si.is_action_invoice = 1
	for item_code in selected:
		si.append("items", {"item_code": item_code, "qty": 1})
	si.insert()

	frappe.db.set_value("Test Request", tr.name, "sales_invoice", si.name)
	return si.name


def _check_no_active_invoice(tr):
	if not tr.sales_invoice:
		return
	# None => deleted, 2 => cancelled: both free the request to be re-invoiced.
	docstatus = frappe.db.get_value("Sales Invoice", tr.sales_invoice, "docstatus")
	if docstatus in (0, 1):
		frappe.throw(_("An invoice ({0}) already exists for this Test Request.").format(tr.sales_invoice))


@frappe.whitelist()
def start_test(test_request):
	tr = frappe.get_doc("Test Request", test_request)
	tr.status = "Ongoing"
	tr.save()
	return tr.status


@frappe.whitelist()
def complete_test(test_request):
	tr = frappe.get_doc("Test Request", test_request)
	tr.status = "Completed"
	tr.save()
	return tr.status
