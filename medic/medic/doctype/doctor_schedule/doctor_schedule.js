// Copyright (c) 2026, Nawa Clinic and contributors
// For license information, please see license.txt

frappe.ui.form.on("Doctor Schedule", {
	refresh(frm) {
		if (frm.doc.__islocal && !frm.doc.schedule?.length) {
			frm.call("fill_table").then(() => {
				frm.refresh_field("schedule");
			});
		}
	},
});
