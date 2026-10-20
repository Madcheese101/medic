<template>
	<v-dialog v-model="open" max-width="720" :fullscreen="mobile" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-account-plus-outline" class="mr-2" />
				{{ __("New Patient") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<v-form ref="form" @submit.prevent="save">
					<v-row dense>
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
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.gender"
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
								v-model="model.blood_type"
								:items="BLOOD_TYPES"
								:label="__('Blood Type')"
								prepend-inner-icon="mdi-water-outline"
								clearable
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
import { BLOOD_TYPES } from "../constants.js";

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
const genders = ref([]);
const genderLoading = ref(false);

const blank = () => ({
	customer_name: "",
	date_of_birth: "",
	phone_number: "",
	gender: null,
	blood_type: null,
});
const model = reactive(blank());

function required(value) {
	return !!value || __("Required");
}

async function searchGenders(txt) {
	genderLoading.value = true;
	const results = await customSearchLink("Gender", txt);
	genders.value = results.map((r) => r.value);
	genderLoading.value = false;
}

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		const name = await call("patients.create_patient", { ...model });
		notifySuccess(__("Patient {0} created", [name]));
		open.value = false;
		emit("created", name);
	} finally {
		saving.value = false;
	}
}

// Reset the form each time the dialog opens, and preload the gender list.
watch(open, (isOpen) => {
	if (!isOpen) return;
	Object.assign(model, blank());
	form.value?.resetValidation();
	searchGenders("");
});
</script>
