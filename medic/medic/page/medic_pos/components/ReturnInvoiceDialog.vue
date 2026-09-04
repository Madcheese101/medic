<template>
	<v-dialog v-model="open" max-width="620" :fullscreen="mobile" :retain-focus="false" scrollable>
		<v-card :loading="loading">
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-cash-refund" class="mr-2" />
				{{ __("Return Invoice") }}
			</v-card-title>
			<v-divider />

			<v-card-text>
				<!-- Not eligible -->
				<v-alert v-if="info && !info.kind" type="info" variant="tonal" density="comfortable">
					{{ info.reason }}
				</v-alert>

				<template v-else-if="info">
					<div class="d-flex justify-space-between text-body-2 mb-1">
						<span class="text-medium-emphasis">{{ __("Paid") }}</span>
						<span>{{ formatCurrency(info.paid, info.currency) }}</span>
					</div>

					<!-- Treatment plan breakdown -->
					<template v-if="info.kind === 'treatment_plan'">
						<div class="d-flex justify-space-between text-body-2 mb-1">
							<span class="text-medium-emphasis">{{ __("Completed sessions") }}</span>
							<span>{{ info.completed_sessions }} / {{ info.total_sessions }}</span>
						</div>
						<div class="d-flex justify-space-between text-body-2 mb-1">
							<span class="text-medium-emphasis">{{ __("Per session") }}</span>
							<span>{{ formatCurrency(info.per_session, info.currency) }}</span>
						</div>
						<div class="d-flex justify-space-between text-body-2 mb-3">
							<span class="text-medium-emphasis">{{ __("Owed for completed") }}</span>
							<span>{{ formatCurrency(info.completed_share, info.currency) }}</span>
						</div>

						<v-alert v-if="info.shortfall > 0" type="warning" variant="tonal" density="comfortable">
							{{ __("The completed sessions are not fully paid. Collect the remaining {0} first.", [formatCurrency(info.shortfall, info.currency)]) }}
						</v-alert>
						<v-alert v-else-if="info.refundable <= 0" type="info" variant="tonal" density="comfortable">
							{{ __("Nothing to refund.") }}
						</v-alert>
					</template>

					<v-divider v-if="showRefundForm" class="my-3" />

					<!-- Refund form (appointment amount input + payment rows) -->
					<template v-if="showRefundForm">
						<v-form ref="form">
							<v-text-field
								v-if="info.kind === 'appointment'"
								v-model.number="amount"
								type="number"
								min="0"
								:label="__('Return Amount')"
								prepend-inner-icon="mdi-cash"
								:hint="__('Up to {0}', [formatCurrency(info.max_refund, info.currency)])"
								persistent-hint
								:rules="[required, positive, withinMax]"
								class="mb-3"
							/>
							<div v-else class="d-flex justify-space-between text-subtitle-1 font-weight-medium mb-3">
								<span>{{ __("Refund") }}</span>
								<span>{{ formatCurrency(refundAmount, info.currency) }}</span>
							</div>

							<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Refund via") }}</div>
							<div v-for="(row, i) in rows" :key="i" class="mb-2">
								<div class="d-flex align-center ga-2">
									<v-autocomplete
										v-model="row.mode_of_payment"
										:items="modes"
										item-title="name"
										item-value="name"
										:label="__('Mode of Payment')"
										prepend-inner-icon="mdi-credit-card-outline"
										:rules="[required]"
									/>
									<v-text-field
										v-model.number="row.amount"
										type="number"
										min="0"
										:label="__('Amount')"
										prepend-inner-icon="mdi-cash"
										:rules="[required, positive]"
										style="max-width: 160px"
									/>
									<v-btn
										v-if="rows.length > 1"
										icon="mdi-close"
										size="small"
										variant="text"
										:title="__('Remove')"
										@click="removeRow(i)"
									/>
								</div>
								<v-row v-if="needsReference(row)" dense class="mt-0">
									<v-col cols="12" sm="6">
										<v-text-field
											v-model="row.reference_no"
											:label="__('Reference No')"
											prepend-inner-icon="mdi-pound"
											:rules="[required]"
										/>
									</v-col>
									<v-col cols="12" sm="6">
										<v-text-field
											v-model="row.reference_date"
											type="date"
											:label="__('Reference Date')"
											prepend-inner-icon="mdi-calendar"
											:rules="[required]"
										/>
									</v-col>
								</v-row>
							</div>
						</v-form>

						<v-btn variant="text" color="primary" prepend-icon="mdi-plus" size="small" @click="addRow">
							{{ __("Add method") }}
						</v-btn>

						<v-divider class="my-3" />
						<div class="d-flex justify-space-between text-body-2">
							<span class="text-medium-emphasis">{{ __("Remaining") }}</span>
							<span :class="canSubmit ? 'text-success' : 'text-error'">
								{{ formatCurrency(remaining, info.currency) }}
							</span>
						</div>
					</template>
				</template>
			</v-card-text>

			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Close") }}</v-btn>
				<v-btn
					v-if="showPayRemaining"
					color="primary"
					variant="flat"
					prepend-icon="mdi-cash-plus"
					@click="payOpen = true"
				>
					{{ __("Pay remaining") }}
				</v-btn>
				<v-btn
					v-if="showRefundForm"
					color="primary"
					variant="flat"
					:disabled="!canSubmit"
					:loading="submitting"
					@click="submit"
				>
					{{ __("Refund") }}
				</v-btn>
			</v-card-actions>
		</v-card>

		<SplitPaymentDialog
			v-model="payOpen"
			:title="__('Pay remaining')"
			:outstanding="info ? info.shortfall : 0"
			:currency="info ? info.currency : null"
			method="record_payments"
			:extra-args="{ invoice }"
			require-full
			@paid="onRemainingPaid"
		/>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { call, formatCurrency, notifySuccess } from "../client.js";
