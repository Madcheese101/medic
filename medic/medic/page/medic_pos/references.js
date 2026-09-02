import { useRouter } from "vue-router";
import { useUiStore } from "./stores/ui.js";

// Opens the detail view for a reference field, from anywhere in the app:
// appointments navigate to their own route; invoices and treatment plans open
// the shared dialogs mounted at the app root.
export function useReferences() {
	const router = useRouter();
	const uiStore = useUiStore();

	function openAppointment(name) {
		if (!name) return;
		// Navigating away replaces the current view, so drop any open reference dialogs first.
		uiStore.closeReferenceDialogs();
		router.push({ name: "appointment", params: { name } }).catch(() => {});
	}

	return {
		openAppointment,
		openInvoice: uiStore.openInvoice,
		openTreatmentPlan: uiStore.openTreatmentPlan,
	};
}
