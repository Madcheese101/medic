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
			<v-select
				v-model="filters.status"
				:items="SALES_INVOICE_STATUS"
				:label="__('Status')"
				clearable
				style="max-width: 180px"
				@update:model-value="load"
			/>
			<v-text-field
				v-model="filters.from_date"
				type="date"
				:label="__('From')"
				clearable
				style="max-width: 170px"
				@update:model-value="load"
			/>
			<v-text-field
				v-model="filters.to_date"
				type="date"
				:label="__('To')"
				clearable
				style="max-width: 170px"
				@update:model-value="load"
			/>
			<v-btn color="primary" variant="tonal" icon="mdi-filter-outline" :title="__('Apply filters')" @click="load" />
		</v-card-text>

		<v-data-table
			:headers="headers"
			:items="rows"
			:loading="loading"
			density="comfortable"
			:no-data-text="__('No invoices found')"
		>
			<template #item.posting_date="{ item }">
				{{ formatDate(item.posting_date) }}
			</template>
			<template #item.grand_total="{ item }">
				{{ formatCurrency(item.grand_total, item.currency) }}
			</template>
			<template #item.outstanding_amount="{ item }">
				{{ formatCurrency(item.outstanding_amount, item.currency) }}
			</template>
			<template #item.status="{ item }">
				<v-chip size="small" variant="tonal" :color="invoiceStatusColor(item.status)">
					{{ item.status || "—" }}
				</v-chip>
			</template>
			<template #item.actions="{ item }">
				<v-btn
					v-if="item.is_action_invoice && item.status === 'Draft'"
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-cash-register"
					:title="__('Pay')"
					class="mr-1"
					@click="openPayAction(item)"
				/>
				<v-btn
					v-if="item.outstanding_amount > 0 && item.status !== 'Draft'"
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-cash-plus"
					:title="__('Add Payment')"
					class="mr-1"
					@click="openPay(item)"
				/>
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-eye"
					:title="__('View details')"
					@click="openDetails(item.name)"
				/>
			</template>
		</v-data-table>
	</v-card>

	<PaymentDialog
		v-model="payOpen"
		:title="__('Add Payment')"
		:grand-total="payTarget.grand_total"
		:outstanding="payTarget.outstanding_amount"
		:currency="payTarget.currency"
		method="add_payment"
		:extra-args="{ invoice: payTarget.name }"
		@paid="load"
	/>

	<PaymentDialog
		v-model="payActionOpen"
		:title="__('Pay')"
		:grand-total="payActionTarget.grand_total"
		:outstanding="payActionTarget.outstanding_amount"
		:currency="payActionTarget.currency"
		full-only
		method="pay_appointment_action"
		:extra-args="{ invoice: payActionTarget.name }"
		@paid="load"
	/>

	<InvoiceDetailsDialog v-model="detailsOpen" :name="detailsName" @paid="load" />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { call, formatCurrency, searchLinkOptions } from "../client.js";
import { SALES_INVOICE_STATUS, invoiceStatusColor } from "../constants.js";
import PaymentDialog from "../components/PaymentDialog.vue";
import InvoiceDetailsDialog from "../components/InvoiceDetailsDialog.vue";

const rows = ref([]);
const loading = ref(false);
const customerOptions = ref([]);
const filters = reactive({ customer: null, status: null, from_date: "", to_date: "" });

const payOpen = ref(false);
const payTarget = ref({});
const payActionOpen = ref(false);
const payActionTarget = ref({});
const detailsOpen = ref(false);
const detailsName = ref(null);

const headers = computed(() => [
	{ title: __("Invoice"), key: "name" },
	{ title: __("Patient"), key: "customer_name" },
	{ title: __("Date"), key: "posting_date" },
	{ title: __("Total"), key: "grand_total", align: "end" },
	{ title: __("Outstanding"), key: "outstanding_amount", align: "end" },
	{ title: __("Status"), key: "status" },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

async function searchCustomers(txt) {
	customerOptions.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
}

async function load() {
	loading.value = true;
	try {
		rows.value = await call("get_sales_invoices", { ...filters });
	} finally {
		loading.value = false;
	}
}

function openPay(item) {
	payTarget.value = item;
	payOpen.value = true;
}

function openPayAction(item) {
	payActionTarget.value = item;
	payActionOpen.value = true;
}

function openDetails(name) {
	detailsName.value = name;
	detailsOpen.value = true;
}

onMounted(() => {
	searchCustomers("");
	load();
});
</script>
