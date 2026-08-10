<template>
	<v-dialog v-model="open" max-width="760" :fullscreen="mobile" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-calendar-plus" class="mr-2" />
				{{ __("New Appointment") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<v-form ref="form" @submit.prevent="save">
					<v-row dense>
						<v-col cols="12" md="6">
							<v-select
								v-model="model.appointment_type"
								:items="APPOINTMENT_TYPES"
								:label="__('Appointment Type')"
								prepend-inner-icon="mdi-clipboard-text-outline"
								:rules="[required]"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-text-field
								v-model="model.appointment_date"
								type="date"
								:label="__('Appointment Date')"
								prepend-inner-icon="mdi-calendar"
								:rules="[required]"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.customer"
								:items="options.customer"
								:label="__('Patient')"
								prepend-inner-icon="mdi-account-outline"
								:rules="[required]"
								@update:search="(t) => searchLink('customer', 'Customer', t)"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.employee"
								:items="options.employee"
								:label="__('Doctor')"
								prepend-inner-icon="mdi-doctor"
								:rules="[required]"
								@update:search="(t) => searchLink('employee', 'Employee', t)"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.service_type"
								:items="options.service_type"
								:label="__('Service Type')"
								prepend-inner-icon="mdi-shape-outline"
								:rules="[required]"
								@update:search="(t) => searchLink('service_type', 'Item Group', t, serviceTypeFilters)"
								@update:model-value="onServiceTypeChange"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.service"
								:items="options.service"
								:label="__('Service')"
								prepend-inner-icon="mdi-medical-bag"
								:disabled="!model.service_type"
								:rules="[required]"
								@update:search="(t) => searchLink('service', 'Item', t, { item_group: model.service_type })"
							/>
						</v-col>
						<v-col cols="12">
							<v-textarea
								v-model="model.notes"
								:label="__('Notes')"
								variant="outlined"
								rows="2"
								auto-grow
								hide-details="auto"
							/>
						</v-col>
					</v-row>
				</v-form>
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Cancel") }}</v-btn>
				<v-btn color="primary" variant="flat" :loading="saving" @click="save">
					{{ __("Create") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { call, customSearchLink, notifySuccess } from "../client.js";
import { APPOINTMENT_TYPES } from "../constants.js";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue", "created"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const form = ref(null);
const saving = ref(false);
const options = reactive({ customer: [], employee: [], service_type: [], service: [] });

// Mirror patient_appointment.js: service types are groups under the clinic's parent service group.
const serviceTypeFilters = computed(() => {
	const filters = { is_group: 1 };
	if (frappe.boot.parent_service) filters.parent_item_group = frappe.boot.parent_service;
	return filters;
});

const blank = () => ({
	appointment_type: null,
	appointment_date: frappe.datetime.get_today(),
	customer: null,
	employee: null,
	service_type: null,
	service: null,
	notes: "",
});
const model = reactive(blank());

function required(value) {
	return !!value || __("Required");
}

async function searchLink(field, doctype, txt, filters = {}) {
	const rows = await customSearchLink(doctype, txt, filters);
	options[field] = rows.map((r) => ({
		title: r.description ? `${r.value} · ${r.description}` : r.value,
		value: r.value,
	}));
}

// Service is scoped to the chosen service type, so reset it when the type changes.
function onServiceTypeChange() {
	model.service = null;
	options.service = [];
	if (model.service_type) searchLink("service", "Item", "", { item_group: model.service_type });
}

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		const name = await call("create_appointment", { ...model });
		notifySuccess(__("Appointment {0} created", [name]));
		open.value = false;
		emit("created");
	} finally {
		saving.value = false;
	}
}

// Reset and preload the link lists whenever the dialog opens.
watch(open, (isOpen) => {
	if (!isOpen) return;
	Object.assign(model, blank());
	form.value?.resetValidation();
	searchLink("customer", "Customer", "");
	searchLink("employee", "Employee", "");
	searchLink("service_type", "Item Group", "", serviceTypeFilters.value);
});
</script>
