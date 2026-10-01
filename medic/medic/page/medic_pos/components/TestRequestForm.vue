<template>
	<v-card :loading="loading">
		<v-card-title class="d-flex align-center">
			<v-btn variant="text" :icon="backIcon" :title="__('Back')" class="mr-2" @click="emit('cancel')" />
			<v-icon icon="mdi-test-tube" class="mr-2" />
			<span class="text-truncate">{{ isNew ? __("New Test Request") : testRequest }}</span>
			<v-chip v-if="doc.status" size="large" variant="flat" class="ml-3" :color="testRequestStatusColor(doc.status)">
				{{ doc.status }}
			</v-chip>
			<v-spacer />
			<div v-if="!isNew" class="d-flex align-center ga-2 mr-3">
				<v-btn v-if="!doc.sales_invoice" color="primary" variant="flat" size="small" @click="invoiceOpen = true">
					{{ __("Create Invoice") }}
				</v-btn>
				<v-btn
					v-if="doc.status === 'Pending' && doc.sales_invoice"
					color="primary"
					variant="flat"
					size="small"
					:disabled="!isPaid"
					:title="isPaid ? '' : __('Invoice must be fully paid first')"
					:loading="acting"
					@click="startTest"
				>
					{{ __("Start Test") }}
				</v-btn>
				<v-btn v-if="doc.status === 'Ongoing'" color="success" variant="flat" size="small" :loading="acting" @click="completeTest">
					{{ __("Mark Completed") }}
				</v-btn>
				<v-btn
					v-if="canEditResults"
					variant="text"
					icon="mdi-content-save-outline"
					:title="__('Save Results')"
					:loading="savingResults"
					@click="saveResults"
				/>
				<v-btn
					variant="text"
					icon="mdi-printer"
					:title="__('Print')"
					@click="printDoc('Test Request', testRequest)"
				/>
			</div>
		</v-card-title>
		<v-divider />

		<v-card-text>
			<v-row dense>
				<v-col cols="12" md="6">
					<v-text-field :model-value="patientName" :label="__('Patient')" prepend-inner-icon="mdi-account-outline" readonly />
				</v-col>
				<v-col v-if="!isNew" cols="12" md="6">
					<v-text-field :label="__('Invoice')" readonly :model-value="doc.sales_invoice || __('Not invoiced')" prepend-inner-icon="mdi-receipt-text-outline">
						<template v-if="doc.sales_invoice" #append-inner>
							<a class="medic-ref-link" @click="refs.openInvoice(doc.sales_invoice)">{{ __("Open") }}</a>
						</template>
					</v-text-field>
				</v-col>
			</v-row>

			<!-- New: pick the tests to order -->
			<template v-if="isNew">
				<v-divider class="my-4" />
				<v-form ref="form">
					<v-autocomplete
						v-model="newItems"
						:items="testOptions"
						:label="__('Tests')"
						prepend-inner-icon="mdi-flask-outline"
						:rules="[nonEmpty]"
						multiple
						chips
						closable-chips
						item-props
						@update:search="searchTests"
					/>
				</v-form>
			</template>

			<!-- View: ordered tests + results -->
			<template v-else>
				<v-divider class="my-4" />
				<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Ordered Tests") }}</div>
				<v-table density="comfortable">
					<thead>
						<tr>
							<th>{{ __("Item") }}</th>
							<th>{{ __("Item Name") }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(row, i) in doc.items || []" :key="i">
							<td>{{ row.item }}</td>
							<td>{{ row.item_name }}</td>
						</tr>
						<tr v-if="!(doc.items && doc.items.length)">
							<td colspan="2" class="text-medium-emphasis">{{ __("No tests") }}</td>
						</tr>
					</tbody>
				</v-table>

				<v-divider class="my-4" />
				<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Results") }}</div>
				<v-table density="comfortable">
					<thead>
						<tr>
							<th>{{ __("Test") }}</th>
							<th>{{ __("Unit") }}</th>
							<th>{{ __("Reference Range") }}</th>
							<th style="min-width: 160px">{{ __("Result") }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(row, i) in results" :key="i">
							<td>{{ row.item_name || row.item }}</td>
							<td>{{ row.uom }}</td>
							<td>{{ row.reference_range }}</td>
							<td>
								<v-text-field v-model="row.result" density="compact" variant="outlined" hide-details :readonly="!canEditResults" />
							</td>
						</tr>
						<tr v-if="!results.length">
							<td colspan="4" class="text-medium-emphasis">
								{{ __("Results appear once the invoice is submitted.") }}
							</td>
						</tr>
					</tbody>
				</v-table>
			</template>
		</v-card-text>
		<v-divider v-if="isNew" />

		<v-card-actions v-if="isNew">
			<v-btn variant="text" @click="emit('cancel')">{{ __("Cancel") }}</v-btn>
			<v-spacer />
			<v-btn color="primary" variant="flat" :loading="saving" @click="create">
				{{ __("Create") }}
			</v-btn>
		</v-card-actions>
	</v-card>

	<TestRequestInvoiceDialog v-model="invoiceOpen" :name="testRequest" @created="reload" />
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRtl } from "vuetify";
import { call, confirmAction, notifySuccess, printDoc, searchLinkOptions } from "../client.js";
import { testRequestStatusColor } from "../constants.js";
import TestRequestInvoiceDialog from "./TestRequestInvoiceDialog.vue";
import { useReferences } from "../references.js";

const props = defineProps({
	appointment: { type: String, default: null },
	patient: { type: String, default: null },
	// Patient's display name, when the caller has it (appointment context).
	patientName: { type: String, default: null },
	testRequest: { type: String, default: null },
});
const emit = defineEmits(["saved", "cancel"]);

const refs = useReferences();
const { isRtl } = useRtl();

const doc = ref({});
const results = ref([]);
const newItems = ref([]);
const testOptions = ref([]);
const form = ref(null);
const loading = ref(false);
const saving = ref(false);
const acting = ref(false);
const savingResults = ref(false);
const invoiceOpen = ref(false);

const isNew = computed(() => !props.testRequest);
const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));
const patientName = computed(() => props.patientName || doc.value.patient_name || props.patient);
const isPaid = computed(() => !!doc.value.sales_invoice && (doc.value.outstanding_amount || 0) <= 0);
const canEditResults = computed(() => doc.value.status === "Ongoing" && results.value.length > 0);

