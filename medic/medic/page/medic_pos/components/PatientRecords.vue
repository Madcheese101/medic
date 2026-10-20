<template>
	<div ref="root">
		<v-tabs v-model="tab" color="primary" density="comfortable" show-arrows class="mb-3">
			<v-tab value="visits" prepend-icon="mdi-calendar-check-outline">{{ __("Visits") }}</v-tab>
			<v-tab value="invoices" prepend-icon="mdi-receipt-text-outline">{{ __("Invoices") }}</v-tab>
			<v-tab value="prescriptions" prepend-icon="mdi-prescription">{{ __("Prescriptions") }}</v-tab>
			<v-tab value="tests" prepend-icon="mdi-test-tube">{{ __("Lab Tests") }}</v-tab>
			<v-tab value="treatments" prepend-icon="mdi-clipboard-pulse-outline">{{ __("Treatments") }}</v-tab>
		</v-tabs>

		<!-- Each table mounts with its tab, which loads it. -->
		<v-data-table-server
			v-if="tab === 'visits'"
			v-model:page="visits.page"
			:headers="visitHeaders"
			:items="visits.rows"
			:items-length="visits.total"
			:loading="visits.loading"
			density="comfortable"
			:no-data-text="__('No appointments found')"
			@update:options="visits.onOptions"
		>
			<template #item.name="{ item }">
				<a class="medic-ref-link" @click="refs.openAppointment(item.name)">{{ item.name }}</a>
			</template>
			<template #item.appointment_date="{ item }">{{ formatDate(item.appointment_date) }}</template>
			<template #item.appointment_type="{ item }">{{ label(item.appointment_type, "Patient Appointment") }}</template>
			<template #item.appointment_status="{ item }">
				<v-chip size="small" variant="tonal" :color="appointmentStatusColor(item.appointment_status)">
					{{ label(item.appointment_status, "Patient Appointment") }}
				</v-chip>
			</template>
		</v-data-table-server>

		<template v-else-if="tab === 'invoices'">
			<v-switch
				v-model="outstandingOnly"
				:label="__('Outstanding only')"
				color="primary"
				density="compact"
				hide-details
				@update:model-value="invoices.reload"
			/>
			<v-data-table-server
				v-model:page="invoices.page"
				:headers="invoiceHeaders"
				:items="invoices.rows"
				:items-length="invoices.total"
				:loading="invoices.loading"
				density="comfortable"
				:no-data-text="__('No invoices found')"
				@update:options="invoices.onOptions"
			>
				<template #item.name="{ item }">
					<a class="medic-ref-link" @click="refs.openInvoice(item.name)">{{ item.name }}</a>
				</template>
				<template #item.posting_date="{ item }">{{ formatDate(item.posting_date) }}</template>
				<template #item.grand_total="{ item }">{{ formatCurrency(item.grand_total, item.currency) }}</template>
				<template #item.outstanding_amount="{ item }">{{ formatCurrency(item.outstanding_amount, item.currency) }}</template>
				<template #item.status="{ item }">
					<v-chip size="small" variant="tonal" :color="invoiceStatusColor(item.status)">{{ item.status || "—" }}</v-chip>
				</template>
			</v-data-table-server>
		</template>

		<v-data-table-server
			v-else-if="tab === 'prescriptions'"
			v-model:page="prescriptions.page"
			:headers="prescriptionHeaders"
			:items="prescriptions.rows"
			:items-length="prescriptions.total"
			:loading="prescriptions.loading"
			density="comfortable"
			:no-data-text="__('No prescriptions found')"
			@update:options="prescriptions.onOptions"
		>
			<template #item.posting_date="{ item }">{{ formatDate(item.posting_date) }}</template>
			<template #item.appointment="{ item }">
				<a v-if="item.appointment" class="medic-ref-link" @click="refs.openAppointment(item.appointment)">{{ item.appointment }}</a>
				<span v-else class="text-medium-emphasis">—</span>
			</template>
			<template #item.invoice_created="{ item }">
				<v-chip size="small" variant="tonal" :color="item.invoice_created ? 'success' : 'warning'">
					{{ item.invoice_created ? __("Invoiced") : __("Pending") }}
				</v-chip>
			</template>
			<template #item.actions="{ item }">
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-printer"
					:title="__('Print')"
					@click="printDoc('Prescription', item.name)"
				/>
			</template>
		</v-data-table-server>

		<v-data-table-server
			v-else-if="tab === 'tests'"
			v-model:page="tests.page"
			:headers="testHeaders"
			:items="tests.rows"
			:items-length="tests.total"
			:loading="tests.loading"
			density="comfortable"
			:no-data-text="__('No test requests found')"
			@update:options="tests.onOptions"
		>
			<template #item.name="{ item }">
				<a class="medic-ref-link" @click="refs.openTestRequest(item.name)">{{ item.name }}</a>
			</template>
			<template #item.posting_date="{ item }">{{ formatDate(item.posting_date) }}</template>
			<template #item.status="{ item }">
				<v-chip size="small" variant="tonal" :color="testRequestStatusColor(item.status)">{{ item.status }}</v-chip>
			</template>
			<template #item.paid="{ item }">
				<span v-if="item.sales_invoice">{{ Math.round((item.paid_pct || 0) * 100) }}%</span>
				<span v-else class="text-medium-emphasis">—</span>
			</template>
		</v-data-table-server>

		<PatientTreatments v-else :customer="customer" />
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { formatCurrency, printDoc } from "../client.js";
import {
	appointmentStatusColor,
	invoiceStatusColor,
	label,
	testRequestStatusColor,
} from "../constants.js";
import { useReferences } from "../references.js";
import { useServerTable } from "../serverTable.js";
import PatientTreatments from "./PatientTreatments.vue";

