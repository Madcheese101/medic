<template>
	<v-card v-if="!selected">
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
			<v-text-field
				v-model="filters.mobile"
				:label="__('Mobile')"
				prepend-inner-icon="mdi-phone-outline"
				clearable
				style="max-width: 200px"
				@update:model-value="loadSoon"
			/>
			<v-checkbox
				v-model="filters.include_invoiced"
				:label="__('Include invoiced')"
				hide-details
				@update:model-value="load"
			/>
			<v-btn
				color="primary"
				variant="tonal"
				icon="mdi-filter-outline"
				:title="__('Apply filters')"
				@click="load"
			/>
		</v-card-text>

		<v-data-table
			:headers="headers"
			:items="rows"
			:loading="loading"
			density="comfortable"
			:no-data-text="__('No prescriptions found')"
		>
			<template #item.posting_date="{ item }">
				{{ formatDate(item.posting_date) }}
			</template>
			<template #item.invoice_created="{ item }">
				<v-chip size="small" variant="tonal" :color="item.invoice_created ? 'success' : 'warning'">
					{{ item.invoice_created ? __("Invoiced") : __("Pending") }}
				</v-chip>
			</template>
			<template #item.actions="{ item }">
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-eye"
					:title="__('View')"
					class="mr-1"
					@click="view(item)"
				/>
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-printer"
					:title="__('Print')"
					class="mr-1"
					@click="printPrescription(item)"
				/>
				<v-btn
					v-if="!item.invoice_created"
					size="small"
					variant="flat"
					color="primary"
					icon="mdi-cash-register"
					:title="__('Create Invoice')"
					@click="createInvoice(item)"
				/>
			</template>
		</v-data-table>
	</v-card>

	<PrescriptionForm
		v-else
		:prescription="selected.name"
		:patient="selected.patient"
		@cancel="closeView"
		@saved="closeView"
	/>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { call, debounce, searchLinkOptions } from "../client.js";
import PrescriptionForm from "../components/PrescriptionForm.vue";

const emit = defineEmits(["navigate"]);

const rows = ref([]);
const loading = ref(false);
const selected = ref(null);
const customerOptions = ref([]);
const filters = reactive({
	customer: null,
	mobile: "",
	include_invoiced: false,
});

const headers = computed(() => [
	{ title: __("Prescription"), key: "name" },
	{ title: __("Patient"), key: "customer_name" },
	{ title: __("Mobile"), key: "mobile" },
	{ title: __("Date"), key: "posting_date" },
	{ title: __("Status"), key: "invoice_created" },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

const searchCustomers = debounce(async (txt) => {
	customerOptions.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
});

async function load() {
	loading.value = true;
	try {
		rows.value = await call("pos.list_prescriptions", {
			customer: filters.customer,
			mobile: filters.mobile,
			include_invoiced: filters.include_invoiced ? 1 : 0,
		});
	} finally {
		loading.value = false;
	}
}

// The mobile filter reloads as it is typed.
const loadSoon = debounce(load);

function view(item) {
	selected.value = item;
}

function closeView() {
	selected.value = null;
	load();
}

function printPrescription(item) {
	// Prescription print uses the format configured in Clinic Setup.
	const fmt = frappe.boot.prescription_print_format
		? `&format=${encodeURIComponent(frappe.boot.prescription_print_format)}`
		: "";
	window.open(
		`/printview?doctype=Prescription&name=${encodeURIComponent(item.name)}${fmt}&trigger_print=1`,
		"_blank"
	);
}

function createInvoice(item) {
	emit("navigate", "pharmacy-pos", { prescription: item.name });
}

onMounted(() => {
	searchCustomers("");
	load();
});
</script>