const nonEmpty = (v) => (Array.isArray(v) && v.length > 0) || __("Add at least one test");

async function searchTests(txt) {
	testOptions.value = await searchLinkOptions("Item", txt, { item_type: "Lab Test" }, "item_name");
}

async function create() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		const name = await call("create_appointment_test_request", {
			appointment: props.appointment,
			items: newItems.value,
		});
		notifySuccess(__("Test request {0} created", [name]));
		emit("saved", name);
	} finally {
		saving.value = false;
	}
}

async function reload() {
	loading.value = true;
	try {
		const data = await call("get_test_request", { name: props.testRequest });
		doc.value = data;
		results.value = (data.result || []).map((r) => ({ ...r }));
	} finally {
		loading.value = false;
	}
}

async function saveResults() {
	savingResults.value = true;
	try {
		const data = await call("save_test_results", {
			name: props.testRequest,
			results: results.value.map((r) => ({ item: r.item, result: r.result })),
		});
		doc.value = data;
		results.value = (data.result || []).map((r) => ({ ...r }));
		notifySuccess(__("Results saved"));
	} finally {
		savingResults.value = false;
	}
}

async function startTest() {
	if (!(await confirmAction(__("Start this test?")))) return;
	acting.value = true;
	try {
		await call("start_test_request", { name: props.testRequest });
		await reload();
	} finally {
		acting.value = false;
	}
}

async function completeTest() {
	// Every test must have a result before completion (also enforced server-side).
	if (!results.value.length || results.value.some((r) => !String(r.result ?? "").trim())) {
		frappe.msgprint({
			title: __("Incomplete"),
			indicator: "red",
			message: __("Enter a result for every test before completing."),
		});
		return;
	}
	if (!(await confirmAction(__("Mark this test as completed?")))) return;
	acting.value = true;
	try {
		await call("complete_test_request", { name: props.testRequest });
		notifySuccess(__("Test completed"));
		await reload();
	} finally {
		acting.value = false;
	}
}

onMounted(() => {
	if (isNew.value) searchTests("");
	else reload();
});
</script>
