import { defineStore } from "pinia";
import { ref } from "vue";

// Cross-view UI intents that outlive a single component (e.g. the app-bar asking
// the Appointments view to open its create form).
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

	return { pendingAppointment, requestNewAppointment, consumeNewAppointment };
});
