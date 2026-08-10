<template>
	<v-app class="medic-pos">
		<v-navigation-drawer
			v-model="drawer"
			:permanent="!mobile"
			:temporary="mobile"
			:rail="rail && !mobile"
			width="260"
			color="surface"
		>
			<v-list nav density="comfortable">
				<v-list-subheader v-if="!rail || mobile">{{ __("Application") }}</v-list-subheader>
				<v-list-item
					v-for="item in navItems"
					:key="item.value"
					:active="activeView === item.value"
					:prepend-icon="item.icon"
					:title="__(item.title)"
					@click="selectView(item.value)"
				/>
			</v-list>

			<template #append>
				<v-list nav density="comfortable">
					<v-list-item
						:active="activeView === 'profile'"
						prepend-icon="mdi-cog-outline"
						:title="__('Profile')"
						@click="selectView('profile')"
					/>
				</v-list>
			</template>
		</v-navigation-drawer>

		<v-app-bar flat color="primary" density="comfortable">
			<template #prepend>
				<v-app-bar-nav-icon @click="toggleDrawer" />
			</template>

			<v-app-bar-title class="text-truncate font-weight-bold">
				<v-icon icon="mdi-hospital-box-outline" class="mr-2" />
				{{ __("Medic") }}
			</v-app-bar-title>

			<v-spacer />

			<v-menu location="bottom end">
				<template #activator="{ props }">
					<v-btn v-bind="props" variant="text" class="text-none px-2">
						<v-avatar size="32" color="surface" class="mr-2">
							<v-img v-if="profileImage" :src="profileImage" :alt="fullName" />
							<span v-else class="text-primary font-weight-bold">{{ initials }}</span>
						</v-avatar>
						<span class="d-none d-sm-inline">{{ fullName }}</span>
						<v-icon icon="mdi-chevron-down" class="ml-1" />
					</v-btn>
				</template>
				<v-list density="comfortable" min-width="180">
					<v-list-item
						prepend-icon="mdi-account-outline"
						:title="__('Profile')"
						@click="selectView('profile')"
					/>
					<v-list-item
						prepend-icon="mdi-calendar-clock"
						:title="__('Schedule')"
						@click="selectView('schedule')"
					/>
					<v-divider />
					<v-list-item prepend-icon="mdi-logout" :title="__('Logout')" @click="logout" />
				</v-list>
			</v-menu>
		</v-app-bar>

		<v-main>
			<v-container fluid class="pa-3 pa-sm-6">
				<component
					:is="activeComponent"
					:key="activeView"
					v-bind="viewParams"
					@navigate="selectView"
					@back="goBack"
				/>
			</v-container>
		</v-main>
	</v-app>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useDisplay } from "vuetify";
import { useDefaultsStore } from "./stores/defaults.js";
import PatientsView from "./views/PatientsView.vue";
import PatientView from "./views/PatientView.vue";
import AppointmentsView from "./views/AppointmentsView.vue";
import AppointmentView from "./views/AppointmentView.vue";
import TreatmentsView from "./views/TreatmentsView.vue";
import ProfileView from "./views/ProfileView.vue";
import ScheduleView from "./views/ScheduleView.vue";

const defaultsStore = useDefaultsStore();
const { mobile } = useDisplay();
const drawer = ref(true);
const rail = ref(false);

const fullName = computed(() => frappe.session.user_fullname || frappe.session.user);
const profileImage = ref(frappe.boot.user_info?.[frappe.session.user]?.image || null);
const initials = computed(() => (fullName.value || "?").trim().charAt(0).toUpperCase());

const navItems = [
	{ value: "patients", title: "Patients", icon: "mdi-account-injury-outline" },
	{ value: "appointments", title: "Appointments", icon: "mdi-calendar-check-outline" },
	{ value: "treatments", title: "Treatments", icon: "mdi-clipboard-pulse-outline" },
];

const activeView = ref("patients");
const viewParams = ref({});
// Visited entries, so each view's back button returns where the user came from.
const history = ref([]);
// `patient` is reachable only per-patient, so it stays out of navItems.
const componentMap = shallowRef({
	patients: PatientsView,
	patient: PatientView,
	appointments: AppointmentsView,
	appointment: AppointmentView,
	treatments: TreatmentsView,
	profile: ProfileView,
	schedule: ScheduleView,
});

const activeComponent = computed(() => componentMap.value[activeView.value]);

function selectView(value, params = {}) {
	if (value !== activeView.value) {
		history.value.push({ view: activeView.value, params: viewParams.value });
	}
	activeView.value = value;
	viewParams.value = params;
	if (mobile.value) drawer.value = false;
}

function goBack() {
	const previous = history.value.pop();
	if (!previous) return;
	activeView.value = previous.view;
	viewParams.value = previous.params;
}

// On mobile the button opens/closes the drawer; on desktop it collapses it to a rail.
function toggleDrawer() {
	if (mobile.value) {
		drawer.value = !drawer.value;
	} else {
		rail.value = !rail.value;
	}
}

function logout() {
	frappe.app.logout();
}

// Start collapsed on small screens.
watch(
	mobile,
	(isMobile) => {
		drawer.value = !isMobile;
	},
	{ immediate: true }
);

onMounted(() => {
	// Scope the z-index override (below) to this page only.
	document.body.classList.add("medic-pos-active");
	defaultsStore.load();
});

onBeforeUnmount(() => {
	document.body.classList.remove("medic-pos-active");
});
</script>

<style>
/* Font applies to the app shell and to teleported overlays (dialogs render
   in .v-overlay-container, outside .medic-pos). */
.medic-pos.v-application,
.v-overlay-container {
	font-family: "IBM Plex Sans Arabic", "Segoe UI", sans-serif;
}

.medic-pos .v-table,
.medic-pos .v-data-table {
	font-variant-numeric: tabular-nums;
}

/* Frappe's native modals (frappe.confirm / msgprint) are Bootstrap dialogs that
   sit below Vuetify's overlays. Lift them above so confirmations are visible. */
body.medic-pos-active .modal-backdrop {
	z-index: 2600 !important;
}

body.medic-pos-active .modal {
	z-index: 2610 !important;
}
</style>
