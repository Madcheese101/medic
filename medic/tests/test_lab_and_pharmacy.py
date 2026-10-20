import frappe
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from frappe.utils import flt

from medic.tests.utils import P, MedicTestCase, _item, call


class TestLabTests(MedicTestCase):
	def test_list_shows_the_estimate_before_invoicing(self):
		patient = self.make_patient()
		name = call("lab.create_test_request", patient=patient, items=self.fx.lab_items)

		row = next(r for r in call("lab.list_test_requests", customer=patient)["rows"] if r["name"] == name)
		self.assertEqual(row["patient_name"], frappe.db.get_value("Customer", patient, "customer_name"))
		self.assertEqual(row["item_count"], 2)
		self.assertEqual(row["status"], "Pending")
		self.assertEqual(row["estimated_total"], 50)
		self.assertIsNone(row["sales_invoice"])

	def test_invoice_is_a_draft_action_invoice_and_paying_it_seeds_results(self):
		name = call("lab.create_test_request", patient=self.make_patient(), items=self.fx.lab_items)
		invoice = call("lab.create_test_request_invoice", name=name, items=self.fx.lab_items[:1])

		si = frappe.get_doc("Sales Invoice", invoice)
		self.assertEqual(si.docstatus, 0)
		self.assertEqual(si.is_action_invoice, 1)
		self.assertEqual(si.company, self.fx.company)
		self.assertEqual([i.item_code for i in si.items], self.fx.lab_items[:1])
		self.assertRaises(frappe.ValidationError, call, "lab.create_test_request_invoice", name=name)

		call("appointments.pay_appointment_action", invoice=invoice, payments=[self.cash(30)])
		data = call("lab.get_test_request", name=name)
		self.assertEqual([r["item"] for r in data["result"]], self.fx.lab_items[:1])
		self.assertEqual(data["outstanding_amount"], 0)

	def test_appointment_test_request_tracks_its_invoice(self):
		appointment, _ = self.make_paid_appointment()
		name = call(
			"appointments.create_appointment_test_request", appointment=appointment, items=self.fx.lab_items
		)
		row = next(
			r
			for r in call("appointments.get_appointment", name=appointment)["actions"]
			if r["invoice"] == name
		)
		self.assertEqual(row["invoice_type"], "Test Request")
		self.assertEqual(row["paid"], 0)
		self.assertIsNone(row["sales_invoice"])

		invoice = call("lab.create_test_request_invoice", name=name)
		call("appointments.pay_appointment_action", invoice=invoice, payments=[self.cash(50)])
		row = next(
			r
			for r in call("appointments.get_appointment", name=appointment)["actions"]
			if r["invoice"] == name
		)
		self.assertEqual(row["paid"], 1)
		# The row resolves the test's invoice, so the appointment can show its amounts.
		self.assertEqual(row["sales_invoice"], invoice)
		self.assertEqual(row["grand_total"], 50)


class TestPharmacy(MedicTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_stock_entry(
			item_code=cls.fx.drug, target=cls.fx.warehouse, qty=10, basic_rate=2, company=cls.fx.company
		)

	def stock(self):
		return flt(
			frappe.db.get_value(
				"Bin", {"item_code": self.fx.drug, "warehouse": self.fx.warehouse}, "actual_qty"
			)
		)

	def test_search_returns_price_stock_and_uoms(self):
		lines = call("pos.pos_search_items", context="pharmacy", txt=self.fx.drug)
		line = next(line for line in lines if line["item_code"] == self.fx.drug)
		self.assertEqual(line["price_list_rate"], 5)
		self.assertEqual(line["actual_qty"], self.stock())
		self.assertGreater(line["actual_qty"], 0)
		self.assertEqual(line["is_stock_item"], 1)
		self.assertEqual([u["uom"] for u in line["uoms"]], ["Nos"])

	def test_scanned_barcode_leads_the_results(self):
		barcode = frappe.generate_hash(length=10)
		item = frappe.get_doc("Item", self.fx.drug)
		item.append("barcodes", {"barcode": barcode})
		# Like the fixtures, ignore mandatory custom fields a site may add to Item.
		item.flags.ignore_mandatory = True
		item.save()
		# Named after the barcode, so it matches too and would sort first by name.
		group = frappe.db.get_value("Item", self.fx.drug, "item_group")
		other = _item(f"{P} Aspirin {barcode}", group, 5, self.fx.price_list)

		lines = call("pos.pos_search_items", context="pharmacy", txt=barcode)
		self.assertEqual([line["item_code"] for line in lines], [self.fx.drug, other])

	def test_prescription_checkout(self):
		appointment, _ = self.make_paid_appointment()
		patient = frappe.db.get_value("Patient Appointment", appointment, "customer")
		prescription = call(
			"appointments.create_prescription",
			appointment=appointment,
			items=[{"item": self.fx.drug, "route": "Oral", "times": 2, "per": "Day", "for": 5}],
		)

		listed = call("pos.list_prescriptions", customer=patient)
		self.assertEqual(listed["total"], 1)
		self.assertEqual(listed["rows"][0]["appointment"], appointment)

		cart = call("pos.get_prescription_cart", context="pharmacy", prescription=prescription)
		self.assertEqual(cart["customer"], patient)
		self.assertEqual(cart["items"][0]["item_code"], self.fx.drug)
		self.assertEqual(cart["items"][0]["actual_qty"], self.stock())

		items = [{"item_code": self.fx.drug, "qty": 2, "uom": "Nos", "conversion_factor": 1, "rate": 5}]
		self.assertRaises(
			frappe.ValidationError,
			call,
			"pos.create_pos_invoice",
			context="pharmacy",
			customer=patient,
			items=items,
			payments=[self.cash(5)],
			prescription=prescription,
		)
		result = call(
			"pos.create_pos_invoice",
			context="pharmacy",
			customer=patient,
			items=items,
			payments=[self.cash(10)],
			prescription=prescription,
		)
		self.assertEqual(flt(result["grand_total"]), 10)
		self.assertEqual(frappe.db.get_value("Prescription", prescription, "sales_invoice"), result["name"])
