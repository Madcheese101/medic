<template>
	<v-card v-if="!prescribing && !testing" :loading="loading">
		<v-card-title class="d-flex align-center">
			<v-btn
				variant="text"
				:icon="backIcon"
				:title="__('Back')"
				class="mr-2"
				@click="emit('back')"
			/>
			<span class="text-truncate">{{ doc.name || __("Appointment") }}</span>
			<v-btn
				v-if="doc.name"
				variant="text"
				icon="mdi-printer"
				:title="__('Print')"
				class="ml-1"
				@click="printDoc('Patient Appointment', doc.name)"
			/>
			<v-spacer />
			<v-menu v-if="doc.docstatus === 1 && !isCompleted" location="bottom end">
				<template #activator="{ props: menuProps }">
					<v-btn
						v-bind="menuProps"
						size="small"
						variant="tonal"
						color="primary"
						prepend-icon="mdi-plus"
						append-icon="mdi-menu-down"
						class="mr-3"
					>
						{{ __("Add Action") }}
					</v-btn>
				</template>
				<v-list density="comfortable">
					<v-list-item
						v-for="t in ACTION_TYPES"
						:key="t"
						:title="t"
						@click="openAction(t)"
					/>
				</v-list>
			</v-menu>
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
					<v-text-field :model-value="doc.service_name || doc.service" :label="__('Service')" prepend-inner-icon="mdi-medical-bag" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<ReferenceField :value="doc.invoice" :label="__('Invoice')" icon="mdi-receipt-text-outline" @open="refs.openInvoice(doc.invoice)" />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="doc.queue" :label="__('Queue')" prepend-inner-icon="mdi-counter" readonly />
				</v-col>
				<v-col v-if="doc.treatment_plan" cols="12" md="6">
					<ReferenceField :value="doc.treatment_plan" :label="__('Treatment Plan')" icon="mdi-clipboard-pulse-outline" @open="refs.openTreatmentPlan(doc.treatment_plan)" />
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
						<th />
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
						<td class="text-end">
							<v-btn
								v-if="row.action_type === 'علاج' && !row.paid"
								size="small"
								variant="tonal"
								color="primary"
								prepend-icon="mdi-cash-register"
								@click="payAction(row)"
							>
								{{ __("Confirm & Pay") }}
							</v-btn>
							<v-btn
								v-if="row.action_type === 'وصفة طبية'"
								size="small"
								variant="tonal"
								color="primary"
								prepend-icon="mdi-prescription"
								@click="viewPrescription(row)"
							>
								{{ __("View") }}
							</v-btn>
							<v-btn
								v-if="row.invoice_type === 'Test Request'"
								size="small"
								variant="tonal"
								color="primary"
								prepend-icon="mdi-test-tube"
								@click="viewTestRequest(row)"
							>
								{{ __("View") }}
							</v-btn>
						</td>
					</tr>
					<tr v-if="!doc.actions || !doc.actions.length">
						<td colspan="5" class="text-medium-emphasis">{{ __("No actions yet") }}</td>
					</tr>
				</tbody>
			</v-table>
		</v-card-text>
	</v-card>

	<PrescriptionForm
		v-if="prescribing"
		:appointment="doc.name"
		:patient="doc.customer_name"
		:prescription="openPrescription"
		@saved="closePrescription"
		@cancel="closePrescription"
	/>

	<TestRequestForm
		v-if="testing"
		:appointment="doc.name"
		:patient="doc.customer"
		:patient-name="doc.customer_name"
		:test-request="openTestRequest"
		@saved="closeTestRequest"
		@cancel="closeTestRequest"
	/>

	<AppointmentActionDialog
		v-model="actionOpen"
		:appointment="doc.name"
		:service-type="doc.service_type"
		:action-type="selectedActionType"
		@created="load"
	/>
	<SplitPaymentDialog
		v-model="payOpen"
		:title="__('Confirm & Pay')"
		:outstanding="payTarget.outstanding_amount"
		:currency="payTarget.currency"
		method="pay_appointment_action"
		:extra-args="{ invoice: payTarget.invoice }"
		require-full
		@paid="load"
	/>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRtl } from "vuetify";
import { call, confirmAction, notifySuccess, printDoc } from "../client.js";
import { ACTION_TYPES, appointmentStatusColor } from "../constants.js";
import AppointmentActionDialog from "../components/AppointmentActionDialog.vue";
import PrescriptionForm from "../components/PrescriptionForm.vue";
import TestRequestForm from "../components/TestRequestForm.vue";
import SplitPaymentDialog from "../components/SplitPaymentDialog.vue";
import ReferenceField from "../components/ReferenceField.vue";
import { useReferences } from "../references.js";

const refs = useReferences();

const props = defineProps({ name: { type: String, default: null } });
const emit = defineEmits(["back"]);

const { isRtl } = useRtl();
const loading = ref(false);
const confirming = ref(false);
const checkingIn = ref(false);
const completing = ref(false);
const savingNotes = ref(false);
const actionOpen = ref(false);
const selectedActionType = ref(null);
const payOpen = ref(false);
const prescribing = ref(false);
const openPrescription = ref(null);
const testing = ref(false);
const openTestRequest = ref(null);
const payTarget = ref({});
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
// Check-in assigns the queue; available once submitted, not yet queued, and only on the appointment's own day.
const canCheckIn = computed(
	() =>
		doc.value.docstatus === 1 &&
		!doc.value.queue &&
		!isTreatmentSession.value &&
		doc.value.appointment_status !== "ملغي" &&
		doc.value.appointment_date === frappe.datetime.get_today()
);
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

// The dropdown picks the action type; the dialog then only asks for the service.
function openAction(actionType) {
	// Prescriptions are not billable, so they get their own inline form instead of the invoice dialog.
	if (actionType === "وصفة طبية") {
		openPrescription.value = null;
		prescribing.value = true;
		return;
	}
	// Lab actions open an inline Test Request form, mirroring the prescription flow.
	if (actionType === "تحليل") {
		openTestRequest.value = null;
		testing.value = true;
		return;
	}
	selectedActionType.value = actionType;
	actionOpen.value = true;
}

// The row's invoice field carries the Prescription name; the form decides view vs. edit from invoice_created.
function viewPrescription(row) {
	openPrescription.value = row.invoice;
	prescribing.value = true;
}

async function closePrescription() {
	prescribing.value = false;
	openPrescription.value = null;
	await load();
}

// The row's invoice field carries the Test Request name.
function viewTestRequest(row) {
	openTestRequest.value = row.invoice;
	testing.value = true;
}

async function closeTestRequest() {
	testing.value = false;
	openTestRequest.value = null;
	await load();
}

// علاج actions are paid in full; the row carries its invoice totals from get_appointment.
function payAction(row) {
	payTarget.value = row;
	payOpen.value = true;
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
