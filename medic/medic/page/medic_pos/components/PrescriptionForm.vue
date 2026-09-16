<template>
	<v-card :loading="loading">
		<v-card-title class="d-flex align-center">
			<v-btn
				variant="text"
				:icon="backIcon"
				:title="__('Back')"
				class="mr-2"
				@click="emit('cancel')"
			/>
			<v-icon icon="mdi-prescription" class="mr-2" />
			<span class="text-truncate">{{ isNew ? __("New Prescription") : prescription }}</span>
			<v-btn
				v-if="!isNew"
				variant="text"
				icon="mdi-printer"
				:title="__('Print')"
				class="ml-1"
				@click="printDoc('Prescription', prescription)"
			/>
			<v-spacer />
			<v-chip v-if="invoiceCreated" color="primary" variant="flat" size="large">
				{{ __("Invoiced") }}
			</v-chip>
		</v-card-title>
		<v-divider />

		<v-card-text>
			<v-row dense>
				<v-col cols="12" md="4">
					<v-text-field :model-value="patient" :label="__('Patient')" prepend-inner-icon="mdi-account-outline" readonly />
				</v-col>
				<v-col cols="12" md="4">
					<v-text-field :model-value="appointment" :label="__('Appointment')" prepend-inner-icon="mdi-calendar-check-outline" readonly />
				</v-col>
				<v-col cols="12" md="4">
					<v-text-field :model-value="formatDate(postingDate)" :label="__('Posting Date')" prepend-inner-icon="mdi-calendar" readonly />
				</v-col>
			</v-row>

			<v-divider class="my-5" />
			<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Items") }}</div>

			<v-form v-if="editable" ref="itemForm">
				<v-row dense align="center">
					<v-col cols="12" sm="6" lg="3">
						<v-autocomplete
							v-model="entry.item"
							:items="options.item"
							:label="__('Item')"
							prepend-inner-icon="mdi-pill"
							item-props
							:rules="[required]"
							@update:search="searchItems"
							@update:model-value="onItemChange"
						/>
					</v-col>
					<v-col cols="12" sm="6" lg="3">
						<v-select
							v-model="entry.route"
							:items="PRESCRIPTION_ROUTES"
							:label="__('Route')"
							prepend-inner-icon="mdi-needle"
							clearable
						/>
					</v-col>
					<v-col cols="4" sm="4" lg="2">
						<v-text-field
							v-model="entry.times"
							type="number"
							min="1"
							:label="__('Times')"
							:rules="[schedulePositive]"
						/>
					</v-col>
					<v-col cols="4" sm="4" lg="2">
						<v-select v-model="entry.per" :items="PRESCRIPTION_PER" :label="__('Per')" :rules="[scheduleRequired]" />
					</v-col>
					<v-col cols="4" sm="4" lg="1">
						<v-text-field
							v-model="entry.for"
							type="number"
							min="1"
							:label="__('For')"
							:rules="[schedulePositive]"
						/>
					</v-col>
					<v-col cols="12" sm="12" lg="1" class="d-flex align-center">
						<v-btn
							v-if="lgAndUp"
							color="primary"
							variant="tonal"
							icon="mdi-plus"
							:title="__('Add')"
							@click="addRow"
						/>
						<v-btn v-else color="primary" variant="tonal" prepend-icon="mdi-plus" block @click="addRow">
							{{ __("Add") }}
						</v-btn>
					</v-col>
				</v-row>
			</v-form>

			<v-table density="comfortable" class="mt-3">
				<thead>
					<tr>
						<th>{{ __("Item") }}</th>
						<th>{{ __("Route") }}</th>
						<th>{{ __("Times") }}</th>
						<th>{{ __("Per") }}</th>
						<th>{{ __("For") }}</th>
						<th style="width: 56px" />
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, index) in rows" :key="index">
						<td>{{ row.item }}</td>
						<td>{{ row.route }}</td>
						<td>{{ row.times }}</td>
						<td>{{ row.per }}</td>
						<td>{{ row.for }}</td>
						<td>
							<v-btn
								v-if="editable"
								size="small"
								variant="text"
								color="error"
								icon="mdi-delete-outline"
								:title="__('Remove')"
								@click="rows.splice(index, 1)"
							/>
						</td>
					</tr>
					<tr v-if="!rows.length">
						<td colspan="6" class="text-medium-emphasis">{{ __("No rows") }}</td>
					</tr>
				</tbody>
			</v-table>
		</v-card-text>
		<v-divider />

		<v-card-actions>
			<v-btn variant="text" @click="emit('cancel')">{{ editable ? __("Cancel") : __("Back") }}</v-btn>
			<v-spacer />
			<v-btn
				v-if="editable"
				color="primary"
				variant="flat"
				:disabled="!rows.length"
				:loading="saving"
				@click="save"
			>
				{{ isNew ? __("Create") : __("Save") }}
			</v-btn>
		</v-card-actions>
	</v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useDisplay, useRtl } from "vuetify";
