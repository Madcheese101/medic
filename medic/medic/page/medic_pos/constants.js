// Mirrors the Blood Type custom field options on Customer (medic/fixtures/custom_field.json).
export const BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

// Mirrors the Patient Appointment doctype Select options.
export const APPOINTMENT_TYPES = ["كشف", "علاج", "مراجعة", "متابعة دورية"];

// Mirrors the Appointment Actions action_type Select options.
export const ACTION_TYPES = ["علاج", "تحليل", "وصفة طبية"];
export const APPOINTMENT_STATUS = ["انتظار", "غير مؤكد", "مؤكد", "مكتمل", "ملغي"];

// Mirrors the Prescription Items Select options (the blank first route option is dropped).
export const PRESCRIPTION_ROUTES = [
	"Oral",
	"Sublingual",
	"Buccal",
	"Rectal",
	"Vaginal",
	"Intravenous",
	"Intramuscular",
	"Subcutaneous",
	"Intradermal",
	"Intrathecal",
	"Epidural",
	"Intra-articular",
	"Topical",
	"Transdermal",
	"Ophthalmic",
	"Otic",
	"Nasal",
	"Inhalation",
	"Nebulization",
	"Intravesical",
	"Nasogastric",
	"Gastrostomy",
];
export const PRESCRIPTION_PER = ["Day", "Week"];

// انتظار Pending, غير مؤكد Not Confirmed, مؤكد Confirmed, مكتمل Completed, ملغي Cancelled.
export function appointmentStatusColor(status) {
	return { انتظار: "warning", "غير مؤكد": "info", مؤكد: "success", مكتمل: "primary", ملغي: "error" }[status] || "surface-variant";
}

export function treatmentStatusColor(status) {
	return { Pending: "warning", Active: "primary", Completed: "success", Cancelled: "error" }[status] || "surface-variant";
}

export function testRequestStatusColor(status) {
	return { Pending: "warning", Ongoing: "primary", Completed: "success" }[status] || "surface-variant";
}

// Mirrors the Sales Invoice status Select options.
export const SALES_INVOICE_STATUS = [
	"Draft",
	"Unpaid",
	"Overdue",
	"Partly Paid",
	"Paid",
	"Return",
	"Credit Note Issued",
	"Cancelled",
];

export function invoiceStatusColor(status) {
	return (
		{
			Paid: "success",
			Unpaid: "error",
			Overdue: "error",
			"Partly Paid": "warning",
			Draft: "surface-variant",
			Return: "info",
			"Credit Note Issued": "info",
			Cancelled: "error",
		}[status] || "surface-variant"
	);
}
