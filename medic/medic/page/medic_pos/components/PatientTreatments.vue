<template>
	<div>
		<div class="d-flex align-center mb-2">
			<v-spacer />
			<v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-plus" @click="newOpen = true">
				{{ __("New Treatment") }}
			</v-btn>
		</div>

		<v-table density="comfortable">
			<thead>
				<tr>
					<th>{{ __("Plan") }}</th>
					<th>{{ __("Service") }}</th>
					<th>{{ __("Status") }}</th>
					<th>{{ __("Sessions") }}</th>
					<th>{{ __("Paid") }}</th>
					<th />
				</tr>
			</thead>
			<tbody>
				<tr v-for="p in plans" :key="p.name">
					<td>{{ p.name }}</td>
					<td>{{ p.service }}</td>
					<td>
						<v-chip size="x-small" variant="tonal" :color="treatmentStatusColor(p.status)">{{ p.status }}</v-chip>
					</td>
					<td>{{ p.completed_sessions || 0 }} / {{ p.total_sessions }}</td>
					<td>{{ Math.round((p.paid_pct || 0) * 100) }}%</td>
					<td class="text-end">
						<v-btn size="small" variant="tonal" color="primary" icon="mdi-eye" :title="__('Open')" @click="refs.openTreatmentPlan(p.name)" />
					</td>
				</tr>
				<tr v-if="!loading && !plans.length">
					<td colspan="6" class="text-medium-emphasis">{{ __("No treatment plans") }}</td>
				</tr>
			</tbody>
		</v-table>

		<NewTreatmentDialog v-model="newOpen" :customer="customer" @created="load" />
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { call } from "../client.js";
import { treatmentStatusColor } from "../constants.js";
import NewTreatmentDialog from "./NewTreatmentDialog.vue";
import { useReferences } from "../references.js";

const props = defineProps({ customer: { type: String, default: null } });

const refs = useReferences();
const plans = ref([]);
const loading = ref(false);
const newOpen = ref(false);

async function load() {
	if (!props.customer) return;
	loading.value = true;
	try {
		plans.value = await call("treatments.get_treatment_plans", { customer: props.customer });
	} finally {
		loading.value = false;
	}
}

onMounted(load);
</script>
