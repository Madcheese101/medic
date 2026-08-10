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
			<span class="text-truncate">{{ doc.name || __("Appointment") }}</span>
			<v-spacer />
			<v-chip v-if="isCancelled" color="error" variant="flat" size="large">
				{{ __("Cancelled") }}
			</v-chip>
			<v-chip v-else :color="appointmentStatusColor(doc.appointment_status)" variant="flat" size="large">
				{{ doc.appointment_status || "—" }}
			</v-chip>
		</v-card-title>
		<v-divider />

		<v-card-text>
			<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Appointment Details") }}</div>
			<v-row dense>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.appointment_type" :label="__('Appointment Type')" prepend-inner-icon="mdi-clipboard-text-outline" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="formatDate(doc.appointment_date)" :label="__('Appointment Date')" prepend-inner-icon="mdi-calendar" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.customer_name" :label="__('Patient')" prepend-inner-icon="mdi-account-outline" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doctorName" :label="__('Doctor')" prepend-inner-icon="mdi-doctor" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.service_type" :label="__('Service Type')" prepend-inner-icon="mdi-shape-outline" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.service" :label="__('Service')" prepend-inner-icon="mdi-medical-bag" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.invoice" :label="__('Invoice')" prepend-inner-icon="mdi-receipt-text-outline" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.queue" :label="__('Queue')" prepend-inner-icon="mdi-counter" readonly />
				</v-col>
			</v-row>

			<div v-if="canConfirm" class="d-flex mt-3">
				<v-spacer />
				<v-btn color="primary" variant="flat" prepend-icon="mdi-check-decagram" :loading="confirming" @click="confirm">
					{{ __("Confirm") }}
				</v-btn>
			</div>

			<v-divider class="my-5" />

			<v-textarea
				v-model="notes"
				:label="__('Notes')"
				variant="outlined"
				rows="3"
				auto-grow
				hide-details="auto"
				class="mb-3"
			/>
			<div class="d-flex">
				<v-spacer />
				<v-btn color="primary" variant="tonal" :loading="savingNotes" @click="saveNotes">
					{{ __("Save Notes") }}
				</v-btn>
			</div>

			<template v-if="doc.actions && doc.actions.length">
				<v-divider class="my-5" />
				<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Actions") }}</div>
				<v-table density="comfortable">
					<thead>
						<tr>
							<th>{{ __("Invoice") }}</th>
							<th>{{ __("Invoice Type") }}</th>
							<th>{{ __("Action Type") }}</th>
							<th>{{ __("Paid") }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(row, i) in doc.actions" :key="i">
							<td>{{ row.invoice }}</td>
							<td>{{ row.invoice_type }}</td>
							<td>{{ row.action_type }}</td>
							<td>
								<v-icon :icon="row.paid ? 'mdi-check-circle' : 'mdi-close-circle-outline'" :color="row.paid ? 'success' : 'medium-emphasis'" />
							</td>
						</tr>
					</tbody>
				</v-table>
			</template>
		</v-card-text>
	</v-card>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRtl } from "vuetify";
import { call, confirmAction, notifySuccess } from "../client.js";
import { appointmentStatusColor } from "../constants.js";

const props = defineProps({ name: { type: String, default: null } });
const emit = defineEmits(["back"]);

const { isRtl } = useRtl();
const loading = ref(false);
const confirming = ref(false);
const savingNotes = ref(false);
const doc = ref({});
const doctorName = ref("");
const notes = ref("");

const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));
const isCancelled = computed(() => doc.value.docstatus === 2);
// Confirm is only reachable on a submitted, still-pending appointment.
const canConfirm = computed(() => doc.value.docstatus === 1 && doc.value.appointment_status === "انتظار");

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

async function load() {
	loading.value = true;
	try {
		const data = await call("get_appointment", { name: props.name });
		doc.value = data;
		doctorName.value = data.doctor_name || data.employee;
		notes.value = data.notes || "";
	} finally {
		loading.value = false;
	}
}

async function confirm() {
	const ok = await confirmAction(__("Create the invoice and confirm this appointment?"));
	if (!ok) return;

	confirming.value = true;
	try {
		await call("confirm_appointment", { name: props.name });
		notifySuccess(__("Appointment confirmed"));
		await load();
	} finally {
		confirming.value = false;
	}
}

async function saveNotes() {
	savingNotes.value = true;
	try {
		await call("save_appointment_notes", { name: props.name, notes: notes.value });
		notifySuccess(__("Notes saved"));
	} finally {
		savingNotes.value = false;
	}
}

onMounted(load);
</script>
