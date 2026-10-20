import { reactive, ref } from "vue";
import { call } from "./client.js";

// State for a v-data-table-server backed by a paged list endpoint, which takes the list's
// filters (`args()`) plus start / page_length / sort_by / sort_order and returns { rows, total }.
// Bind it with v-model:page="table.page", :items="table.rows", :items-length="table.total",
// :loading="table.loading" and @update:options="table.onOptions".
export function useServerTable(method, args = () => ({})) {
	const rows = ref([]);
	const total = ref(0);
	const loading = ref(false);
	const page = ref(1);
	let itemsPerPage = 10;
	let sortBy = [];
	// Only the latest request may fill the table; an earlier one can answer after it.
	let latest = 0;

	async function load() {
		const request = ++latest;
		loading.value = true;
		try {
			const result = await call(method, {
				...args(),
				start: (page.value - 1) * itemsPerPage,
				page_length: itemsPerPage,
				sort_by: sortBy[0]?.key,
				sort_order: sortBy[0]?.order,
			});
			if (request !== latest) return;
			rows.value = result.rows;
			total.value = result.total;
		} finally {
			if (request === latest) loading.value = false;
		}
	}

	// The table emits its options on mount and on every page, page size or sort change.
	function onOptions(options) {
		page.value = options.page;
		itemsPerPage = options.itemsPerPage;
		sortBy = options.sortBy;
		load();
	}

	// New filters start again from the first page. Moving the table there emits its options,
	// which loads; on the first page already, load directly.
	function reload() {
		if (page.value === 1) load();
		else page.value = 1;
	}

	return reactive({ rows, total, loading, page, load, reload, onOptions });
}
