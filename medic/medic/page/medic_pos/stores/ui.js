import { defineStore } from "pinia";
import { ref } from "vue";

// Cross-view UI intents that outlive a single component (e.g. the app-bar asking
// the Appointments view to open its create form, or a reference link opening a
// detail dialog mounted once at the app root).
export const useUiStore = defineStore("ui", () => {
	// null, or { newPatient: boolean } requesting the New Appointment form be opened.
	const pendingAppointment = ref(null);

	function requestNewAppointment(newPatient) {
		pendingAppointment.value = { newPatient: !!newPatient };
	}

	function consumeNewAppointment() {
		const req = pendingAppointment.value;
		pendingAppointment.value = null;
		return req;
	}

	// Reference detail dialogs, mounted once at the app root so any view can open
	// them for its invoice / treatment-plan reference fields.
	const treatmentDetail = ref({ open: false, name: null });
	const invoiceDetail = ref({ open: false, name: null });

	function openTreatmentPlan(name) {
		if (name) treatmentDetail.value = { open: true, name };
	}

	function openInvoice(name) {
		if (name) invoiceDetail.value = { open: true, name };
	}

	function closeReferenceDialogs() {
		treatmentDetail.value = { ...treatmentDetail.value, open: false };
		invoiceDetail.value = { ...invoiceDetail.value, open: false };
	}

	return {
		pendingAppointment,
		requestNewAppointment,
		consumeNewAppointment,
		treatmentDetail,
		invoiceDetail,
		openTreatmentPlan,
		openInvoice,
		closeReferenceDialogs,
	};
});
