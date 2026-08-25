<template>
	<v-dialog v-model="open" max-width="640" :fullscreen="mobile" :retain-focus="false">
		<v-card :loading="loading">
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-receipt-text-outline" class="mr-2" />
				<span class="text-truncate">{{ doc.name || __("Invoice") }}</span>
				<v-spacer />
				<v-chip :color="invoiceStatusColor(doc.status)" variant="flat" size="small">
					{{ doc.status || "—" }}
				</v-chip>
			</v-card-title>
			<v-divider />

			<v-card-text>
				<v-row dense class="mb-2">
					<v-col cols="12" sm="6">
						<div class="text-caption text-medium-emphasis">{{ __("Patient") }}</div>
						<div>{{ doc.customer_name || doc.customer || "—" }}</div>
					</v-col>
					<v-col cols="12" sm="6">
						<div class="text-caption text-medium-emphasis">{{ __("Date") }}</div>
						<div>{{ formatDate(doc.posting_date) }}</div>
					</v-col>
					<v-col cols="6">
						<div class="text-caption text-medium-emphasis">{{ __("Total") }}</div>
						<div>{{ formatCurrency(doc.grand_total, doc.currency) }}</div>
					</v-col>
					<v-col cols="6">
						<div class="text-caption text-medium-emphasis">{{ __("Outstanding") }}</div>
						<div>{{ formatCurrency(doc.outstanding_amount, doc.currency) }}</div>
					</v-col>
				</v-row>

				<div class="text-subtitle-2 text-medium-emphasis mt-4 mb-1">{{ __("Items") }}</div>
				<v-table density="compact">
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

				<div class="text-subtitle-2 text-medium-emphasis mt-4 mb-1">{{ __("Payments") }}</div>
				<v-table v-if="doc.payments && doc.payments.length" density="compact">
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
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-btn
					v-if="doc.is_action_invoice && doc.status === 'Draft'"
					color="primary"
					variant="flat"
					prepend-icon="mdi-cash-register"
					@click="payOpen = true"
				>
					{{ __("Pay") }}
				</v-btn>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Close") }}</v-btn>
			</v-card-actions>
		</v-card>

		<PaymentDialog
			v-model="payOpen"
			:title="__('Pay')"
			:grand-total="doc.grand_total"
			:outstanding="doc.outstanding_amount"
			:currency="doc.currency"
			full-only
			method="pay_appointment_action"
			:extra-args="{ invoice: doc.name }"
			@paid="onPaid"
		/>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { call, formatCurrency } from "../client.js";
import { invoiceStatusColor } from "../constants.js";
import PaymentDialog from "./PaymentDialog.vue";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	name: { type: String, default: null },
});
const emit = defineEmits(["update:modelValue", "paid"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const loading = ref(false);
const payOpen = ref(false);
const doc = ref({ items: [], payments: [] });

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

async function onPaid() {
	await load();
	emit("paid");
}

watch(open, (isOpen) => {
	if (isOpen && props.name) load();
});
</script>
