<template>
	<v-card v-if="!creating">
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
			<v-btn color="primary" variant="tonal" prepend-icon="mdi-calendar-account" class="mr-2" @click="sessionOpen = true">
				{{ __("New Session") }}
			</v-btn>
			<v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="creating = true">
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
			<template #item.queue="{ item }">
				<span v-if="item.queue">{{ item.queue }}</span>
				<v-btn
					v-else-if="item.docstatus === 1"
					size="small"
					variant="tonal"
					color="primary"
					prepend-icon="mdi-login"
					:loading="checkingIn === item.name"
					@click="checkIn(item.name)"
				>
					{{ __("Check in") }}
				</v-btn>
				<span v-else class="text-medium-emphasis">—</span>
			</template>
			<template #item.actions="{ item }">
				<v-btn
					v-if="item.docstatus === 1 && !item.invoice && !item.treatment_plan"
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-cash-register"
					:title="__('Confirm & Pay')"
					:loading="confirming === item.name"
					class="mr-1"
					@click="confirmAndPay(item.name)"
				/>
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

	<NewAppointmentForm v-else @created="onCreated" @cancel="creating = false" />

	<NewSessionDialog v-model="sessionOpen" @created="load" />

	<PaymentDialog
		v-model="payOpen"
		:title="__('Confirm & Pay')"
		:grand-total="payTarget.grand_total"
		:outstanding="payTarget.outstanding_amount"
		:currency="payTarget.currency"
		method="pay_appointment"
		:extra-args="{ name: payTarget.name }"
		@paid="load"
	/>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { call, notifySuccess, searchLinkOptions } from "../client.js";
import { APPOINTMENT_STATUS, appointmentStatusColor } from "../constants.js";
import NewAppointmentForm from "../components/NewAppointmentForm.vue";
import NewSessionDialog from "../components/NewSessionDialog.vue";
import PaymentDialog from "../components/PaymentDialog.vue";

const emit = defineEmits(["navigate"]);

const rows = ref([]);
const loading = ref(false);
const creating = ref(false);
const sessionOpen = ref(false);
const checkingIn = ref(null);
const confirming = ref(null);
const payOpen = ref(false);
const payTarget = ref({});
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
	{ title: __("Queue"), key: "queue", sortable: false },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

async function searchCustomers(txt) {
	customerOptions.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
}

async function searchEmployees(txt) {
	employeeOptions.value = await searchLinkOptions("Employee", txt, {}, "employee_name");
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

// Ensure the invoice exists (the "confirm" step), then open the pay dialog with its totals.
async function confirmAndPay(name) {
	confirming.value = name;
	try {
		const fin = await call("confirm_appointment_invoice", { name });
		payTarget.value = { name, ...fin };
		payOpen.value = true;
	} finally {
		confirming.value = null;
	}
}

function onCreated() {
	creating.value = false;
	load();
}

async function checkIn(name) {
	checkingIn.value = name;
	try {
		const q = await call("check_in", { appointment: name });
		notifySuccess(__("Checked in — queue {0}", [q]));
		await load();
	} finally {
		checkingIn.value = null;
	}
}

onMounted(() => {
	searchCustomers("");
	searchEmployees("");
	load();
});
</script>
