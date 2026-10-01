<template>
	<v-dialog v-model="open" max-width="640" :fullscreen="mobile" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-test-tube" class="mr-2" />
				{{ __("New Test Request") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<v-form ref="form" @submit.prevent="save">
					<v-row dense>
						<v-col v-if="!customer" cols="12">
							<v-autocomplete
								v-model="model.patient"
								:items="patients"
								:label="__('Patient')"
								prepend-inner-icon="mdi-account-outline"
								:rules="[required]"
								item-props
								@update:search="searchPatients"
							/>
						</v-col>
						<v-col cols="12">
							<v-autocomplete
								v-model="model.items"
								:items="tests"
								:label="__('Tests')"
								prepend-inner-icon="mdi-flask-outline"
								:rules="[nonEmpty]"
								multiple
								chips
								closable-chips
								item-props
								@update:search="searchTests"
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
import { call, notifySuccess, searchLinkOptions } from "../client.js";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	customer: { type: String, default: null },
});
const emit = defineEmits(["update:modelValue", "created"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const form = ref(null);
const saving = ref(false);
const patients = ref([]);
const tests = ref([]);

const blank = () => ({ patient: null, items: [] });
const model = reactive(blank());

const required = (v) => !!v || __("Required");
const nonEmpty = (v) => (Array.isArray(v) && v.length > 0) || __("Add at least one test");

async function searchPatients(txt) {
	patients.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
}

async function searchTests(txt) {
	tests.value = await searchLinkOptions("Item", txt, { item_type: "Lab Test" }, "item_name");
}

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		const patient = props.customer || model.patient;
		const name = await call("create_test_request", { patient, items: model.items });
		notifySuccess(__("Test request {0} created", [name]));
		open.value = false;
		emit("created", name);
	} finally {
		saving.value = false;
	}
}

watch(open, (isOpen) => {
	if (!isOpen) return;
	Object.assign(model, blank());
	form.value?.resetValidation();
	searchTests("");
	if (!props.customer) searchPatients("");
});
</script>
