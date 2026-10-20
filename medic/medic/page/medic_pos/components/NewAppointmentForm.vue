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

		<v-stepper v-model="step" :items="steps" hide-actions flat>
			<!-- Step 1: pick an existing patient, or create one inline. -->
			<template #item.1>
				<v-form ref="step1Form">
					<v-checkbox
						v-model="isNew"
						:label="__('Is new Patient')"
						density="comfortable"
						hide-details
						class="mb-2"
					/>
					<v-row v-if="!isNew" dense>
						<v-col cols="12">
							<v-autocomplete
								v-model="customer"
								:items="options.customer"
								:label="__('Patient')"
								prepend-inner-icon="mdi-account-outline"
								item-props
								:rules="[required]"
								@update:search="searchCustomers"
							/>
						</v-col>
					</v-row>
					<v-row v-else dense>
						<v-col cols="12" md="6">
							<v-text-field
								v-model="patient.customer_name"
								:label="__('Patient Name')"
								prepend-inner-icon="mdi-account-outline"
								:rules="[required]"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-text-field
								v-model="patient.date_of_birth"
								type="date"
								:label="__('Date of Birth')"
								prepend-inner-icon="mdi-calendar"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-text-field
								v-model="patient.phone_number"
								:label="__('Mobile No')"
								prepend-inner-icon="mdi-phone-outline"
								:hint="__('e.g. 0912345678')"
								:rules="[required]"
							/>
							<PhoneDuplicateAlert :phone="patient.phone_number" />
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="patient.gender"
								:items="genders"
								:loading="genderLoading"
								:label="__('Gender')"
								prepend-inner-icon="mdi-gender-male-female"
								:rules="[required]"
								@update:search="searchGenders"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-select
								v-model="patient.blood_type"
								:items="BLOOD_TYPES"
								:label="__('Blood Type')"
								prepend-inner-icon="mdi-water-outline"
								clearable
							/>
						</v-col>
					</v-row>
				</v-form>
			</template>

			<!-- Step 2: appointment details. -->
			<template #item.2>
				<v-form ref="step2Form">
					<v-row dense>
						<v-col cols="12" md="6">
							<v-select
								v-model="appt.appointment_type"
								:items="APPOINTMENT_TYPES"
								:label="__('Appointment Type')"
								prepend-inner-icon="mdi-clipboard-text-outline"
								:rules="[required]"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="appt.employee"
								:items="options.employee"
								:label="__('Doctor')"
								prepend-inner-icon="mdi-doctor"
								item-props
								:rules="[required]"
								@update:search="searchEmployees"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<DoctorDatePicker
								v-model="appt.appointment_date"
								:employee="appt.employee"
								:label="__('Appointment Date')"
								:rules="[required]"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="appt.service_type"
								:items="options.service_type"
								:label="__('Service Type')"
								prepend-inner-icon="mdi-shape-outline"
								item-props
								:rules="[required]"
								@update:search="searchServiceTypes"
								@update:model-value="onServiceTypeChange"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="appt.service"
								:items="options.service"
								:label="__('Service')"
								prepend-inner-icon="mdi-medical-bag"
								item-props
								:disabled="!appt.service_type"
								:rules="[required]"
								@update:search="searchServices"
							/>
						</v-col>
						<v-col v-if="showDiscount" cols="12" md="6">
							<v-text-field
								v-model.number="appt.discount_percentage"
								type="number"
								min="0"
								:max="maxDiscount"
								:label="__('Discount %')"
								prepend-inner-icon="mdi-sale-outline"
								:rules="[discountRule]"
								:hint="__('Maximum {0}%', [maxDiscount])"
								persistent-hint
							/>
						</v-col>
						<v-col cols="12">
							<v-textarea
								v-model="appt.notes"
								:label="__('Notes')"
								variant="outlined"
								rows="2"
								auto-grow
								hide-details="auto"
							/>
						</v-col>
					</v-row>
				</v-form>
			</template>
		</v-stepper>

		<v-divider />
		<v-card-actions>
			<v-btn variant="text" @click="emit('cancel')">{{ __("Cancel") }}</v-btn>
			<v-spacer />
			<v-btn v-if="step === 2" variant="text" @click="step = 1">{{ __("Back") }}</v-btn>
			<v-btn v-if="step === 1" color="primary" variant="flat" @click="nextStep">
				{{ __("Next") }}
			</v-btn>
			<v-btn v-else color="primary" variant="flat" :loading="saving" @click="save">
				{{ __("Create") }}
			</v-btn>
		</v-card-actions>
	</v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRtl } from "vuetify";
