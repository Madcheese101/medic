<template>
	<v-card>
		<v-card-title class="d-flex align-center">
			<v-btn
				variant="text"
				:icon="backIcon"
				:title="__('Back')"
				class="mr-2"
				@click="emit('cancel')"
			/>
			<v-icon icon="mdi-calendar-plus" class="mr-2" />
			<span class="text-truncate">{{ __("New Appointment") }}</span>
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
							item-props
							:rules="[required]"
							@update:search="(t) => searchLink('customer', 'Customer', t, {}, 'customer_name')"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-autocomplete
							v-model="model.employee"
							:items="options.employee"
							:label="__('Doctor')"
							prepend-inner-icon="mdi-doctor"
							item-props
							:rules="[required]"
							@update:search="(t) => searchLink('employee', 'Employee', t, {}, 'employee_name')"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-autocomplete
							v-model="model.service_type"
							:items="options.service_type"
							:label="__('Service Type')"
							prepend-inner-icon="mdi-shape-outline"
							item-props
							:rules="[required]"
							@update:search="(t) => searchLink('service_type', 'Item Group', t, serviceTypeFilters, 'name')"
							@update:model-value="onServiceTypeChange"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-autocomplete
							v-model="model.service"
							:items="options.service"
							:label="__('Service')"
							prepend-inner-icon="mdi-medical-bag"
							item-props
							:disabled="!model.service_type"
							:rules="[required]"
							@update:search="(t) => searchLink('service', 'Item', t, { item_group: model.service_type }, 'item_name')"
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
			<v-btn variant="text" @click="emit('cancel')">{{ __("Cancel") }}</v-btn>
			<v-btn color="primary" variant="flat" :loading="saving" @click="save">
				{{ __("Create") }}
			</v-btn>
		</v-card-actions>
	</v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRtl } from "vuetify";
import { call, notifySuccess, searchLinkOptions } from "../client.js";
import { APPOINTMENT_TYPES } from "../constants.js";

const emit = defineEmits(["created", "cancel"]);

const { isRtl } = useRtl();
const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));

const form = ref(null);
const saving = ref(false);
const options = reactive({ customer: [], employee: [], service_type: [], service: [] });

// Mirror patient_appointment.js: service types are groups under the clinic's parent service group.
const serviceTypeFilters = computed(() => {
	const filters = { is_group: 0 };
	if (frappe.boot.parent_service) filters.parent_item_group = frappe.boot.parent_service;
	return filters;
});

const model = reactive({
	appointment_type: null,
	appointment_date: frappe.datetime.get_today(),
	customer: null,
	employee: null,
	service_type: null,
	service: null,
	notes: "",
});

function required(value) {
	return !!value || __("Required");
}

async function searchLink(field, doctype, txt, filters = {}, labelFieldname = null) {
	options[field] = await searchLinkOptions(doctype, txt, filters, labelFieldname);
}

// Service is scoped to the chosen service type, so reset it when the type changes.
function onServiceTypeChange() {
	model.service = null;
	options.service = [];
	if (model.service_type) searchLink("service", "Item", "", { item_group: model.service_type }, "item_name");
}

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		const name = await call("create_appointment", { ...model });
		notifySuccess(__("Appointment {0} created", [name]));
		emit("created");
	} finally {
		saving.value = false;
	}
}

// Preload the link lists when the form opens.
onMounted(() => {
	searchLink("customer", "Customer", "", {}, "customer_name");
	searchLink("employee", "Employee", "", {}, "employee_name");
	searchLink("service_type", "Item Group", "", serviceTypeFilters.value, "name");
});
</script>
