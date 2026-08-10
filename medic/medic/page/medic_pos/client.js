const API = "medic.medic.page.medic_pos.api";

// Resolves to the method's return value. Frappe already shows a dialog for server
// errors before rejecting, so callers must not report the error a second time.
export async function call(method, args = {}) {
	const r = await frappe.call({ method: `${API}.${method}`, args });
	return r.message;
}

export function customSearchLink(doctype, txt, filters = {}) {
	// Autocomplete fires per keystroke - degrade to an empty list instead of a dialog.
	return call("custom_search_link", { doctype, txt: txt || "", page_length: 20, filters })
		.then((rows) => rows || [])
		.catch(() => []);
}

export function notifySuccess(message) {
	frappe.show_alert({ message, indicator: "green" });
}

// Native Frappe confirm dialog as a promise. Resolves true on Yes, false otherwise.
export function confirmAction(message) {
	return new Promise((resolve) => {
		frappe.confirm(
			message,
			() => resolve(true),
			() => resolve(false)
		);
	});
}

export function formatCurrency(value, currency) {
	// Frappe exposes format_currency as a global (returns a plain string);
	// frappe.format(Currency) instead returns an HTML <div>, so avoid it.
	return window.format_currency(value || 0, currency);
}