import SplitPaymentDialog from "./SplitPaymentDialog.vue";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	invoice: { type: String, default: null },
});
const emit = defineEmits(["update:modelValue", "returned"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const form = ref(null);
const loading = ref(false);
const submitting = ref(false);
const info = ref(null);
const amount = ref(null);
const rows = ref([]);
const modes = ref([]);
const payOpen = ref(false);

const required = (v) => (v !== null && v !== "" && v !== undefined) || __("Required");
const positive = (v) => v > 0 || __("Must be greater than 0");
const withinMax = (v) => (info.value && v <= info.value.max_refund + 0.01) || __("Exceeds paid amount");

// The amount being refunded: user-entered for appointments, fixed for plans.
const refundAmount = computed(() => {
	if (!info.value) return 0;
	return info.value.kind === "appointment" ? Number(amount.value) || 0 : Number(info.value.refundable) || 0;
});

const showRefundForm = computed(() => {
	if (!info.value) return false;
	if (info.value.kind === "appointment") return true;
	return info.value.kind === "treatment_plan" && info.value.shortfall <= 0 && info.value.refundable > 0;
});
const showPayRemaining = computed(() => !!info.value && info.value.kind === "treatment_plan" && info.value.shortfall > 0);

const total = computed(() => rows.value.reduce((sum, r) => sum + (Number(r.amount) || 0), 0));
const remaining = computed(() => Number((refundAmount.value - total.value).toFixed(2)));
const canSubmit = computed(() => refundAmount.value > 0 && Math.abs(remaining.value) < 0.01);

function needsReference(row) {
	const mode = modes.value.find((m) => m.name === row.mode_of_payment);
	return !!mode && mode.type !== "Cash";
}

function blankRow(amt = null) {
	return { mode_of_payment: null, amount: amt, reference_no: "", reference_date: frappe.datetime.get_today() };
}
function addRow() {
	rows.value.push(blankRow(remaining.value > 0 ? remaining.value : null));
}
function removeRow(i) {
	rows.value.splice(i, 1);
}

async function loadInfo() {
	loading.value = true;
	try {
		info.value = await call("get_invoice_return_info", { invoice: props.invoice });
		amount.value = info.value.kind === "appointment" ? info.value.max_refund : null;
		resetRows();
	} finally {
		loading.value = false;
	}
}

function resetRows() {
	rows.value = [blankRow(refundAmount.value || null)];
	form.value?.resetValidation();
}

async function onRemainingPaid() {
	await loadInfo();
}

async function submit() {
	const { valid } = await form.value.validate();
	if (!valid || !canSubmit.value) return;

	submitting.value = true;
	try {
		await call("create_invoice_return", {
			invoice: props.invoice,
			amount: refundAmount.value,
			payments: rows.value.map((r) => ({
				mode_of_payment: r.mode_of_payment,
				amount: r.amount,
				reference_no: r.reference_no || null,
				reference_date: r.reference_date || null,
			})),
		});
		notifySuccess(__("Return recorded"));
		open.value = false;
		emit("returned");
	} finally {
		submitting.value = false;
	}
}

watch(open, async (isOpen) => {
	if (!isOpen) return;
	info.value = null;
	if (!modes.value.length) modes.value = await call("get_payment_modes");
	await loadInfo();
});

// Keep the single refund row in step with a freshly typed appointment amount.
watch(refundAmount, (val) => {
	if (rows.value.length === 1) rows.value[0].amount = val || null;
});
</script>