// The patient file's history: everything recorded for one patient, a tab per kind of record.
const props = defineProps({ customer: { type: String, required: true } });

const refs = useReferences();
const root = ref(null);
const tab = ref("visits");
const outstandingOnly = ref(false);

const visits = useServerTable("appointments.get_appointments", () => ({ customer: props.customer }));
const invoices = useServerTable("billing.get_sales_invoices", () => ({
	customer: props.customer,
	outstanding_only: outstandingOnly.value ? 1 : 0,
}));
const prescriptions = useServerTable("pos.list_prescriptions", () => ({
	customer: props.customer,
	include_invoiced: 1,
}));
const tests = useServerTable("lab.list_test_requests", () => ({ customer: props.customer }));

// Columns joined in on the server can't be sorted there.
const visitHeaders = computed(() => [
	{ title: __("Appointment"), key: "name" },
	{ title: __("Date"), key: "appointment_date" },
	{ title: __("Type"), key: "appointment_type" },
	{ title: __("Doctor"), key: "doctor_name", sortable: false },
	{ title: __("Service"), key: "service_name", sortable: false },
	{ title: __("Status"), key: "appointment_status" },
]);
const invoiceHeaders = computed(() => [
	{ title: __("Invoice"), key: "name" },
	{ title: __("Date"), key: "posting_date" },
	{ title: __("Total"), key: "grand_total", align: "end" },
	{ title: __("Outstanding"), key: "outstanding_amount", align: "end" },
	{ title: __("Status"), key: "status" },
]);
const prescriptionHeaders = computed(() => [
	{ title: __("Prescription"), key: "name" },
	{ title: __("Date"), key: "posting_date" },
	{ title: __("Appointment"), key: "appointment", sortable: false },
	{ title: __("Status"), key: "invoice_created" },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);
const testHeaders = computed(() => [
	{ title: __("Request"), key: "name" },
	{ title: __("Date"), key: "posting_date" },
	{ title: __("Tests"), key: "item_count", sortable: false },
	{ title: __("Status"), key: "status" },
	{ title: __("Paid"), key: "paid", sortable: false },
]);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

// The balance chip's target: the invoices that still owe money, brought into view.
function showOutstanding() {
	outstandingOnly.value = true;
	if (tab.value === "invoices") {
		invoices.reload();
	} else {
		// The table mounts with the tab and loads this page.
		invoices.page = 1;
		tab.value = "invoices";
	}
	root.value?.scrollIntoView({ behavior: "smooth", block: "start" });
}

defineExpose({ showOutstanding });
</script>