import { call, notifySuccess, printDoc, searchLinkOptions } from "../client.js";
import { PRESCRIPTION_PER, PRESCRIPTION_ROUTES } from "../constants.js";

const props = defineProps({
	appointment: { type: String, default: null },
	patient: { type: String, default: null },
	prescription: { type: String, default: null },
});
const emit = defineEmits(["saved", "cancel"]);

const { isRtl } = useRtl();
const { lgAndUp } = useDisplay();
const itemForm = ref(null);
const loading = ref(false);
const saving = ref(false);
const invoiceCreated = ref(false);
const postingDate = ref(frappe.datetime.get_today());
const rows = ref([]);
const options = reactive({ item: [] });
const entry = reactive({ item: null, route: null, times: null, per: null, for: null });
// True when the selected item is a Pharma item that requires a dosing schedule,
// which makes Times/Per/For mandatory for that row.
const requiresSchedule = ref(false);

const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));
const isNew = computed(() => !props.prescription);
// Once the pharmacy has invoiced it, the prescription is a read-only record.
const editable = computed(() => isNew.value || !invoiceCreated.value);

const required = (value) => !!value || __("Required");
// Times/Per/For are only required for schedule-bound Pharma items.
const scheduleRequired = (value) => !requiresSchedule.value || !!value || __("Required");
const schedulePositive = (value) => !requiresSchedule.value || Number(value) > 0 || __("Required");

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

// Prescribed items come from the pharmacy group when the clinic has one configured.
async function searchItems(txt) {
	const filters = frappe.boot.pharmacy_item_group ? { item_group: frappe.boot.pharmacy_item_group } : {};
	options.item = await searchLinkOptions("Item", txt, filters, "item_name");
}

// Look up the chosen item's type/schedule flag to drive Times/Per/For validation.
async function onItemChange(item) {
	if (!item) {
		requiresSchedule.value = false;
		return;
	}
	const { message } = await frappe.db.get_value("Item", item, ["item_type", "requires_schedule"]);
	requiresSchedule.value = message?.item_type === "Pharma" && !!message?.requires_schedule;
}

async function addRow() {
	const { valid } = await itemForm.value.validate();
	if (!valid) return;

	rows.value.push({ ...entry });
	Object.assign(entry, { item: null, route: null, times: null, per: null, for: null });
	requiresSchedule.value = false;
	itemForm.value.resetValidation();
}

async function save() {
	saving.value = true;
	try {
		if (isNew.value) {
			const name = await call("create_prescription", {
				appointment: props.appointment,
				items: rows.value,
			});
			notifySuccess(__("Prescription {0} created", [name]));
		} else {
			await call("update_prescription", { name: props.prescription, items: rows.value });
			notifySuccess(__("Prescription saved"));
		}
		emit("saved");
	} finally {
		saving.value = false;
	}
}

onMounted(async () => {
	searchItems("");
	if (isNew.value) return;

	loading.value = true;
	try {
		const doc = await call("get_prescription", { name: props.prescription });
		rows.value = doc.items || [];
		postingDate.value = doc.posting_date;
		invoiceCreated.value = !!doc.invoice_created;
	} finally {
		loading.value = false;
	}
});
</script>
