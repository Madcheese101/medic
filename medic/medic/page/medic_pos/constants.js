// Mirrors the Blood Type custom field options on Customer (medic/fixtures/custom_field.json).
export const BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

// Stored values of the Medic Select fields; mirrors medic/constants.py and the doctype JSON.
export const AppointmentStatus = {
	PENDING: "Pending",
	UNCONFIRMED: "Unconfirmed",
	CONFIRMED: "Confirmed",
	COMPLETED: "Completed",
	CANCELLED: "Cancelled",
};

export const AppointmentType = {
	CONSULTATION: "Consultation",
	TREATMENT: "Treatment",
	REVIEW: "Review",
	FOLLOW_UP: "Follow-up",
};

export const ActionType = {
	TREATMENT: "Treatment",
	LAB_TEST: "Lab Test",
	PRESCRIPTION: "Prescription",
};

export const IllnessType = {
	OTHER: "Other",
	SKIN: "Skin",
};

// A stored Select value as the user reads it. Translations are keyed by the doctype
// (medic/translations/ar.csv), the same context Frappe's own formatter uses.
export function label(value, doctype) {
	return value ? __(value, null, doctype) : "—";
}

const options = (values, doctype) =>
	Object.values(values).map((value) => ({ title: label(value, doctype), value }));

// Labelled options for selects and menus.
export const APPOINTMENT_TYPES = options(AppointmentType, "Patient Appointment");
export const APPOINTMENT_STATUS = options(AppointmentStatus, "Patient Appointment");
export const ACTION_TYPES = options(ActionType, "Appointment Actions");

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

export function appointmentStatusColor(status) {
	return (
		{
			[AppointmentStatus.PENDING]: "warning",
			[AppointmentStatus.UNCONFIRMED]: "info",
			[AppointmentStatus.CONFIRMED]: "success",
			[AppointmentStatus.COMPLETED]: "primary",
			[AppointmentStatus.CANCELLED]: "error",
		}[status] || "surface-variant"
	);
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
