<template>
	<v-dialog v-model="open" max-width="600" :fullscreen="mobile" :retain-focus="false" scrollable>
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-cash-multiple" class="mr-2" />
				{{ title || __("Pay") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<div class="d-flex justify-space-between text-subtitle-1 font-weight-medium mb-3">
					<span>{{ __("Total") }}</span>
					<span>{{ formatCurrency(outstanding, currency) }}</span>
				</div>

				<v-form ref="form">
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
								@update:model-value="onModeChange(row)"
							/>
							<v-text-field
								v-model.number="row.amount"
								type="number"
								min="0"
								:label="rowCurrency(row) ? __('Amount ({0})', [rowCurrency(row)]) : __('Amount')"
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
						<v-row v-if="rowCurrency(row)" dense class="mt-0">
							<v-col cols="12">
								<v-text-field
									v-model.number="row.exchange_rate"
									type="number"
									min="0"
									:label="__('Exchange Rate (1 {0} = ? {1})', [rowCurrency(row), baseCurrency])"
									prepend-inner-icon="mdi-swap-horizontal"
									:rules="[required, positive]"
									:hint="__('Equals {0}', [formatCurrency(rowBase(row), baseCurrency)])"
									persistent-hint
								/>
							</v-col>
						</v-row>
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
					<span :class="canPay ? 'text-success' : 'text-error'">
						{{ formatCurrency(remaining, currency) }}
					</span>
				</div>
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Cancel") }}</v-btn>
				<v-btn color="primary" variant="flat" :disabled="!canPay" :loading="paying" @click="submit">
					{{ __("Pay") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { call, formatCurrency, notifySuccess } from "../client.js";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	title: { type: String, default: null },
	outstanding: { type: Number, default: 0 },
	currency: { type: String, default: null },
	// The whitelisted method (receives a `payments` list) plus the fixed args identifying the target.
	method: { type: String, default: "billing.record_payments" },
	extraArgs: { type: Object, default: () => ({}) },
	// Actions must be paid in full; other invoices allow a partial total.
	requireFull: { type: Boolean, default: false },
	// Restrict the mode list (e.g. a POS Profile's modes). null → fetch all enabled modes.
	modes: { type: Array, default: null },
});
const emit = defineEmits(["update:modelValue", "paid"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const form = ref(null);
const paying = ref(false);
const modes = ref([]);
const rows = ref([]);

const required = (v) => (v !== null && v !== "" && v !== undefined) || __("Required");
const positive = (v) => v > 0 || __("Must be greater than 0");

// Totals are kept in company currency; foreign-currency rows are converted at their rate.
const baseCurrency = computed(() => props.currency || frappe.boot.sysdefaults.currency);
const total = computed(() => rows.value.reduce((sum, r) => sum + rowBase(r), 0));
const remaining = computed(() => Number((props.outstanding - total.value).toFixed(2)));
// Foreign cash is counted in its own cents, so allow half a foreign cent of overshoot per row.
const slack = computed(() =>
	rows.value.reduce((sum, r) => sum + (rowCurrency(r) ? (Number(r.exchange_rate) || 0) * 0.005 : 0), 0.01)
);
// Full payment must land on the total; partial just may not exceed it.
const canPay = computed(() =>
	props.requireFull
		? remaining.value < 0.01 && remaining.value >= -slack.value
		: total.value > 0 && remaining.value >= -slack.value
);

function modeOf(row) {
	return modes.value.find((m) => m.name === row.mode_of_payment);
}

// Reference no/date only apply to non-Cash modes (bank/cheque).
function needsReference(row) {
	const mode = modeOf(row);
	return !!mode && mode.type !== "Cash";
}

// The row's currency when it differs from the company's (e.g. a USD cash box), else null.
function rowCurrency(row) {
	const currency = modeOf(row)?.currency;
	return currency && currency !== baseCurrency.value ? currency : null;
}

function rowBase(row) {
	const amount = Number(row.amount) || 0;
	if (!rowCurrency(row)) return amount;
	return Math.round(amount * (Number(row.exchange_rate) || 0) * 100) / 100;
}

// A prefilled company-currency amount is meaningless in a foreign currency; let the cashier enter it.
function onModeChange(row) {
	if (rowCurrency(row)) row.amount = null;
}

function blankRow(amount = null) {
	return {
		mode_of_payment: null,
		amount,
		exchange_rate: null,
		reference_no: "",
		reference_date: frappe.datetime.get_today(),
	};
}

function addRow() {
	// Prefill the new line with whatever is still owed.
	rows.value.push(blankRow(remaining.value > 0 ? remaining.value : null));
}

function removeRow(i) {
	rows.value.splice(i, 1);
}

async function loadModes() {
	modes.value = await call("billing.get_payment_modes");
}

async function submit() {
	const { valid } = await form.value.validate();
	if (!valid || !canPay.value) return;

	paying.value = true;
	try {
		const result = await call(props.method, {
			...props.extraArgs,
			payments: rows.value.map((r) => ({
				mode_of_payment: r.mode_of_payment,
				amount: r.amount,
				reference_no: r.reference_no || null,
				reference_date: r.reference_date || null,
				exchange_rate: rowCurrency(r) ? r.exchange_rate : null,
			})),
		});
		notifySuccess(__("Payment recorded"));
		open.value = false;
		emit("paid", result);
	} finally {
		paying.value = false;
	}
}

// Start each open with a single line for the full amount.
watch(open, (isOpen) => {
	if (!isOpen) return;
	rows.value = [blankRow(props.outstanding || null)];
	form.value?.resetValidation();
	if (props.modes) modes.value = props.modes;
	else if (!modes.value.length) loadModes();
});
</script>
