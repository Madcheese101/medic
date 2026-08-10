frappe.pages['medic-pos'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Medic POS',
		single_column: true,
	});

	$("head").append(
		"<link href='/assets/medic/node_modules/vuetify/dist/vuetify.min.css' rel='stylesheet'>"
	);
	$("head").append(
		"<link href='/assets/medic/node_modules/@mdi/font/css/materialdesignicons.min.css' rel='stylesheet'>"
	);
	["400", "500", "600", "700"].forEach((weight) => {
		$("head").append(
			`<link href='/assets/medic/node_modules/@fontsource/ibm-plex-sans-arabic/${weight}.css' rel='stylesheet'>`
		);
	});

	this.page.$MedicPos = new frappe.MedicPos.Controller(this.page);
};
