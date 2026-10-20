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
				:items="['Pending', 'Ongoing', 'Completed']"
				:label="__('Status')"
				clearable
				style="max-width: 180px"
				@update:model-value="load"
			/>
			<v-btn color="primary" variant="tonal" icon="mdi-filter-outline" :title="__('Apply filters')" @click="load" />
			<v-spacer />
			<v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="newOpen = true">
				{{ __("New Test Request") }}
			</v-btn>
		</v-card-text>

		<v-data-table
			:headers="headers"
			:items="rows"
			:loading="loading"
			density="comfortable"
			:no-data-text="__('No test requests found')"
		>
			<template #item.status="{ item }">
				<v-chip size="small" variant="tonal" :color="testRequestStatusColor(item.status)">{{ item.status }}</v-chip>
			</template>
			<template #item.sales_invoice="{ item }">
				<a v-if="item.sales_invoice" class="medic-ref-link" @click="refs.openInvoice(item.sales_invoice)">{{ item.sales_invoice }}</a>
				<span v-else class="text-medium-emphasis">—</span>
			</template>
			<template #item.paid="{ item }">
				<span v-if="item.sales_invoice">{{ Math.round((item.paid_pct || 0) * 100) }}%</span>
				<span v-else class="text-medium-emphasis">—</span>
			</template>
			<template #item.actions="{ item }">
				<v-btn
					v-if="!item.sales_invoice"
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-receipt-text-plus-outline"
					:title="__('Create Invoice')"
					class="mr-1"
					@click="openInvoice(item)"
				/>
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-printer"
					:title="__('Print')"
					class="mr-1"
					@click="printDoc('Test Request', item.name)"
				/>
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-eye"
					:title="__('Open')"
					@click="refs.openTestRequest(item.name)"
				/>
			</template>
		</v-data-table>
	</v-card>

	<NewTestRequestDialog v-model="newOpen" @created="load" />

	<TestRequestInvoiceDialog v-model="invoiceOpen" :name="invoiceTarget.name" @created="load" />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { call, debounce, printDoc, searchLinkOptions } from "../client.js";
import { testRequestStatusColor } from "../constants.js";
import NewTestRequestDialog from "../components/NewTestRequestDialog.vue";
import TestRequestInvoiceDialog from "../components/TestRequestInvoiceDialog.vue";
import { useReferences } from "../references.js";

const refs = useReferences();

const rows = ref([]);
const loading = ref(false);
const newOpen = ref(false);
const invoiceOpen = ref(false);
const invoiceTarget = ref({});
const customerOptions = ref([]);
const filters = reactive({ customer: null, status: null });

const headers = computed(() => [
	{ title: __("Request"), key: "name" },
	{ title: __("Patient"), key: "patient_name" },
	{ title: __("Tests"), key: "item_count", sortable: false },
	{ title: __("Invoice"), key: "sales_invoice" },
	{ title: __("Status"), key: "status" },
	{ title: __("Paid"), key: "paid", sortable: false },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

const searchCustomers = debounce(async (txt) => {
	customerOptions.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
});

async function load() {
	loading.value = true;
	try {
		rows.value = await call("lab.list_test_requests", { ...filters });
	} finally {
		loading.value = false;
	}
}

function openInvoice(item) {
	invoiceTarget.value = item;
	invoiceOpen.value = true;
}

onMounted(() => {
	searchCustomers("");
	load();
});
</script>
