import frappe

# Stored Arabic value -> English key. The Arabic is now the label, from medic/translations/ar.csv.
# Kept literal: a patch must keep doing what it did even if medic.constants changes later.
VALUES = {
	("Patient Appointment", "appointment_status"): {
		"انتظار": "Pending",
		"غير مؤكد": "Unconfirmed",
		"مؤكد": "Confirmed",
		"مكتمل": "Completed",
		"ملغي": "Cancelled",
	},
	("Patient Appointment", "appointment_type"): {
		"كشف": "Consultation",
		"علاج": "Treatment",
		"مراجعة": "Review",
		"متابعة دورية": "Follow-up",
	},
	("Appointment Actions", "action_type"): {
		"علاج": "Treatment",
		"تحليل": "Lab Test",
		"وصفة طبية": "Prescription",
	},
	("Illness", "illness_type"): {
		"أخرى": "Other",
		"جلدي": "Skin",
	},
}


def execute():
	for (doctype, fieldname), values in VALUES.items():
		table = frappe.qb.DocType(doctype)
		for old, new in values.items():
			frappe.qb.update(table).set(table[fieldname], new).where(table[fieldname] == old).run()
