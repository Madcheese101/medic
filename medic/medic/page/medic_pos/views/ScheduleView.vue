<template>
	<v-card :loading="loading">
		<v-card-title class="d-flex align-center">
			<v-btn
				variant="text"
				:icon="backIcon"
				:title="__('Back')"
				class="mr-2"
				@click="emit('back')"
			/>
			{{ __("Availability Schedule") }}
			<v-chip v-if="doctorName" size="small" variant="tonal" color="primary" class="ml-3">
				{{ doctorName }}
			</v-chip>
		</v-card-title>
		<v-divider />

		<v-card-text>
			<v-alert v-if="!loading && !rows.length" type="info" variant="tonal">
				{{ __("No Doctor Schedule is linked to your user.") }}
			</v-alert>

			<v-row v-for="row in rows" :key="row.day" dense class="align-center">
				<v-col cols="12" sm="3" class="d-flex align-center">
					<v-checkbox v-model="row.is_active" :true-value="1" :false-value="0" hide-details density="comfortable" />
					<span class="font-weight-medium">{{ __(row.day) }}</span>
				</v-col>
				<v-col cols="6" sm="3">
					<v-text-field
						v-model="row.from_time"
						type="time"
						:label="__('From')"
						:disabled="!row.is_active"
						prepend-inner-icon="mdi-clock-start"
					/>
				</v-col>
				<v-col cols="6" sm="3">
					<v-text-field
						v-model="row.to_time"
						type="time"
						:label="__('To')"
						:disabled="!row.is_active"
						prepend-inner-icon="mdi-clock-end"
					/>
				</v-col>
				<v-col cols="12" sm="3">
					<v-text-field
						v-model.number="row.maximum_appointments"
						type="number"
						min="0"
						:label="__('Max Appointments')"
						:disabled="!row.is_active"
						prepend-inner-icon="mdi-counter"
					/>
				</v-col>
			</v-row>
		</v-card-text>

		<v-divider />
		<v-card-actions>
			<v-spacer />
			<v-btn color="primary" variant="flat" :loading="saving" :disabled="!rows.length" @click="save">
				{{ __("Save Schedule") }}
			</v-btn>
		</v-card-actions>
	</v-card>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRtl } from "vuetify";
import { call, notifySuccess } from "../client.js";
import { useDefaultsStore } from "../stores/defaults.js";

const emit = defineEmits(["back"]);

const { isRtl } = useRtl();
const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));
const defaultsStore = useDefaultsStore();
const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const doctorName = ref(null);

async function load() {
	loading.value = true;
	try {
		// The API takes the employee from the client, so the store must be resolved first.
		await defaultsStore.load();
		const doc = await call("profile.get_my_schedule", { employee: defaultsStore.employee });
		doctorName.value = doc?.employee_name || null;
		rows.value = (doc?.schedule || []).map((r) => ({
			day: r.day,
			is_active: r.is_active,
			from_time: r.from_time,
			to_time: r.to_time,
			maximum_appointments: r.maximum_appointments,
		}));
	} finally {
		loading.value = false;
	}
}

async function save() {
	saving.value = true;
	try {
		await call("profile.save_schedule", {
			rows: JSON.stringify(rows.value),
			employee: defaultsStore.employee,
		});
		notifySuccess(__("Schedule saved"));
		await load();
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>
