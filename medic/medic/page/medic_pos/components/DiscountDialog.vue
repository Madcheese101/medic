<template>
	<v-dialog v-model="open" max-width="400" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-sale-outline" class="mr-2" />
				{{ __("Discount") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<v-form ref="form" @submit.prevent="save">
					<v-text-field
						v-model.number="pct"
						type="number"
						min="0"
						:max="maxPct"
						:label="__('Discount Percentage')"
						prepend-inner-icon="mdi-percent-outline"
						:rules="[inRange]"
						:hint="__('Maximum {0}%', [maxPct])"
						persistent-hint
					/>
				</v-form>
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Cancel") }}</v-btn>
				<v-btn color="primary" variant="flat" :loading="saving" @click="save">
					{{ __("Save") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { call, notifySuccess } from "../client.js";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	current: { type: Number, default: 0 },
	// Whitelisted method receiving `discount_percentage` plus the args identifying the target.
	method: { type: String, required: true },
	extraArgs: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["update:modelValue", "saved"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

// Clinic Setup's cap; the server enforces it too.
const maxPct = Number(frappe.boot.max_discount_percentage) || 0;
const form = ref(null);
const saving = ref(false);
const pct = ref(0);

const inRange = (v) => (v >= 0 && v <= maxPct) || __("Must be between 0 and {0}", [maxPct]);

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		await call(props.method, { ...props.extraArgs, discount_percentage: pct.value || 0 });
		notifySuccess(__("Discount saved"));
		open.value = false;
		emit("saved");
	} finally {
		saving.value = false;
	}
}

watch(open, (isOpen) => {
	if (!isOpen) return;
	pct.value = props.current || 0;
	form.value?.resetValidation();
});
</script>
