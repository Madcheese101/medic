// Mirrors the Blood Type custom field options on Customer (medic/fixtures/custom_field.json).
export const BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

// Mirrors the Patient Appointment doctype Select options.
export const APPOINTMENT_TYPES = ["كشف", "علاج", "مراجعة", "متابعة دورية"];
export const APPOINTMENT_STATUS = ["انتظار", "غير مؤكد", "مؤكد"];

// انتظار Pending, غير مؤكد Not Confirmed, مؤكد Confirmed.
export function appointmentStatusColor(status) {
	return { انتظار: "warning", "غير مؤكد": "info", مؤكد: "success" }[status] || "surface-variant";
}
