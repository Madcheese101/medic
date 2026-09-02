<template>
	<v-text-field
		:model-value="value"
		:label="label"
		:prepend-inner-icon="icon"
		readonly
		:append-inner-icon="clickable ? 'mdi-open-in-new' : undefined"
		:class="{ 'reference-field--link': clickable }"
		@click="onClick"
		@click:append-inner="onClick"
	/>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	value: { type: String, default: null },
	label: { type: String, default: "" },
	icon: { type: String, default: null },
});
const emit = defineEmits(["open"]);

// Only a populated reference is a live link.
const clickable = computed(() => !!props.value);

function onClick() {
	if (clickable.value) emit("open");
}
</script>

<style scoped>
.reference-field--link :deep(.v-field) {
	cursor: pointer;
}
.reference-field--link :deep(.v-field__input) {
	color: rgb(var(--v-theme-primary));
	cursor: pointer;
}
</style>
