// Copyright (c) 2026, Nawa Clinic and contributors
// For license information, please see license.txt

frappe.ui.form.on("Test Request", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		const { status, sales_invoice } = frm.doc;

		if (sales_invoice) {
			frm.add_custom_button(__("View Invoice"), () =>
				frappe.set_route("Form", "Sales Invoice", sales_invoice)
			);
		}
		if (status === "Pending" && !sales_invoice) {
			frm.add_custom_button(__("Create Invoice"), () => create_invoice(frm));
		}
		if (status === "Pending" && sales_invoice) {
			frm.add_custom_button(__("Start Test"), () =>
				run(frm, "start_test", __("Start this test?"))
			);
		}
		if (status === "Ongoing") {
			frm.add_custom_button(__("Mark Completed"), () =>
				run(frm, "complete_test", __("Mark this test as completed?"))
			);
		}
	},
});

function run(frm, method, confirm_msg) {
	frappe.confirm(confirm_msg, () => {
		frappe
			.call({
				method: `medic.medic.doctype.test_request.test_request.${method}`,
				args: { test_request: frm.doc.name },
				freeze: true,
			})
			.then(() => frm.reload_doc());
	});
}

function create_invoice(frm) {
	const item_codes = (frm.doc.items || []).map((d) => d.item);
	frappe.db
		.get_list("Item", { filters: { name: ["in", item_codes] }, fields: ["name", "item_name"], limit: 0 })
		.then((records) => {
			const name_map = Object.fromEntries(records.map((r) => [r.name, r.item_name]));
			// All items checked by default; the lab tech can uncheck any to exclude them.
			const rows = item_codes.map((code) => ({
				item: code,
				item_name: name_map[code] || "",
				__checked: 1,
			}));
			open_invoice_dialog(frm, rows);
		});
}

function open_invoice_dialog(frm, rows) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create Invoice"),
		fields: [
			{
				fieldname: "help",
				fieldtype: "HTML",
				options: `<p class="text-muted">${__("Uncheck any item you don't want to invoice.")}</p>`,
			},
			{
				fieldname: "items",
				fieldtype: "Table",
				label: __("Items"),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: false,
				data: rows,
				get_data: () => rows,
				fields: [
					{
						fieldname: "item",
						fieldtype: "Data",
						label: __("Item"),
						in_list_view: 1,
						read_only: 1,
					},
					{
						fieldname: "item_name",
						fieldtype: "Data",
						label: __("Item Name"),
						in_list_view: 1,
						read_only: 1,
					},
				],
			},
		],
		primary_action_label: __("Create"),
		primary_action() {
			const checked = (dialog.fields_dict.items.grid.get_selected_children() || []).map(
				(r) => r.item
			);
			const items = checked.length ? checked : rows.map((r) => r.item);
			frappe
				.call({
					method: "medic.medic.doctype.test_request.test_request.make_sales_invoice",
					args: { test_request: frm.doc.name, items },
					freeze: true,
				})
				.then((r) => {
					dialog.hide();
					frm.reload_doc();
					if (r.message) frappe.set_route("Form", "Sales Invoice", r.message);
				});
		},
	});
	dialog.show();
}
