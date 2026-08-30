<template>
	<v-dialog v-model="open" max-width="820" :fullscreen="mobile" :retain-focus="false" scrollable>
		<v-card :loading="loading">
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-clipboard-pulse-outline" class="mr-2" />
				<span class="text-truncate">{{ plan.service_name || plan.service || __("Treatment Plan") }}</span>
				<v-spacer />
				<v-chip :color="treatmentStatusColor(plan.status)" variant="tonal" size="small">
					{{ plan.status }}
				</v-chip>
			</v-card-title>
			<v-divider />

			<v-card-text>
				<v-text-field
					:model-value="plan.invoice"
					:label="__('Invoice')"
					prepend-inner-icon="mdi-receipt-text-outline"
					readonly
					class="mb-3"
				/>

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
				<div class="d-flex align-center ga-2 mb-4">
					<v-chip size="small" variant="tonal" color="primary">
						{{ __("Sessions") }}: {{ plan.completed_sessions || 0 }} / {{ plan.total_sessions }}
					</v-chip>
					<v-spacer />
					<v-btn
						v-if="!plan.invoice"
						size="small"
						variant="tonal"
						color="primary"
						prepend-icon="mdi-receipt-text-plus-outline"
						:loading="creatingInvoice"
						@click="createInvoice"
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

				<v-divider class="mb-3" />

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
							<td>{{ s.name }}</td>
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

			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Close") }}</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>

	<SplitPaymentDialog
		v-model="payOpen"
		:title="__('Add Payment')"
		:outstanding="plan.outstanding_amount"
		:currency="plan.currency"
		method="record_payments"
		:extra-args="{ invoice: plan.invoice }"
		@paid="onPaid"
	/>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { call, formatCurrency, notifySuccess } from "../client.js";
import { appointmentStatusColor, treatmentStatusColor } from "../constants.js";
import SplitPaymentDialog from "./SplitPaymentDialog.vue";
import DoctorDatePicker from "./DoctorDatePicker.vue";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	name: { type: String, default: null },
});
const emit = defineEmits(["update:modelValue", "changed"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const loading = ref(false);
const addingSession = ref(false);
const checkingIn = ref(null);
const creatingInvoice = ref(false);
const plan = ref({ sessions: [] });
const sessionDate = ref(null);

const payOpen = ref(false);

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
		await call("create_session", {
			treatment_plan: props.name,
			appointment_date: sessionDate.value,
		});
		notifySuccess(__("Session added"));
		sessionDate.value = null;
		await load();
		emit("changed");
	} finally {
		addingSession.value = false;
	}
}

async function createInvoice() {
	creatingInvoice.value = true;
	try {
		await call("create_treatment_plan_invoice", { name: props.name });
		notifySuccess(__("Invoice created"));
		await load();
		emit("changed");
	} finally {
		creatingInvoice.value = false;
	}
}

async function checkIn(appointment) {
	checkingIn.value = appointment;
	try {
		const q = await call("check_in", { appointment });
		notifySuccess(__("Checked in — queue {0}", [q]));
		await load();
		emit("changed");
	} finally {
		checkingIn.value = null;
	}
}

async function onPaid() {
	await load();
	emit("changed");
}

watch(open, (isOpen) => {
	if (isOpen && props.name) load();
});
</script>
