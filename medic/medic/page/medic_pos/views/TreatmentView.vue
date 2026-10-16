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
			<span class="text-truncate">{{ plan.name || __("Treatment Plan") }}</span>
			<v-btn
				v-if="plan.name"
				variant="text"
				icon="mdi-printer"
				:title="__('Print')"
				class="ml-1"
				@click="printDoc('Treatment Plan', plan.name)"
			/>
			<v-spacer />
			<v-chip :color="treatmentStatusColor(plan.status)" variant="flat" size="large">
				{{ plan.status || "—" }}
			</v-chip>
		</v-card-title>
		<v-divider />

		<v-card-text>
			<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Treatment Details") }}</div>
			<v-row dense>
				<v-col cols="12" md="6">
					<v-text-field :model-value="plan.customer_name" :label="__('Patient')" prepend-inner-icon="mdi-account-outline" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="plan.doctor_name || plan.employee" :label="__('Doctor')" prepend-inner-icon="mdi-doctor" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<v-text-field :model-value="plan.service_name || plan.service" :label="__('Service')" prepend-inner-icon="mdi-medical-bag" readonly />
				</v-col>
				<v-col cols="12" md="6">
					<ReferenceField :value="plan.invoice" :label="__('Invoice')" icon="mdi-receipt-text-outline" @open="refs.openInvoice(plan.invoice)" />
				</v-col>
			</v-row>

			<v-divider class="my-5" />

			<!-- Payment progress -->
			<div class="d-flex align-center justify-space-between mb-1">
				<span class="text-body-2">
					{{ formatCurrency(plan.paid, plan.currency) }} / {{ formatCurrency(plan.grand_total, plan.currency) }}
				</span>
				<span class="text-body-2 text-medium-emphasis">
					{{ __("Outstanding") }}: {{ formatCurrency(plan.outstanding_amount, plan.currency) }}
				</span>
			</div>
			<v-progress-linear :model-value="paidPct" color="success" height="10" rounded class="mb-2" />
			<div class="d-flex align-center flex-wrap ga-2 mb-4">
				<v-chip size="small" variant="tonal" color="primary">
					{{ __("Sessions") }}: {{ plan.completed_sessions || 0 }} / {{ plan.total_sessions }}
				</v-chip>
				<v-btn
					v-if="['Pending', 'Active'].includes(plan.status)"
					size="small"
					variant="text"
					color="primary"
					prepend-icon="mdi-plus-circle-outline"
					@click="openExtraSessions"
				>
					{{ __("More Sessions") }}
				</v-btn>
				<v-chip v-if="plan.discount_percentage" size="small" variant="tonal" color="success">
					{{ __("Discount") }}: {{ plan.discount_percentage }}%
				</v-chip>
				<v-spacer />
				<v-btn
					v-if="canDiscount"
					size="small"
					variant="tonal"
					color="primary"
					prepend-icon="mdi-sale-outline"
					@click="discountOpen = true"
				>
					{{ __("Discount") }}
				</v-btn>
				<v-btn
					v-if="!plan.invoice"
					size="small"
					variant="tonal"
					color="primary"
					prepend-icon="mdi-receipt-text-plus-outline"
					@click="depositOpen = true"
				>
					{{ __("Create Invoice") }}
				</v-btn>
				<v-btn v-else size="small" variant="tonal" color="primary" prepend-icon="mdi-cash-plus" @click="payOpen = true">
					{{ __("Add Payment") }}
				</v-btn>
				<DoctorDatePicker
					v-if="plan.invoice"
					v-model="sessionDate"
					:employee="plan.employee"
					:label="__('Session Date')"
					style="max-width: 220px"
				/>
				<v-btn
					size="small"
					variant="flat"
					color="primary"
					prepend-icon="mdi-plus"
					:disabled="!plan.invoice || !sessionDate"
					:loading="addingSession"
					@click="addSession"
				>
					{{ __("Add Session") }}
				</v-btn>
			</div>

			<v-divider class="my-5" />

			<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Sessions") }}</div>
			<v-table density="comfortable">
				<thead>
					<tr>
						<th>#</th>
						<th>{{ __("Appointment") }}</th>
						<th>{{ __("Date") }}</th>
						<th>{{ __("Status") }}</th>
						<th>{{ __("Queue") }}</th>
						<th />
					</tr>
				</thead>
				<tbody>
					<tr v-for="s in plan.sessions" :key="s.name">
						<td>{{ s.session_no }}</td>
						<td><a class="medic-ref-link" @click="refs.openAppointment(s.name)">{{ s.name }}</a></td>
						<td>{{ formatDate(s.appointment_date) }}</td>
						<td>
							<v-chip size="x-small" variant="tonal" :color="appointmentStatusColor(s.appointment_status)">
								{{ s.appointment_status || "—" }}
							</v-chip>
						</td>
						<td>{{ s.queue || "—" }}</td>
						<td class="text-end">
							<v-btn
								v-if="!s.queue"
								size="small"
								variant="tonal"
								color="primary"
								prepend-icon="mdi-login"
								:loading="checkingIn === s.name"
								@click="checkIn(s.name)"
							>
								{{ __("Check in") }}
							</v-btn>
						</td>
					</tr>
					<tr v-if="!plan.sessions || !plan.sessions.length">
						<td colspan="6" class="text-medium-emphasis">{{ __("No sessions yet") }}</td>
					</tr>
				</tbody>
			</v-table>
		</v-card-text>
	</v-card>

	<v-dialog v-model="extraOpen" max-width="400" :retain-focus="false">
		<v-card>
			<v-card-title>{{ __("Add More Sessions") }}</v-card-title>
			<v-divider />
			<v-card-text>
				<v-text-field
					v-model.number="extraSessions"
					type="number"
					min="1"
					:label="__('Sessions to add')"
					prepend-inner-icon="mdi-counter"
					:hint="plan.invoice ? __('The plan is already invoiced; the extra sessions are not charged.') : ''"
					persistent-hint
				/>
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="extraOpen = false">{{ __("Cancel") }}</v-btn>
				<v-btn
					color="primary"
					variant="flat"
					:disabled="!(extraSessions >= 1)"
					:loading="addingExtra"
					@click="addExtraSessions"
				>
					{{ __("Add") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>

	<DiscountDialog
		v-model="discountOpen"
		:current="plan.discount_percentage"
		method="set_treatment_plan_discount"
		:extra-args="{ name: props.name }"
		@saved="load"
	/>

	<SplitPaymentDialog
		v-model="payOpen"
		:title="__('Add Payment')"
		:outstanding="plan.outstanding_amount"
		:currency="plan.currency"
		method="record_payments"
		:extra-args="{ invoice: plan.invoice }"
		@paid="load"
	/>

	<SplitPaymentDialog
		v-model="depositOpen"
		:title="__('Create Invoice & Collect Deposit')"
		:outstanding="plan.estimated_total"
		:currency="plan.currency"
		method="create_treatment_plan_invoice"
		:extra-args="{ name: props.name }"
		:modes="cashierModes"
		@paid="load"
	/>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRtl } from "vuetify";
import { call, formatCurrency, notifySuccess, printDoc } from "../client.js";
import { appointmentStatusColor, treatmentStatusColor } from "../constants.js";
import SplitPaymentDialog from "../components/SplitPaymentDialog.vue";
import DoctorDatePicker from "../components/DoctorDatePicker.vue";
import DiscountDialog from "../components/DiscountDialog.vue";
import ReferenceField from "../components/ReferenceField.vue";
import { useReferences } from "../references.js";

const props = defineProps({ name: { type: String, default: null } });
const emit = defineEmits(["back"]);

const refs = useReferences();
const { isRtl } = useRtl();

const loading = ref(false);
const addingSession = ref(false);
const checkingIn = ref(null);
const plan = ref({ sessions: [] });
const sessionDate = ref(null);
const payOpen = ref(false);
const depositOpen = ref(false);
const extraOpen = ref(false);
const discountOpen = ref(false);
const extraSessions = ref(1);
const addingExtra = ref(false);

// Cashier POS Profile modes for the deposit; null falls back to all modes.
const cashierModes = frappe.boot.cashier_payment_modes?.length ? frappe.boot.cashier_payment_modes : null;

const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));
// The plan invoice is submitted on creation, so the discount is only open before it exists.
const canDiscount = computed(
	() =>
		!plan.value.invoice &&
		["Pending", "Active"].includes(plan.value.status) &&
		["Doctor", "Cashier"].some((r) => frappe.user_roles.includes(r))
);
const paidPct = computed(() => (plan.value.paid_pct || 0) * 100);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

async function load() {
	loading.value = true;
	try {
		plan.value = await call("get_treatment_plan", { name: props.name });
	} finally {
		loading.value = false;
	}
}

async function addSession() {
	addingSession.value = true;
	try {
		await call("create_session", { treatment_plan: props.name, appointment_date: sessionDate.value });
		notifySuccess(__("Session added"));
		sessionDate.value = null;
		await load();
	} finally {
		addingSession.value = false;
	}
}

function openExtraSessions() {
	extraSessions.value = 1;
	extraOpen.value = true;
}

async function addExtraSessions() {
	addingExtra.value = true;
	try {
		await call("add_treatment_sessions", { name: props.name, sessions: extraSessions.value });
		notifySuccess(__("Sessions added"));
		extraOpen.value = false;
		await load();
	} finally {
		addingExtra.value = false;
	}
}

async function checkIn(appointment) {
	checkingIn.value = appointment;
	try {
		const q = await call("check_in", { appointment });
		notifySuccess(__("Checked in — queue {0}", [q]));
		await load();
	} finally {
		checkingIn.value = null;
	}
}

onMounted(load);
</script>
