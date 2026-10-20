<template>
	<v-card :loading="loading">
		<v-card-title class="d-flex align-center flex-wrap ga-2">
			<v-btn
				variant="text"
				:icon="backIcon"
				:title="__('Back')"
				@click="emit('back')"
			/>
			<span class="text-truncate">{{ model.customer_name || __("Patient") }}</span>
			<v-spacer />
			<v-btn color="primary" variant="tonal" prepend-icon="mdi-calendar-plus" @click="newAppointment">
				{{ __("New Appointment") }}
			</v-btn>
			<!-- An amount owed opens the invoices behind it. -->
			<v-chip
				v-if="balance !== null"
				:color="balanceColor"
				variant="flat"
				size="large"
				:link="balance > 0"
				:title="balance > 0 ? __('Show outstanding invoices') : undefined"
				@click="balance > 0 && records.showOutstanding()"
			>
				<v-icon start icon="mdi-wallet-outline" />
				{{ formatCurrency(balance, currency) }}
			</v-chip>
		</v-card-title>
		<v-divider />

		<v-card-text>
			<div class="text-subtitle-2 text-medium-emphasis mb-2">{{ __("Patient Details") }}</div>
			<v-form ref="form">
				<v-row>
					<v-col cols="12" md="6">
						<v-text-field
							v-model="model.customer_name"
							:label="__('Patient Name')"
							prepend-inner-icon="mdi-account-outline"
							:rules="[required]"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-text-field
							v-model="model.date_of_birth"
							type="date"
							:label="__('Date of Birth')"
							prepend-inner-icon="mdi-calendar"
							:suffix="age"
							:rules="[required]"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-text-field
							v-model="model.phone_number"
							:label="__('Mobile No')"
							prepend-inner-icon="mdi-phone-outline"
							:hint="__('e.g. 0912345678')"
							:rules="[required]"
						/>
						<PhoneDuplicateAlert :phone="model.phone_number" :exclude="props.patient" />
					</v-col>
					<v-col cols="12" md="6">
						<v-autocomplete
							v-model="model.gender"
							:items="genders"
							:label="__('Gender')"
							prepend-inner-icon="mdi-gender-male-female"
							:rules="[required]"
							@update:search="searchGenders"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-select
							v-model="model.blood_type"
							:items="BLOOD_TYPES"
							:label="__('Blood Type')"
							prepend-inner-icon="mdi-water-outline"
							clearable
						/>
					</v-col>
				</v-row>
			</v-form>

			<div class="d-flex mt-3">
				<v-spacer />
				<v-btn color="primary" variant="flat" :loading="savingPatient" @click="savePatient">
					{{ __("Save Patient") }}
				</v-btn>
			</div>

			<v-divider class="my-5" />

			<!-- Section order follows the Medical History doctype field_order. -->
			<v-textarea
				v-model="history.notes"
				:label="__('Notes')"
				variant="outlined"
				rows="3"
				auto-grow
				hide-details="auto"
				class="mb-5"
			/>

			<IllnessTable
				v-model="history.medical_history"
				:label="__('Medical History')"
				:illness-type="IllnessType.OTHER"
				class="mb-5"
			/>

			<IllnessTable
				v-model="history.skin_illness"
				:label="__('Skin Illness')"
				:illness-type="IllnessType.SKIN"
			/>

			<div class="d-flex mt-3">
				<v-spacer />
				<v-btn color="primary" variant="flat" :loading="savingHistory" @click="saveHistory">
					{{ __("Save Medical History") }}
				</v-btn>
			</div>

			<v-divider class="my-5" />

			<PatientRecords ref="records" :customer="props.patient" />
		</v-card-text>
	</v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRtl } from "vuetify";
import { call, customSearchLink, debounce, formatCurrency, notifySuccess } from "../client.js";
import { BLOOD_TYPES, IllnessType } from "../constants.js";
import { useUiStore } from "../stores/ui.js";
import IllnessTable from "../components/IllnessTable.vue";
import PatientRecords from "../components/PatientRecords.vue";
import PhoneDuplicateAlert from "../components/PhoneDuplicateAlert.vue";


const props = defineProps({ patient: { type: String, default: null } });
const emit = defineEmits(["back", "navigate"]);

const uiStore = useUiStore();
const { isRtl } = useRtl();
const form = ref(null);
const records = ref(null);
const loading = ref(false);
const savingPatient = ref(false);
const savingHistory = ref(false);
const balance = ref(null);
const currency = ref(null);
const genders = ref([]);

const model = reactive({
	customer_name: "",
	date_of_birth: "",
	phone_number: "",
	gender: null,
	blood_type: null,
});
const history = reactive({ notes: "", medical_history: [], skin_illness: [] });

const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));

// Positive balance means the patient still owes the clinic.
const balanceColor = computed(() => {
	if (!balance.value) return "surface-variant";
	return balance.value > 0 ? "error" : "success";
});

// Whole years, or months for a baby under one.
const age = computed(() => {
	if (!model.date_of_birth) return "";
	const born = frappe.datetime.str_to_obj(model.date_of_birth);
	const now = new Date();
	const months =
		(now.getFullYear() - born.getFullYear()) * 12 +
		now.getMonth() -
		born.getMonth() -
		(now.getDate() < born.getDate() ? 1 : 0);
	if (months < 0) return "";
	return months < 12 ? __("{0} months", [months]) : __("{0} years", [Math.floor(months / 12)]);
});

function required(value) {
	return !!value || __("Required");
}

const searchGenders = debounce(async (txt) => {
	const results = await customSearchLink("Gender", txt);
	genders.value = results.map((r) => r.value);
});

async function load() {
	loading.value = true;
	try {
		const data = await call("patients.get_patient", { name: props.patient });
		Object.assign(model, data.customer);
		balance.value = data.balance;
		currency.value = data.currency;

		const mh = data.medical_history;
		history.notes = mh?.notes || "";
		history.medical_history = mh?.medical_history || [];
		history.skin_illness = mh?.skin_illness || [];

		searchGenders("");
	} finally {
		loading.value = false;
	}
}

async function savePatient() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	savingPatient.value = true;
	try {
		await call("patients.save_patient", { name: props.patient, ...model });
		notifySuccess(__("Patient saved"));
	} finally {
		savingPatient.value = false;
	}
}

async function saveHistory() {
	savingHistory.value = true;
	try {
		await call("patients.save_medical_history", {
			customer: props.patient,
			notes: history.notes,
			medical_history: JSON.stringify(history.medical_history),
			skin_illness: JSON.stringify(history.skin_illness),
		});
		notifySuccess(__("Medical history saved"));
	} finally {
		savingHistory.value = false;
	}
}

// Book for this patient: the Appointments view opens its form with them already chosen.
function newAppointment() {
	uiStore.requestNewAppointment(false, { name: props.patient, customer_name: model.customer_name });
	emit("navigate", "appointments");
}

onMounted(load);
</script>
