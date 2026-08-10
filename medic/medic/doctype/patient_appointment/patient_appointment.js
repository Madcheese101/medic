// Copyright (c) 2026, Nawa Clinic and contributors
// For license information, please see license.txt
const service_type_filters = {is_group: 1};
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

		frm.add_custom_button(
			__("Confirm Appointment"),
				() => {
					frm.call("confirm_appointment").then((r) => {
						frm.reload_doc();
						frm.refresh();
					});
				}
		);

		frm.add_custom_button(
			__("Sales Invoice"),
				() => {
					pick_services(frm, "create_sales_invoice", "Sales Invoice");
				},
				__("Create")
		);

		frm.add_custom_button(
			__("Procedure Appointment"),
				() => {
					pick_services(frm, "create_procedure_appointment", "Procedure Appointment");
				},
				__("Create")
		);
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

	pick_services(frm, method, title) {
		var diag = new frappe.ui.Dialog({
			title: __(title + " Services"),
			size: "large",
			fields: [
				{
					fieldname: "service_type",
					fieldtype: "Link",
					options: "Item Group",
					label: __("Service Type"),
					query: () => {
						return {
							filters: service_type_filters
						}
					}
				},
				{
					fieldname: "service",
					fieldtype: "Link",
					options: "Item",
					label: __("Service"),
				},
				{
					fieldname: "discount_amount",
					fieldtype: "float",
					label: __("Discount"),
				}
				// {
				// 	fieldname: "services",
				// 	fieldtype: "Table",
				// 	fields: [
				// 		{
				// 			fieldname: "service_type",
				// 			fieldtype: "Link",
				// 			options: "Item Group",
				// 			label: __("Service Type"),
				// 			query: () => {
				// 				return {
				// 					filters: service_type_filters
				// 				}
				// 			}
				// 		},
				// 		{
				// 			fieldname: "service",
				// 			fieldtype: "Link",
				// 			options: "Item",
				// 			label: __("Service"),
				// 		},
				// 		{
				// 			fieldname: "discount_amount",
				// 			fieldtype: "float",
				// 			label: __("Discount"),
				// 		}

				// 	],
				// }
			],
			primary_action_label: __("Create"),
			primary_action(args) {
				frm.call(method, {
					service: args.service,
					discount_amount: args.discount_amount
				});
				diag.hide();
			},
			secondary_action_label: __("Cancel"),
			secondary_action(args) {
				diag.hide();
			}
		});
		diag.show();
	},
});
