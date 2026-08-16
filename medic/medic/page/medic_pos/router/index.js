import { createRouter, createWebHistory } from "vue-router";
import PatientsView from "../views/PatientsView.vue";
import PatientView from "../views/PatientView.vue";
import AppointmentsView from "../views/AppointmentsView.vue";
import AppointmentView from "../views/AppointmentView.vue";
import TreatmentsView from "../views/TreatmentsView.vue";
import ProfileView from "../views/ProfileView.vue";
import ScheduleView from "../views/ScheduleView.vue";

// Frappe desk runs its own history-based router and keeps routing metadata on
// `history.state`. vue-router's createWebHistory overwrites that state on every
// push/replace, which wipes Frappe's keys and breaks desk back/forward. Patch the
// history methods once to MERGE onto Frappe's state instead of replacing it, so
// both routers coexist and the URL bar can reflect our route.
const ROUTER_STATE_KEYS = ["back", "current", "forward", "position", "replaced", "scroll"];

const hasRouterState = (state) =>
	Boolean(state) && ROUTER_STATE_KEYS.some((key) => state[key] !== undefined);

const preserveRouterHistoryState = () => {
	if (typeof window === "undefined" || window.__medicPosHistoryStatePatched) return;

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
			return originalMethod.call(window.history, { ...currentState, ...state }, title, url);
		};
	};

	wrapHistoryMethod("replaceState");
	wrapHistoryMethod("pushState");
	window.__medicPosHistoryStatePatched = true;
};

preserveRouterHistoryState();

// The page is mounted by Frappe at <desk>/medic-pos (e.g. /app/medic-pos). Derive
// the base from the current URL so our routes hang off it and survive a refresh,
// whether the desk prefix is /app or /desk.
const PAGE_NAME = "medic-pos";
const pathname = window.location.pathname;
const nameAt = pathname.indexOf(PAGE_NAME);
const base = nameAt >= 0 ? pathname.slice(0, nameAt + PAGE_NAME.length) : `/app/${PAGE_NAME}`;

// `patient` / `appointment` carry the record id and are reachable only from their
// list view, so they stay out of the nav drawer. Their id param is optional so the
// route still resolves when opened without one.
const routes = [
	{ path: "/", redirect: { name: "patients" } },
	{ path: "/patients", name: "patients", component: PatientsView },
	{ path: "/patient/:patient?", name: "patient", component: PatientView },
	{ path: "/appointments", name: "appointments", component: AppointmentsView },
	{ path: "/appointment/:name?", name: "appointment", component: AppointmentView },
	{ path: "/treatments", name: "treatments", component: TreatmentsView },
	{ path: "/profile", name: "profile", component: ProfileView },
	{ path: "/schedule", name: "schedule", component: ScheduleView },
];

const router = createRouter({
	history: createWebHistory(base),
	routes,
});

export default router;
