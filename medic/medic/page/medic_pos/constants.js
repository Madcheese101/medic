// Mirrors the Blood Type custom field options on Customer (medic/fixtures/custom_field.json).
export const BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

// Mirrors the Patient Appointment doctype Select options.
export const APPOINTMENT_TYPES = ["كشف", "علاج", "مراجعة", "متابعة دورية"];
export const APPOINTMENT_STATUS = ["انتظار", "غير مؤكد", "مؤكد", "مكتمل"];

// انتظار Pending, غير مؤكد Not Confirmed, مؤكد Confirmed, مكتمل Completed.
export function appointmentStatusColor(status) {
	return { انتظار: "warning", "غير مؤكد": "info", مؤكد: "success", مكتمل: "primary" }[status] || "surface-variant";
}

export function treatmentStatusColor(status) {
	return { Active: "primary", Completed: "success", Cancelled: "error" }[status] || "surface-variant";
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
