<template>
	<div>
		<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ label }}</div>
		<v-table density="comfortable">
			<thead>
				<tr>
					<th>{{ __("Illness") }}</th>
					<th style="width: 56px" />
				</tr>
			</thead>
			<tbody>
				<tr v-for="(row, index) in rows" :key="index">
					<td class="py-2">
						<v-autocomplete
							:model-value="row"
							:items="itemsFor(row)"
							:loading="loading"
							density="compact"
							@update:model-value="(value) => setRow(index, value)"
							@update:search="search"
						/>
					</td>
					<td>
						<v-btn
							size="small"
							variant="text"
							color="error"
							icon="mdi-delete-outline"
							:title="__('Remove')"
							@click="removeRow(index)"
						/>
					</td>
				</tr>
				<tr v-if="!rows.length">
					<td colspan="2" class="text-medium-emphasis">{{ __("No rows") }}</td>
				</tr>
			</tbody>
		</v-table>

		<v-btn
			size="small"
			variant="tonal"
			color="primary"
			prepend-icon="mdi-plus"
			class="mt-2"
			@click="addRow"
		>
			{{ __("Add Row") }}
		</v-btn>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { customSearchLink } from "../client.js";

const props = defineProps({
	modelValue: { type: Array, default: () => [] },
	label: { type: String, default: "" },
	illnessType: { type: String, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const options = ref([]);
const loading = ref(false);

const rows = computed(() => props.modelValue);

// A saved row's value may not be in the current search results, so keep it selectable.
function itemsFor(row) {
	return row && !options.value.includes(row) ? [row, ...options.value] : options.value;
}

async function search(txt) {
	loading.value = true;
	const results = await customSearchLink("Illness", txt, { illness_type: props.illnessType });
	options.value = results.map((r) => r.value);
	loading.value = false;
}

function update(next) {
	emit("update:modelValue", next);
}

function setRow(index, value) {
	const next = [...rows.value];
	next[index] = value;
	update(next);
}

function addRow() {
	update([...rows.value, ""]);
}

function removeRow(index) {
	update(rows.value.filter((_, i) => i !== index));
}

onMounted(() => search(""));
</script>
