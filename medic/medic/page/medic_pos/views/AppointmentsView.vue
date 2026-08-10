<template>
	<v-card>
		<v-card-text class="d-flex flex-wrap align-center ga-3">
			<v-autocomplete
				v-model="filters.customer"
				:items="customerOptions"
				:label="__('Patient')"
				prepend-inner-icon="mdi-account-outline"
				clearable
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
				style="max-width: 220px"
				@update:search="searchEmployees"
				@update:model-value="load"
			/>
			<v-text-field
				v-model="filters.appointment_date"
				type="date"
				:label="__('Date')"
				clearable
				style="max-width: 190px"
				@update:model-value="load"
			/>
			<v-select
				v-model="filters.appointment_status"
				:items="APPOINTMENT_STATUS"
				:label="__('Status')"
				clearable
				style="max-width: 180px"
				@update:model-value="load"
			/>
			<v-btn color="primary" variant="tonal" icon="mdi-filter-outline" :title="__('Apply filters')" @click="load" />
			<v-spacer />
			<v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="newOpen = true">
				{{ __("New Appointment") }}
			</v-btn>
		</v-card-text>

		<v-data-table
			:headers="headers"
			:items="rows"
			:loading="loading"
			density="comfortable"
			:no-data-text="__('No appointments found')"
		>
			<template #item.appointment_date="{ item }">
				{{ formatDate(item.appointment_date) }}
			</template>
			<template #item.appointment_status="{ item }">
				<v-chip size="small" variant="tonal" :color="appointmentStatusColor(item.appointment_status)">
					{{ item.appointment_status || "—" }}
				</v-chip>
			</template>
			<template #item.actions="{ item }">
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-eye"
					:title="__('View')"
					@click="view(item.name)"
				/>
			</template>
		</v-data-table>
	</v-card>

	<NewAppointmentDialog v-model="newOpen" @created="load" />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { call, customSearchLink } from "../client.js";
import { APPOINTMENT_STATUS, appointmentStatusColor } from "../constants.js";
import NewAppointmentDialog from "../components/NewAppointmentDialog.vue";

const emit = defineEmits(["navigate"]);

const rows = ref([]);
const loading = ref(false);
const newOpen = ref(false);
const customerOptions = ref([]);
const employeeOptions = ref([]);
const filters = reactive({
	customer: null,
	employee: null,
	appointment_date: "",
	appointment_status: null,
});

const headers = computed(() => [
	{ title: __("Appointment"), key: "name" },
	{ title: __("Date"), key: "appointment_date" },
	{ title: __("Type"), key: "appointment_type" },
	{ title: __("Patient"), key: "customer_name" },
	{ title: __("Doctor"), key: "doctor_name" },
	{ title: __("Service"), key: "service" },
	{ title: __("Status"), key: "appointment_status" },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

async function searchCustomers(txt) {
	const r = await customSearchLink("Customer", txt);
	customerOptions.value = r.map((x) => ({ title: x.description || x.value, value: x.value }));
}

async function searchEmployees(txt) {
	const r = await customSearchLink("Employee", txt);
	employeeOptions.value = r.map((x) => ({ title: x.description || x.value, value: x.value }));
}

async function load() {
	loading.value = true;
	try {
		rows.value = await call("get_appointments", { ...filters });
	} finally {
		loading.value = false;
	}
}

function view(name) {
	emit("navigate", "appointment", { name });
}

onMounted(() => {
	searchCustomers("");
	searchEmployees("");
	load();
});
</script>
