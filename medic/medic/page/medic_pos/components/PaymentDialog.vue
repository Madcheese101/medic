<template>
	<v-dialog v-model="open" max-width="480" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-cash-register" class="mr-2" />
				{{ title }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<div class="d-flex justify-space-between text-body-2 mb-1">
					<span class="text-medium-emphasis">{{ __("Total") }}</span>
					<span>{{ formatCurrency(grandTotal, currency) }}</span>
				</div>
				<div class="d-flex justify-space-between text-subtitle-1 font-weight-medium mb-3">
					<span>{{ __("Outstanding") }}</span>
					<span>{{ formatCurrency(outstanding, currency) }}</span>
				</div>

				<v-form ref="form">
					<v-text-field
						v-if="!fullOnly"
						v-model.number="payment.amount"
						type="number"
						min="0"
						:label="__('Amount')"
						prepend-inner-icon="mdi-cash"
						:rules="[required, positive]"
					/>
					<v-autocomplete
						v-model="payment.mode_of_payment"
						:items="modes"
						item-title="name"
						item-value="name"
						:label="__('Mode of Payment')"
						prepend-inner-icon="mdi-credit-card-outline"
						:rules="[required]"
						class="mt-3"
					/>
					<template v-if="needsReference">
						<v-text-field
							v-model="payment.reference_no"
							:label="__('Reference No')"
							prepend-inner-icon="mdi-pound"
							:rules="[required]"
							class="mt-3"
						/>
						<v-text-field
							v-model="payment.reference_date"
							type="date"
							:label="__('Reference Date')"
							prepend-inner-icon="mdi-calendar"
							:rules="[required]"
							class="mt-3"
						/>
					</template>
				</v-form>
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Cancel") }}</v-btn>
				<v-btn color="primary" variant="flat" :loading="paying" @click="submit">
					{{ __("Pay") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { call, formatCurrency, notifySuccess } from "../client.js";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	title: { type: String, default: null },
	grandTotal: { type: Number, default: 0 },
	outstanding: { type: Number, default: 0 },
	currency: { type: String, default: null },
	// The whitelisted method to call, plus the fixed args identifying what is being paid.
	method: { type: String, default: "add_payment" },
	extraArgs: { type: Object, default: () => ({}) },
	// Hide the amount field and always pay the full outstanding (action invoices).
	fullOnly: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue", "paid"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const form = ref(null);
const paying = ref(false);
const modes = ref([]);
const payment = reactive({ amount: null, mode_of_payment: null, reference_no: "", reference_date: "" });

const required = (v) => (v !== null && v !== "" && v !== undefined) || __("Required");
const positive = (v) => v > 0 || __("Must be greater than 0");

// Reference no/date only apply to non-Cash modes (bank/cheque), where ERPNext requires them.
const needsReference = computed(() => {
	const mode = modes.value.find((m) => m.name === payment.mode_of_payment);
	return !!mode && mode.type !== "Cash";
});

async function loadModes() {
	modes.value = await call("get_payment_modes");
}

async function submit() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	paying.value = true;
	try {
		await call(props.method, {
			...props.extraArgs,
			amount: payment.amount,
			mode_of_payment: payment.mode_of_payment,
			reference_no: payment.reference_no || null,
			reference_date: payment.reference_date || null,
		});
		notifySuccess(__("Payment recorded"));
		open.value = false;
		emit("paid");
	} finally {
		paying.value = false;
	}
}

// Reset the form and default the amount to the outstanding balance each time it opens.
watch(open, (isOpen) => {
	if (!isOpen) return;
	payment.amount = props.outstanding || null;
	payment.mode_of_payment = null;
	payment.reference_no = "";
	payment.reference_date = "";
	form.value?.resetValidation();
	if (!modes.value.length) loadModes();
});
</script>
