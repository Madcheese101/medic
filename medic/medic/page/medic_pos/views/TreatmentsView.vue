<template>
	<v-card>
		<v-card-text class="d-flex flex-wrap align-center ga-3">
			<v-autocomplete
				v-model="filters.customer"
				:items="customerOptions"
				:label="__('Patient')"
				prepend-inner-icon="mdi-account-outline"
				clearable
				item-props
				style="max-width: 220px"
				@update:search="searchCustomers"
				@update:model-value="load"
			/>
			<v-autocomplete
				v-model="filters.employee"
				:items="employeeOptions"
				:label="__('Doctor')"
				prepend-inner-icon="mdi-doctor"
				clearable
				item-props
				style="max-width: 220px"
				@update:search="searchEmployees"
				@update:model-value="load"
			/>
			<v-select
				v-model="filters.status"
				:items="['Active', 'Completed', 'Cancelled']"
				:label="__('Status')"
				clearable
				style="max-width: 180px"
				@update:model-value="load"
			/>
			<v-btn color="primary" variant="tonal" icon="mdi-filter-outline" :title="__('Apply filters')" @click="load" />
			<v-spacer />
			<v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="newOpen = true">
				{{ __("New Treatment") }}
			</v-btn>
		</v-card-text>

		<v-data-table
			:headers="headers"
			:items="rows"
			:loading="loading"
			density="comfortable"
			:no-data-text="__('No treatment plans found')"
		>
			<template #item.status="{ item }">
				<v-chip size="small" variant="tonal" :color="treatmentStatusColor(item.status)">{{ item.status }}</v-chip>
			</template>
			<template #item.sessions="{ item }">{{ item.completed_sessions || 0 }} / {{ item.total_sessions }}</template>
			<template #item.paid="{ item }">{{ Math.round((item.paid_pct || 0) * 100) }}%</template>
			<template #item.actions="{ item }">
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-eye"
					:title="__('Open')"
					@click="openPlan(item.name)"
				/>
			</template>
		</v-data-table>
	</v-card>

	<NewTreatmentDialog v-model="newOpen" @created="load" />
	<TreatmentDialog v-model="detailOpen" :name="selected" @changed="load" />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { call, searchLinkOptions } from "../client.js";
import { treatmentStatusColor } from "../constants.js";
import NewTreatmentDialog from "../components/NewTreatmentDialog.vue";
import TreatmentDialog from "../components/TreatmentDialog.vue";

const rows = ref([]);
const loading = ref(false);
const newOpen = ref(false);
const detailOpen = ref(false);
const selected = ref(null);
const customerOptions = ref([]);
const employeeOptions = ref([]);
const filters = reactive({ customer: null, employee: null, status: null });

const headers = computed(() => [
	{ title: __("Plan"), key: "name" },
	{ title: __("Patient"), key: "customer_name" },
	{ title: __("Service"), key: "service" },
	{ title: __("Doctor"), key: "doctor_name" },
	{ title: __("Status"), key: "status" },
	{ title: __("Sessions"), key: "sessions", sortable: false },
	{ title: __("Paid"), key: "paid", sortable: false },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

async function searchCustomers(txt) {
	customerOptions.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
}

async function searchEmployees(txt) {
	employeeOptions.value = await searchLinkOptions("Employee", txt, {}, "employee_name");
}

async function load() {
	loading.value = true;
	try {
		rows.value = await call("list_treatment_plans", { ...filters });
	} finally {
		loading.value = false;
	}
}

function openPlan(name) {
	selected.value = name;
	detailOpen.value = true;
}

onMounted(() => {
	searchCustomers("");
	searchEmployees("");
	load();
});
</script>
