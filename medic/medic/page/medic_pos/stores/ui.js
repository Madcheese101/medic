import { defineStore } from "pinia";
import { ref } from "vue";

// Cross-view UI intents that outlive a single component (e.g. the app-bar asking
// the Appointments view to open its create form).
export const useUiStore = defineStore("ui", () => {
	// null, or { newPatient: boolean, customer: { name, customer_name } | null } requesting the
	// New Appointment form be opened, for that existing patient when one is given.
	const pendingAppointment = ref(null);

	function requestNewAppointment(newPatient, customer = null) {
		pendingAppointment.value = { newPatient: !!newPatient, customer };
	}

	function consumeNewAppointment() {
		const req = pendingAppointment.value;
		pendingAppointment.value = null;
		return req;
	}

	return { pendingAppointment, requestNewAppointment, consumeNewAppointment };
});
