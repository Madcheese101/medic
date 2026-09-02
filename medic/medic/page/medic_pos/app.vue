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
				<template v-for="item in navItems" :key="item.value">
					<v-list-group v-if="item.children" :value="item.value">
						<template #activator="{ props }">
							<v-list-item
								v-bind="props"
								:prepend-icon="item.icon"
								:title="__(item.title)"
							/>
						</template>
						<v-list-item
							v-for="child in item.children"
							:key="child.value"
							:active="activeView === child.value"
							:prepend-icon="child.icon"
							:title="__(child.title)"
							@click="selectView(child.value)"
						/>
					</v-list-group>
					<v-list-item
						v-else
						:active="activeView === item.value"
						:prepend-icon="item.icon"
						:title="__(item.title)"
						@click="selectView(item.value)"
					/>
				</template>
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
					<v-btn
						v-bind="props"
						variant="text"
						class="text-none px-2 mr-1"
						prepend-icon="mdi-calendar-plus"
						append-icon="mdi-chevron-down"
					>
						<span class="d-none d-sm-inline">{{ __("New") }}</span>
					</v-btn>
				</template>
				<v-list density="comfortable" min-width="220">
					<v-list-item
						prepend-icon="mdi-account-plus-outline"
						:title="__('Create Direct appointment')"
						@click="createAppointment(true)"
					/>
					<v-list-item
						prepend-icon="mdi-calendar-plus"
						:title="__('Create Appointment')"
						@click="createAppointment(false)"
					/>
				</v-list>
			</v-menu>

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
				<router-view v-slot="{ Component, route }">
					<component
						:is="Component"
						:key="route.fullPath"
						v-bind="route.params"
						@navigate="selectView"
						@back="goBack"
					/>
				</router-view>
			</v-container>
		</v-main>
	</v-app>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { useDefaultsStore } from "./stores/defaults.js";
import { useUiStore } from "./stores/ui.js";

const defaultsStore = useDefaultsStore();
const uiStore = useUiStore();
const { mobile } = useDisplay();
const drawer = ref(true);
const rail = ref(false);

const fullName = computed(() => frappe.session.user_fullname || frappe.session.user);
const profileImage = ref(frappe.boot.user_info?.[frappe.session.user]?.image || null);
const initials = computed(() => (fullName.value || "?").trim().charAt(0).toUpperCase());

const navItems = computed(() => {
	const items = [
		{ value: "patients", title: "Patients", icon: "mdi-account-injury-outline" },
		{ value: "appointments", title: "Appointments", icon: "mdi-calendar-check-outline" },
		{ value: "treatments", title: "Treatments", icon: "mdi-clipboard-pulse-outline" },
		{ value: "invoices", title: "Invoices", icon: "mdi-receipt-text-outline" },
	];
	// Pharmacy section only when the clinic has pharmacy configured.
	if (frappe.boot.pharmacy_item_group) {
		items.push({
			value: "pharmacy",
			title: "Pharmacy",
			icon: "mdi-medical-bag",
			children: [
				{ value: "pharmacy-prescriptions", title: "Prescription", icon: "mdi-prescription" },
				{ value: "pharmacy-pos", title: "POS", icon: "mdi-cash-register" },
			],
		});
	}
	return items;
});

const router = useRouter();
const route = useRoute();
// Route name drives nav-item highlighting; the router owns the current view.
const activeView = computed(() => route.name);

function selectView(value, params = {}) {
	// Navigating to the current route resolves to a failure instead of rejecting;
	// swallow it so it never surfaces as an unhandled rejection.
	router.push({ name: value, params }).catch(() => {});
	if (mobile.value) drawer.value = false;
}

function goBack() {
	router.back();
}

// Ask the Appointments view to open its create form; newPatient presets "Is new Patient".
function createAppointment(newPatient) {
	uiStore.requestNewAppointment(newPatient);
	selectView("appointments");
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

/* Clickable reference values in tables. */
.medic-ref-link {
	color: rgb(var(--v-theme-primary));
	cursor: pointer;
}
.medic-ref-link:hover {
	text-decoration: underline;
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
