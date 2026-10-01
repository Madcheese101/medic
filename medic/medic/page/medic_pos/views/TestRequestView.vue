<template>
	<TestRequestForm :test-request="name" @cancel="goBack" />
</template>

<script setup>
import TestRequestForm from "../components/TestRequestForm.vue";

defineProps({ name: { type: String, default: null } });
const emit = defineEmits(["navigate"]);

function goBack() {
	emit("navigate", "test-requests");
}
</script>
