// Copyright (c) 2026, Nawa Clinic and contributors
// For license information, please see license.txt

frappe.ui.form.on("Clinic Setup", {
	enable_pharmacy(frm) {
		if (!frm.doc.enable_pharmacy) {
			frm.set_value("pharmacy_item_group", 1);
		}
	},
	enable_test_lab(frm) {
		if (!frm.doc.enable_test_lab) {
			frm.set_value("test_lab_item_group", 1);
		}
	},
});
