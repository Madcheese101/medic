import random

from medic.tests.utils import P, MedicTestCase, call


class TestPatients(MedicTestCase):
	def create(self, customer_name, phone_number="+218912345678"):
		return call(
			"patients.create_patient",
			customer_name=customer_name,
			date_of_birth="1990-01-01",
			phone_number=phone_number,
			gender="Male",
		)

	def test_list_pages_and_sorts(self):
		prefix = f"{P} List {random.randint(10000, 99999)}"
		names = [self.create(f"{prefix} {letter}") for letter in "CAB"]

		page = call(
			"patients.get_patients",
			customer_name=prefix,
			page_length=2,
			sort_by="customer_name",
			sort_order="asc",
		)
		self.assertEqual(page["total"], 3)
		self.assertEqual([r["customer_name"] for r in page["rows"]], [f"{prefix} A", f"{prefix} B"])
		rest = call("patients.get_patients", customer_name=prefix, start=2, page_length=2)
		self.assertEqual(len(rest["rows"]), 1)
		self.assertIn(rest["rows"][0]["name"], names)
