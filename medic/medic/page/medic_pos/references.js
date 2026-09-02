import { useRouter } from "vue-router";

// Opens the detail view for a reference field, from anywhere in the app.
// Each reference type has its own routed view (mirroring the appointment view).
export function useReferences() {
	const router = useRouter();

	function push(name, recordName) {
		if (recordName) router.push({ name, params: { name: recordName } }).catch(() => {});
	}

	return {
		openAppointment: (name) => push("appointment", name),
		openInvoice: (name) => push("invoice", name),
		openTreatmentPlan: (name) => push("treatment", name),
	};
}
