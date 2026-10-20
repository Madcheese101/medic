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
				@update:model-value="table.reload"
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
				@update:model-value="table.reload"
			/>
			<v-text-field
				v-model="filters.appointment_date"
				type="date"
				:label="__('Date')"
				clearable
				style="max-width: 190px"
				@update:model-value="table.reload"
			/>
			<v-select
				v-model="filters.appointment_status"
				:items="APPOINTMENT_STATUS"
				:label="__('Status')"
				clearable
				style="max-width: 180px"
				@update:model-value="table.reload"
			/>
			<v-btn color="primary" variant="tonal" icon="mdi-filter-outline" :title="__('Apply filters')" @click="table.reload" />
			<v-spacer />
			<v-btn color="primary" variant="tonal" prepend-icon="mdi-calendar-account" class="mr-2" @click="sessionOpen = true">
				{{ __("New Session") }}
			</v-btn>
			<v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openCreate(false)">
				{{ __("New Appointment") }}
			</v-btn>
		</v-card-text>

		<v-data-table-server
			v-model:page="table.page"
			:headers="headers"
			:items="table.rows"
			:items-length="table.total"
			:loading="table.loading"
			density="comfortable"
			:no-data-text="__('No appointments found')"
			@update:options="table.onOptions"
		>
			<template #item.appointment_date="{ item }">
				{{ formatDate(item.appointment_date) }}
			</template>
			<template #item.appointment_type="{ item }">
				{{ label(item.appointment_type, "Patient Appointment") }}
			</template>
			<template #item.appointment_status="{ item }">
				<v-chip size="small" variant="tonal" :color="appointmentStatusColor(item.appointment_status)">
					{{ label(item.appointment_status, "Patient Appointment") }}
				</v-chip>
			</template>
			<template #item.queue="{ item }">
				<span v-if="item.queue">{{ item.queue }}</span>
				<v-btn
					v-else-if="item.docstatus === 1 && item.appointment_date === today && item.appointment_status !== AppointmentStatus.CANCELLED"
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
					@click="confirmAndPay(item)"
				/>
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-printer"
					:title="__('Print')"
					class="mr-1"
					@click="printDoc('Patient Appointment', item.name)"
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
		</v-data-table-server>
	</v-card>

	<NewAppointmentForm v-else :initial-new="createNew" @created="onCreated" @cancel="creating = false" />

	<NewSessionDialog v-model="sessionOpen" @created="table.load" />

	<SplitPaymentDialog
		v-model="payOpen"
		:title="__('Confirm & Pay')"
		:outstanding="payTarget.outstanding_amount"
		:currency="payTarget.currency"
		method="appointments.pay_appointment"
		:extra-args="{ name: payTarget.name }"
		:require-full="payTarget.appointment_type === AppointmentType.CONSULTATION"
		:modes="cashierModes"
		@paid="table.load"
	/>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { call, debounce, notifySuccess, printDoc, searchLinkOptions } from "../client.js";
import {
	APPOINTMENT_STATUS,
	AppointmentStatus,
	AppointmentType,
	appointmentStatusColor,
	label,
} from "../constants.js";
import { useServerTable } from "../serverTable.js";
import { useUiStore } from "../stores/ui.js";
import NewAppointmentForm from "../components/NewAppointmentForm.vue";
import NewSessionDialog from "../components/NewSessionDialog.vue";
import SplitPaymentDialog from "../components/SplitPaymentDialog.vue";

const emit = defineEmits(["navigate"]);

const uiStore = useUiStore();

// Cashier POS Profile modes for front-desk collections; null falls back to all modes.
const cashierModes = frappe.boot.cashier_payment_modes?.length ? frappe.boot.cashier_payment_modes : null;
const today = frappe.datetime.get_today();
const creating = ref(false);
const createNew = ref(false);
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

const table = useServerTable("appointments.get_appointments", () => filters);

// The doctor and service names are joined in on the server, which can't sort on them.
const headers = computed(() => [
	{ title: __("Appointment"), key: "name" },
	{ title: __("Date"), key: "appointment_date" },
	{ title: __("Type"), key: "appointment_type" },
	{ title: __("Patient"), key: "customer_name" },
	{ title: __("Doctor"), key: "doctor_name", sortable: false },
	{ title: __("Service"), key: "service_name", sortable: false },
	{ title: __("Status"), key: "appointment_status" },
	{ title: __("Queue"), key: "queue" },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

const searchCustomers = debounce(async (txt) => {
	customerOptions.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
});

const searchEmployees = debounce(async (txt) => {
	const filters = frappe.boot.default_doctor_designation
		? { designation: frappe.boot.default_doctor_designation }
		: {};
	employeeOptions.value = await searchLinkOptions("Employee", txt, filters, "employee_name");
});

function view(name) {
	emit("navigate", "appointment", { name });
}

// Ensure the invoice exists (the "confirm" step), then open the pay dialog with its totals.
// The appointment type rides along so a consultation can require full payment in the dialog.
async function confirmAndPay(item) {
	confirming.value = item.name;
	try {
		const fin = await call("appointments.confirm_appointment_invoice", { name: item.name });
		payTarget.value = { name: item.name, appointment_type: item.appointment_type, ...fin };
		payOpen.value = true;
	} finally {
		confirming.value = null;
	}
}

function openCreate(newPatient) {
	createNew.value = !!newPatient;
	creating.value = true;
}

// The app-bar "New" menu queues a request here; open the form and clear it.
// immediate covers arriving from another view; the watch covers already being here.
watch(
	() => uiStore.pendingAppointment,
	(req) => {
		if (!req) return;
		openCreate(req.newPatient);
		uiStore.consumeNewAppointment();
	},
	{ immediate: true }
);

function onCreated() {
	creating.value = false;
}

async function checkIn(name) {
	checkingIn.value = name;
	try {
		const q = await call("appointments.check_in", { appointment: name });
		notifySuccess(__("Checked in — queue {0}", [q]));
		await table.load();
	} finally {
		checkingIn.value = null;
	}
}

onMounted(() => {
	searchCustomers("");
	searchEmployees("");
});
</script>
