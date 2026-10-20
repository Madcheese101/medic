<template>
	<v-menu v-model="menu" :close-on-content-click="false" location="bottom start">
		<template #activator="{ props: menuProps }">
			<v-text-field
				v-bind="menuProps"
				:model-value="displayValue"
				:label="label"
				:rules="rules"
				:disabled="disabled || !employee"
				:hint="!employee ? __('Select a doctor first') : undefined"
				:persistent-hint="!employee"
				prepend-inner-icon="mdi-calendar"
				readonly
			/>
		</template>
		<v-date-picker
			:model-value="pickedDate"
			:min="minDate"
			:allowed-dates="allowedDates"
			hide-header
			@update:model-value="onPick"
		/>
	</v-menu>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { call } from "../client.js";

const props = defineProps({
	modelValue: { type: String, default: null },
	employee: { type: String, default: null },
	label: { type: String, default: "" },
	rules: { type: Array, default: () => [] },
	disabled: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue"]);

const menu = ref(false);
const weekdayMax = ref({}); // { "0".."6": maximum_appointments } for active weekdays
const booked = ref({}); // { "YYYY-MM-DD": count } for future appointments
const todayStr = ref(null);

// Local YYYY-MM-DD (avoid the UTC shift of toISOString).
function fmt(date) {
	const y = date.getFullYear();
	const m = String(date.getMonth() + 1).padStart(2, "0");
	const d = String(date.getDate()).padStart(2, "0");
	return `${y}-${m}-${d}`;
}

function parse(str) {
	if (!str) return null;
	const [y, m, d] = str.split("-").map(Number);
	return new Date(y, m - 1, d);
}

const pickedDate = computed(() => parse(props.modelValue));
const minDate = computed(() => parse(todayStr.value));
const displayValue = computed(() =>
	props.modelValue ? frappe.datetime.str_to_user(props.modelValue) : "",
);

// Enable a date only when it is today-or-later, on an active weekday, under the cap.
function allowedDates(date) {
	const iso = fmt(date);
	if (todayStr.value && iso < todayStr.value) return false;
	const max = weekdayMax.value[String(date.getDay())];
	if (max === undefined) return false; // inactive weekday / no schedule
	if (max === 0) return true; // 0 = unlimited
	return (booked.value[iso] || 0) < max;
}

async function loadAvailability() {
	if (!props.employee) {
		weekdayMax.value = {};
		booked.value = {};
		todayStr.value = null;
		return;
	}
	const res = await call("appointments.get_doctor_availability", { employee: props.employee });
	weekdayMax.value = res.weekday_max || {};
	booked.value = res.booked || {};
	todayStr.value = res.today;
	// Drop a selection that the new doctor's schedule no longer allows.
	if (props.modelValue && !allowedDates(parse(props.modelValue))) {
		emit("update:modelValue", null);
	}
}

function onPick(date) {
	emit("update:modelValue", date ? fmt(date) : null);
	menu.value = false;
}

watch(() => props.employee, loadAvailability, { immediate: true });
</script>
