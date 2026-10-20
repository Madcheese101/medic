<template>
	<v-alert v-if="matches.length" type="warning" variant="tonal" density="compact" class="mt-2">
		{{ __("This mobile number already belongs to {0}.", [names]) }}
	</v-alert>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { call, debounce } from "../client.js";

// A warning, not a block: family members often share one mobile number.
const props = defineProps({
	phone: { type: String, default: "" },
	// The patient being edited, who is not a duplicate of themselves.
	exclude: { type: String, default: null },
});

const matches = ref([]);
const names = computed(() => matches.value.map((p) => `${p.customer_name} (${p.name})`).join(", "));

// Checked as the number is typed; a failed check just leaves the warning off.
const check = debounce(async (phone) => {
	if (!phone) {
		matches.value = [];
		return;
	}
	matches.value = await call("patients.patients_with_phone", {
		phone_number: phone,
		exclude: props.exclude,
	}).catch(() => []);
}, 500);

watch(() => props.phone, check, { immediate: true });
</script>
