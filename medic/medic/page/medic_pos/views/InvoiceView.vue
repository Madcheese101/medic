<template>
	<v-card :loading="loading">
		<v-card-title class="d-flex align-center">
			<v-btn
				variant="text"
				:icon="backIcon"
				:title="__('Back')"
				class="mr-2"
				@click="emit('back')"
			/>
			<span class="text-truncate">{{ doc.name || __("Invoice") }}</span>
			<v-btn
				v-if="doc.name"
				variant="text"
				icon="mdi-printer"
				:title="__('Print')"
				class="ml-1"
				@click="printDoc('Sales Invoice', doc.name)"
			/>
			<v-spacer />
			<v-chip :color="invoiceStatusColor(doc.status)" variant="flat" size="large">
				{{ doc.status || "—" }}
			</v-chip>
		</v-card-title>
		<v-divider />

		<v-card-text>
			<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Invoice Details") }}</div>
			<v-row dense>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.customer_name || doc.customer" :label="__('Patient')" prepend-inner-icon="mdi-account-outline" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="formatDate(doc.posting_date)" :label="__('Date')" prepend-inner-icon="mdi-calendar" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="formatCurrency(doc.grand_total, doc.currency)" :label="__('Total')" prepend-inner-icon="mdi-cash" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="formatCurrency(doc.outstanding_amount, doc.currency)" :label="__('Outstanding')" prepend-inner-icon="mdi-cash-clock" readonly />
				</v-col>
				<v-col v-if="doc.patient_appointment" cols="12" md="6">
					<ReferenceField :value="doc.patient_appointment" :label="__('Appointment')" icon="mdi-calendar-check-outline" @open="refs.openAppointment(doc.patient_appointment)" />
				</v-col>
				<v-col v-if="doc.treatment_plan" cols="12" md="6">
					<ReferenceField :value="doc.treatment_plan" :label="__('Treatment Plan')" icon="mdi-clipboard-pulse-outline" @open="refs.openTreatmentPlan(doc.treatment_plan)" />
				</v-col>
			</v-row>

			<v-divider class="my-5" />

			<div class="text-subtitle-2 text-medium-emphasis mb-1">{{ __("Items") }}</div>
			<v-table density="comfortable">
				<thead>
					<tr>
						<th class="text-left">{{ __("Item") }}</th>
						<th class="text-end">{{ __("Qty") }}</th>
						<th class="text-end">{{ __("Rate") }}</th>
						<th class="text-end">{{ __("Amount") }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(item, i) in doc.items" :key="i">
						<td>{{ item.item_name || item.item_code }}</td>
						<td class="text-end">{{ item.qty }}</td>
						<td class="text-end">{{ formatCurrency(item.rate, doc.currency) }}</td>
						<td class="text-end">{{ formatCurrency(item.amount, doc.currency) }}</td>
					</tr>
				</tbody>
			</v-table>

			<v-divider class="my-5" />

			<div class="text-subtitle-2 text-medium-emphasis mb-1">{{ __("Payments") }}</div>
			<v-table v-if="doc.payments && doc.payments.length" density="comfortable">
				<thead>
					<tr>
						<th class="text-left">{{ __("Date") }}</th>
						<th class="text-left">{{ __("Mode") }}</th>
						<th class="text-end">{{ __("Amount") }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(p, i) in doc.payments" :key="i">
						<td>{{ formatDate(p.posting_date) }}</td>
						<td>{{ p.mode_of_payment || "—" }}</td>
						<td class="text-end">{{ formatCurrency(p.allocated_amount, doc.currency) }}</td>
					</tr>
				</tbody>
			</v-table>
			<div v-else class="text-medium-emphasis text-body-2">{{ __("No payments yet") }}</div>

			<div v-if="doc.is_action_invoice && doc.status === 'Draft'" class="d-flex mt-4">
				<v-spacer />
				<v-btn color="primary" variant="flat" prepend-icon="mdi-cash-register" @click="payOpen = true">
					{{ __("Pay") }}
				</v-btn>
			</div>
		</v-card-text>
	</v-card>

	<SplitPaymentDialog
		v-model="payOpen"
		:title="__('Pay')"
		:outstanding="doc.outstanding_amount"
		:currency="doc.currency"
		method="pay_appointment_action"
		:extra-args="{ invoice: doc.name }"
		require-full
		@paid="load"
	/>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRtl } from "vuetify";
import { call, formatCurrency, printDoc } from "../client.js";
import { invoiceStatusColor } from "../constants.js";
import SplitPaymentDialog from "../components/SplitPaymentDialog.vue";
import ReferenceField from "../components/ReferenceField.vue";
import { useReferences } from "../references.js";

const props = defineProps({ name: { type: String, default: null } });
const emit = defineEmits(["back"]);

const refs = useReferences();
const { isRtl } = useRtl();

const loading = ref(false);
const payOpen = ref(false);
const doc = ref({ items: [], payments: [] });

const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

async function load() {
	loading.value = true;
	try {
		doc.value = await call("get_sales_invoice", { name: props.name });
	} finally {
		loading.value = false;
	}
}

onMounted(load);
</script>
