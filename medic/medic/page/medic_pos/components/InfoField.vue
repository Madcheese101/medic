<template>
	<div class="d-flex align-start ga-3 py-1">
		<v-icon v-if="icon" :icon="icon" size="20" class="text-medium-emphasis mt-1" />
		<div style="min-width: 0">
			<div class="text-caption text-medium-emphasis">{{ label }}</div>
			<a v-if="link && value" class="medic-ref-link text-body-1" @click="emit('open')">{{ value }}</a>
			<div v-else class="text-body-1 text-break">{{ value || value === 0 ? value : "—" }}</div>
		</div>
	</div>
</template>

<script setup>
// A read-only value on a detail page: a label over plain text, so it doesn't look editable.
// With `link`, a populated value opens its record through the `open` event.
defineProps({
	value: { type: [String, Number], default: null },
	label: { type: String, default: "" },
	icon: { type: String, default: null },
	link: { type: Boolean, default: false },
});
const emit = defineEmits(["open"]);
</script>
