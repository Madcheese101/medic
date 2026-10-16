<template>
	<v-dialog v-model="open" max-width="640" :fullscreen="mobile" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-clipboard-plus-outline" class="mr-2" />
				{{ __("New Treatment Plan") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<v-form ref="form" @submit.prevent="save">
					<v-row dense>
						<v-col v-if="!customer" cols="12">
							<v-autocomplete
								v-model="model.customer"
								:items="patients"
								:label="__('Patient')"
								prepend-inner-icon="mdi-account-outline"
								:rules="[required]"
								item-props
								@update:search="(t) => searchLink('patients', 'Customer', t, 'customer_name')"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.employee"
								:items="doctors"
								:label="__('Doctor')"
								prepend-inner-icon="mdi-doctor"
								:rules="[required]"
								item-props
								@update:search="(t) => searchLink('doctors', 'Employee', t, 'employee_name')"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="category"
								:items="categories"
								:label="__('Category')"
								prepend-inner-icon="mdi-shape-outline"
								clearable
								@update:model-value="onCategoryChange"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.service"
								:items="services"
								:label="__('Service')"
								prepend-inner-icon="mdi-medical-bag"
								:rules="[required]"
								item-props
								@update:search="(t) => searchLink('services', 'Item', t, 'item_name')"
							/>
						</v-col>
						<v-col cols="12" md="6">
							<v-text-field
								v-model.number="model.total_sessions"
								type="number"
								min="1"
								:label="__('Total Sessions')"
								prepend-inner-icon="mdi-counter"
								:rules="[required, positive]"
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
const doctors = ref([]);
const services = ref([]);
const patients = ref([]);
// Filters the Service picker only; not saved on the plan.
const category = ref(null);
// The parent service group's descendants; the parent itself already bounds every search.
const categories = (frappe.boot.service_item_groups || []).filter((g) => g !== frappe.boot.parent_service);

const blank = () => ({ customer: null, employee: null, service: null, total_sessions: 1, notes: "" });
const model = reactive(blank());

const required = (v) => !!v || __("Required");
const positive = (v) => v > 0 || __("Must be at least 1");

async function searchLink(target, doctype, txt, labelFieldname = null) {
	let filters = {};
	// The Doctor picker is always restricted to the clinic's doctor designation.
	if (target === "doctors" && frappe.boot.default_doctor_designation) {
		filters = { designation: frappe.boot.default_doctor_designation };
	} else if (target === "services" && category.value) {
		filters = { item_group: ["descendants of (inclusive)", category.value] };
	} else if (target === "services" && frappe.boot.service_item_groups?.length) {
		// The Service picker is always restricted to the clinic's service item groups.
		filters = { item_group: ["in", frappe.boot.service_item_groups] };
	}
	const list = await searchLinkOptions(doctype, txt, filters, labelFieldname);
	if (target === "doctors") doctors.value = list;
	else if (target === "patients") patients.value = list;
	else services.value = list;
}

function onCategoryChange() {
	model.service = null;
	searchLink("services", "Item", "");
}

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		// Prop customer (Patient view) wins; else the in-form picker (standalone view).
		const customer = props.customer || model.customer;
		const name = await call("create_treatment_plan", { ...model, customer });
		notifySuccess(__("Treatment plan {0} created", [name]));
		open.value = false;
		emit("created");
	} finally {
		saving.value = false;
	}
}

watch(open, (isOpen) => {
	if (!isOpen) return;
	Object.assign(model, blank());
	category.value = null;
	form.value?.resetValidation();
	searchLink("doctors", "Employee", "");
	searchLink("services", "Item", "");
	if (!props.customer) searchLink("patients", "Customer", "");
});
</script>
