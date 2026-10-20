import { defineStore } from "pinia";
import { ref } from "vue";
import { call } from "../client.js";

export const useDefaultsStore = defineStore("defaults", () => {
	const employee = ref(null);
	const loading = ref(false);
	const loaded = ref(false);

	// Callers that need the data (not just a warm cache) await this, so a concurrent
	// call must return the in-flight request rather than resolving immediately.
	let inflight = null;

	function load() {
		if (loaded.value) return Promise.resolve();
		if (inflight) return inflight;

		loading.value = true;
		inflight = (async () => {
			try {
				const result = await call("profile.load_defaults");
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
		employee,
		loading,
		loaded,
		load,
	};
});
