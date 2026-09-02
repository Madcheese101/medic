const API = "medic.medic.page.medic_pos.api";

// Resolves to the method's return value. Frappe already shows a dialog for server
// errors before rejecting, so callers must not report the error a second time.
export async function call(method, args = {}) {
	const r = await frappe.call({ method: `${API}.${method}`, args });
	return r.message;
}

// `labelFieldname` asks the server to attach that field's value to each row as `label`.
export function customSearchLink(doctype, txt, filters = {}, labelFieldname = null) {
	// Autocomplete fires per keystroke - degrade to an empty list instead of a dialog.
	return call("custom_search_link", {
		doctype,
		txt: txt || "",
		page_length: 20,
		filters,
		label_fieldname: labelFieldname,
	})
		.then((rows) => rows || [])
		.catch(() => []);
}

// The label is repeated as the first part of `description`, so drop it - a subtitle that only
// echoes the title is noise. Returns undefined when nothing else is left to show.
function subtitleFor(row, labelFieldname) {
	const label = (row.label || "").trim();
	const parts = (row.description || "")
		.split(",")
		.map((part) => part.trim())
		.filter((part) => part && part !== label);

	// Any label other than `name` leaves the id off the title, so surface it here instead -
	// unless the record is autonamed after that same label and would only repeat the title.
	const showId = labelFieldname && labelFieldname !== "name" && row.value !== label;
	if (showId && !parts.includes(row.value)) parts.unshift(row.value);

	return parts.join(" · ") || undefined;
}

// Link search results as v-autocomplete items. Needs `item-props` on the field for the
// subtitle to render.
export async function searchLinkOptions(doctype, txt, filters = {}, labelFieldname = null) {
	const rows = await customSearchLink(doctype, txt, filters, labelFieldname);
	return rows.map((r) => ({
		title: r.label || r.value,
		subtitle: subtitleFor(r, labelFieldname),
		value: r.value,
	}));
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

// Opens the standalone print view in a new tab. Omitting `format` makes Frappe
// use the doctype's default print format; trigger_print fires the print dialog.
export function printDoc(doctype, name) {
	if (!name) return;
	const params = new URLSearchParams({
		doctype,
		name,
		trigger_print: "1",
		no_letterhead: "0",
		_lang: frappe.boot.lang || "en",
	});
	window.open(`/printview?${params.toString()}`, "_blank");
}

export function formatCurrency(value, currency) {
	// Frappe exposes format_currency as a global (returns a plain string);
	// frappe.format(Currency) instead returns an HTML <div>, so avoid it.
	return window.format_currency(value || 0, currency);
}
