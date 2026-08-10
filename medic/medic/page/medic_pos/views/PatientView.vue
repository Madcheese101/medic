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
			<span class="text-truncate">{{ model.customer_name || __("Patient") }}</span>
			<v-spacer />
			<v-chip v-if="balance !== null" :color="balanceColor" variant="flat" size="large">
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
							:rules="[required]"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-text-field
							v-model="model.custom_phone_number"
							:label="__('Mobile No')"
							prepend-inner-icon="mdi-phone-outline"
							:hint="__('Include the country code, e.g. +218…')"
							:rules="[required]"
						/>
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
				:illness-type="GENERAL_ILLNESS"
				class="mb-5"
			/>

			<IllnessTable
				v-model="history.skin_illness"
				:label="__('Skin Illness')"
				:illness-type="SKIN_ILLNESS"
			/>

			<div class="d-flex mt-3">
				<v-spacer />
				<v-btn color="primary" variant="flat" :loading="savingHistory" @click="saveHistory">
					{{ __("Save Medical History") }}
				</v-btn>
			</div>

			<v-divider class="my-5" />

			<PatientTreatments :customer="props.patient" />
		</v-card-text>
	</v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRtl } from "vuetify";
import { call, customSearchLink, formatCurrency, notifySuccess } from "../client.js";
import { BLOOD_TYPES } from "../constants.js";
import IllnessTable from "../components/IllnessTable.vue";
import PatientTreatments from "../components/PatientTreatments.vue";

// Illness.illness_type options, as defined on the Illness doctype.
const GENERAL_ILLNESS = "أخرى";
const SKIN_ILLNESS = "جلدي";

const props = defineProps({ patient: { type: String, default: null } });
const emit = defineEmits(["back"]);

const { isRtl } = useRtl();
const form = ref(null);
const loading = ref(false);
const savingPatient = ref(false);
const savingHistory = ref(false);
const balance = ref(null);
const currency = ref(null);
const genders = ref([]);

const model = reactive({
	customer_name: "",
	date_of_birth: "",
	custom_phone_number: "",
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

function required(value) {
	return !!value || __("Required");
}

async function searchGenders(txt) {
	const results = await customSearchLink("Gender", txt);
	genders.value = results.map((r) => r.value);
}

async function load() {
	loading.value = true;
	try {
		const data = await call("get_patient", { name: props.patient });
		Object.assign(model, data.customer);
		balance.value = data.balance;
		currency.value = data.currency;

		const mh = data.medical_history;
		history.notes = mh?.notes || "";
		history.medical_history = mh?.medical_history || [];
		history.skin_illness = mh?.skin_illness || [];

		await searchGenders("");
	} finally {
		loading.value = false;
	}
}

async function savePatient() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	savingPatient.value = true;
	try {
		await call("save_patient", { name: props.patient, ...model });
		notifySuccess(__("Patient saved"));
	} finally {
		savingPatient.value = false;
	}
}

async function saveHistory() {
	savingHistory.value = true;
	try {
		await call("save_medical_history", {
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

onMounted(load);
</script>