import { call, customSearchLink, debounce, notifySuccess, searchLinkOptions } from "../client.js";
import { APPOINTMENT_TYPES, AppointmentType, BLOOD_TYPES } from "../constants.js";
import DoctorDatePicker from "./DoctorDatePicker.vue";
import PhoneDuplicateAlert from "./PhoneDuplicateAlert.vue";
import { canDiscount, discountRule, maxDiscount } from "../discount.js";

const props = defineProps({
	initialNew: { type: Boolean, default: false },
	// { name, customer_name } of an existing patient to book for (from the patient file).
	initialCustomer: { type: Object, default: null },
});
const emit = defineEmits(["created", "cancel"]);

const { isRtl } = useRtl();
const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));

const steps = [__("Patient"), __("Appointment")];
// Booking for a known patient skips straight to the appointment details.
const step = ref(props.initialCustomer ? 2 : 1);
const step1Form = ref(null);
const step2Form = ref(null);
const saving = ref(false);

// Step 1 state: either an existing customer, or a new patient to create.
const isNew = ref(props.initialNew && !props.initialCustomer);
const customer = ref(props.initialCustomer?.name || null);
const patient = reactive({
	customer_name: "",
	date_of_birth: "",
	phone_number: "",
	gender: null,
	blood_type: null,
});
const genders = ref([]);
const genderLoading = ref(false);

// Step 2 state: the appointment itself.
const appt = reactive({
	appointment_type: null,
	appointment_date: frappe.datetime.get_today(),
	employee: null,
	service_type: null,
	service: null,
	notes: "",
	discount_percentage: null,
});
// Consultations, reviews and follow-ups are never discounted.
const showDiscount = computed(() => canDiscount() && appt.appointment_type === AppointmentType.TREATMENT);

const options = reactive({
	customer: props.initialCustomer
		? [{ title: props.initialCustomer.customer_name, value: props.initialCustomer.name }]
		: [],
	employee: [],
	service_type: [],
	service: [],
});

// Mirror patient_appointment.js: service types are groups under the clinic's parent service group.
const serviceTypeFilters = computed(() => {
	const filters = { is_group: 0 };
	if (frappe.boot.parent_service) filters.parent_item_group = frappe.boot.parent_service;
	return filters;
});

// The Doctor picker is always restricted to employees with the clinic's doctor designation.
const doctorFilters = frappe.boot.default_doctor_designation
	? { designation: frappe.boot.default_doctor_designation }
	: {};

function required(value) {
	return !!value || __("Required");
}

async function searchLink(field, doctype, txt, filters = {}, labelFieldname = null) {
	options[field] = await searchLinkOptions(doctype, txt, filters, labelFieldname);
}

// One debounce per field, so typing in one field never cancels another field's search.
const searchCustomers = debounce((t) => searchLink("customer", "Customer", t, {}, "customer_name"));
const searchEmployees = debounce((t) =>
	searchLink("employee", "Employee", t, doctorFilters, "employee_name")
);
const searchServiceTypes = debounce((t) =>
	searchLink("service_type", "Item Group", t, serviceTypeFilters.value, "name")
);
const searchServices = debounce((t) =>
	searchLink("service", "Item", t, { item_group: appt.service_type }, "item_name")
);

const searchGenders = debounce(async (txt) => {
	genderLoading.value = true;
	const results = await customSearchLink("Gender", txt);
	genders.value = results.map((r) => r.value);
	genderLoading.value = false;
});

// Service is scoped to the chosen service type, so reset it when the type changes.
function onServiceTypeChange() {
	appt.service = null;
	options.service = [];
	if (appt.service_type) searchLink("service", "Item", "", { item_group: appt.service_type }, "item_name");
}

async function nextStep() {
	const { valid } = await step1Form.value.validate();
	if (valid) step.value = 2;
}

async function save() {
	const { valid } = await step2Form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		// A brand-new patient is created first; its Customer id becomes the appointment's customer.
		let customerId = customer.value;
		if (isNew.value) {
			customerId = await call("patients.create_patient", { ...patient });
			notifySuccess(__("Patient {0} created", [customerId]));
		}
		const name = await call("appointments.create_appointment", {
			...appt,
			customer: customerId,
			discount_percentage: showDiscount.value ? appt.discount_percentage : null,
		});
		notifySuccess(__("Appointment {0} created", [name]));
		emit("created");
	} finally {
		saving.value = false;
	}
}

// Preload the link lists when the form opens; a preset patient keeps their own entry instead.
onMounted(() => {
	if (!props.initialCustomer) searchLink("customer", "Customer", "", {}, "customer_name");
	searchLink("employee", "Employee", "", doctorFilters, "employee_name");
	searchLink("service_type", "Item Group", "", serviceTypeFilters.value, "name");
	searchGenders("");
});
</script>
