// Copyright (c) 2026, Nawa Clinic and contributors
// For license information, please see license.txt
frappe.ui.form.on("Patient Appointment", {
	refresh(frm) {
		const service_type_filters = {is_group: 1};
		if (frappe.boot.parent_service)
			service_type_filters["parent_item_group"] = frappe.boot.parent_service;

		frm.set_query('service_type', () => {
			return {
				filters: service_type_filters
			}
		});

		// Creates the appointment's draft invoice (Pending -> Not Confirmed).
		if (frm.doc.docstatus === 1 && frm.doc.appointment_status === "Pending") {
			frm.add_custom_button(__("Confirm Appointment"), () => {
				frm.call("confirm_appointment").then(() => frm.reload_doc());
			});
		}
	},
	service_type(frm) {
		// Your code here
		if(!frm.doc.service_type){
			frm.set_value('service', null);
			frm.set_df_property('service', 'read_only', 1)
			return;
		}

		frm.set_df_property('service', 'read_only', 0);
		frm.set_query('service', () => {
			return {
				filters: {item_group: frm.doc.service_type}
			}
		});
	},
	service(frm) {
		// Your code here
	},
});
