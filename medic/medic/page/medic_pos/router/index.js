import { createRouter, createWebHistory, createMemoryHistory } from "vue-router";
import PatientsView from "../views/PatientsView.vue";
import PatientView from "../views/PatientView.vue";
import AppointmentsView from "../views/AppointmentsView.vue";
import AppointmentView from "../views/AppointmentView.vue";
import TreatmentsView from "../views/TreatmentsView.vue";
import TreatmentView from "../views/TreatmentView.vue";
import InvoicesView from "../views/InvoicesView.vue";
import InvoiceView from "../views/InvoiceView.vue";
import ProfileView from "../views/ProfileView.vue";
import ScheduleView from "../views/ScheduleView.vue";
import PrescriptionsView from "../views/PrescriptionsView.vue";
import PosView from "../views/PosView.vue";

const ROUTER_STATE_KEYS = ["back", "current", "forward", "position", "replaced", "scroll"];

const hasRouterState = (state) => {
	return Boolean(state) && ROUTER_STATE_KEYS.some((key) => state[key] !== undefined);
};

const preserveRouterHistoryState = () => {
	if (typeof window === "undefined" || window.__medicPosHistoryStatePatched) {
		return;
	}

	const wrapHistoryMethod = (methodName) => {
		const originalMethod = window.history[methodName];

		window.history[methodName] = function patchedHistoryState(state, title, url) {
			const currentState = window.history.state;

			if (!hasRouterState(currentState)) {
				return originalMethod.call(window.history, state, title, url);
			}

			if (state == null) {
				return originalMethod.call(window.history, { ...currentState }, title, url);
			}

			if (typeof state !== "object") {
				return originalMethod.call(window.history, state, title, url);
			}

			const mergedState = { ...currentState, ...state };
			return originalMethod.call(window.history, mergedState, title, url);
		};
	};

	wrapHistoryMethod("replaceState");
	wrapHistoryMethod("pushState");
	window.__medicPosHistoryStatePatched = true;
};

preserveRouterHistoryState();

const routes = [
	{
		path: "/",
		// name: "Patients",
		// component: PatientsView
		redirect: "/app/medic-pos",
	},
	{
		path: "/app/medic-pos",
		name: "patients",
		component: PatientsView,
		// props: true
		// redirect: '/'
	},
	{
		path: "/app/medic-pos/patient/:patient?",
		name: "patient",
		component: PatientView,
	},
	{
		path: "/app/medic-pos/appointments",
		name: "appointments",
		component: AppointmentsView,
	},
	{
		path: "/app/medic-pos/appointment/:name?",
		name: "appointment",
		component: AppointmentView,
	},
	{
		path: "/app/medic-pos/treatments",
		name: "treatments",
		component: TreatmentsView,
	},
	{
		path: "/app/medic-pos/treatment/:name?",
		name: "treatment",
		component: TreatmentView,
	},
	{
		path: "/app/medic-pos/invoices",
		name: "invoices",
		component: InvoicesView,
	},
	{
		path: "/app/medic-pos/invoice/:name?",
		name: "invoice",
		component: InvoiceView,
	},
	{
		path: "/app/medic-pos/pharmacy/prescriptions",
		name: "pharmacy-prescriptions",
		component: PrescriptionsView,
	},
	{
		path: "/app/medic-pos/pharmacy/pos/:prescription?",
		name: "pharmacy-pos",
		component: PosView,
	},
	{
		path: "/app/medic-pos/profile",
		name: "profile",
		component: ProfileView,
	},
	{
		path: "/app/medic-pos/schedule",
		name: "schedule",
		component: ScheduleView,
	},
];

const router = createRouter({
	history: createWebHistory(),
	// abstract: createMemoryHistory(),
	routes: routes,
});

export default router;
