import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { call } from "../client.js";

export const useDefaultsStore = defineStore("defaults", () => {
	const posProfile = ref(null);
	const roles = ref([]);
	const employee = ref(null);
	const loading = ref(false);
	const loaded = ref(false);

	const posProfileName = computed(() => posProfile.value?.name || null);
	const currency = computed(() => posProfile.value?.currency || null);
	const employeeName = computed(() => employee.value?.employee_name || null);
	const isDoctor = computed(() => !!employee.value);

	function hasRole(role) {
		return roles.value.includes(role);
	}

	// Callers that need the data (not just a warm cache) await this, so a concurrent
	// call must return the in-flight request rather than resolving immediately.
	let inflight = null;

	function load() {
		if (loaded.value) return Promise.resolve();
		if (inflight) return inflight;

		loading.value = true;
		inflight = (async () => {
			try {
				const result = await call("load_defaults");
				// pos_profile is null when the user has none configured - not an error.
				posProfile.value = result.pos_profile;
				roles.value = result.roles || [];
				employee.value = result.employee;
				loaded.value = true;
			} finally {
				loading.value = false;
				inflight = null;
			}
		})();

		return inflight;
	}

	return {
		posProfile,
		roles,
		employee,
		loading,
		loaded,
		posProfileName,
		currency,
		employeeName,
		isDoctor,
		hasRole,
		load,
	};
});
