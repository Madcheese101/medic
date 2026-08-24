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
				<v-col v-if="doc.treatment_plan" cols="12" md="6">
					<v-text-field :model-value="doc.treatment_plan" :label="__('Treatment Plan')" prepend-inner-icon="mdi-clipboard-pulse-outline" readonly />
				</v-col>
			</v-row>

			<div v-if="canConfirm || canCheckIn || canComplete" class="d-flex mt-3 ga-2">
				<v-spacer />
				<v-btn
					v-if="canCheckIn"
					color="primary"
					variant="tonal"
					prepend-icon="mdi-login"
					:loading="checkingIn"
					@click="checkIn"
				>
					{{ __("Check in") }}
				</v-btn>
				<v-btn
					v-if="canConfirm"
					color="primary"
					variant="flat"
					prepend-icon="mdi-check-decagram"
					:loading="confirming"
					@click="confirm"
				>
					{{ __("Confirm") }}
				</v-btn>
				<v-btn
					v-if="canComplete"
					color="success"
					variant="flat"
					prepend-icon="mdi-check-all"
					:loading="completing"
					@click="complete"
				>
					{{ __("Mark Completed") }}
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
				:readonly="isCompleted"
				class="mb-3"
			/>
			<div class="d-flex">
				<v-spacer />
				<v-btn color="primary" variant="tonal" :disabled="isCompleted" :loading="savingNotes" @click="saveNotes">
					{{ __("Save Notes") }}
				</v-btn>
			</div>

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
					<tr v-if="!doc.actions || !doc.actions.length">
						<td colspan="4" class="text-medium-emphasis">{{ __("No actions yet") }}</td>
					</tr>
				</tbody>
			</v-table>
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
const checkingIn = ref(false);
const completing = ref(false);
const savingNotes = ref(false);
const doc = ref({});
const doctorName = ref("");
const notes = ref("");

const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));
const isCancelled = computed(() => doc.value.docstatus === 2);
// Treatment-plan sessions are confirmed and checked in from the plan, not here.
const isTreatmentSession = computed(() => !!doc.value.treatment_plan);
// Completed is terminal: it disables every other action.
const isCompleted = computed(() => doc.value.appointment_status === "مكتمل");
// Confirm is only reachable on a submitted, still-pending, non-plan appointment.
const canConfirm = computed(
	() => doc.value.docstatus === 1 && doc.value.appointment_status === "انتظار" && !isTreatmentSession.value
);
// Check-in assigns the queue; available once submitted and not yet queued.
const canCheckIn = computed(() => doc.value.docstatus === 1 && !doc.value.queue && !isTreatmentSession.value);
// Complete is offered once the patient has a queue number, until it is marked مكتمل.
const canComplete = computed(() => doc.value.docstatus === 1 && !!doc.value.queue && !isCompleted.value);

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

async function checkIn() {
	checkingIn.value = true;
	try {
		const q = await call("check_in", { appointment: props.name });
		notifySuccess(__("Checked in — queue {0}", [q]));
		await load();
	} finally {
		checkingIn.value = false;
	}
}

async function complete() {
	const ok = await confirmAction(__("Mark this appointment as completed?"));
	if (!ok) return;

	completing.value = true;
	try {
		await call("complete_appointment", { name: props.name });
		notifySuccess(__("Appointment completed"));
		await load();
	} finally {
		completing.value = false;
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
