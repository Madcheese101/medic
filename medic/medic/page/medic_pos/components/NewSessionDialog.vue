<template>
	<v-dialog v-model="open" max-width="560" :fullscreen="mobile" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-calendar-account" class="mr-2" />
				{{ __("New Session") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<v-autocomplete
					v-model="customer"
					:items="customers"
					:label="__('Patient')"
					prepend-inner-icon="mdi-account-outline"
					item-props
					@update:search="searchCustomers"
					@update:model-value="loadPlans"
				/>

				<v-select
					v-model="plan"
					:items="planItems"
					:label="__('Treatment Plan')"
					prepend-inner-icon="mdi-clipboard-pulse-outline"
					:loading="loadingPlans"
					:no-data-text="__('No active plan for this patient')"
					class="mt-3"
				/>

				<DoctorDatePicker
					v-model="sessionDate"
					:employee="selectedPlanEmployee"
					:label="__('Session Date')"
					:disabled="!plan"
					class="mt-3"
				/>
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Cancel") }}</v-btn>
				<v-btn
					color="primary"
					variant="flat"
					:loading="saving"
					:disabled="!plan || !sessionDate"
					@click="save"
				>
					{{ __("Create") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { call, notifySuccess, searchLinkOptions } from "../client.js";
import DoctorDatePicker from "./DoctorDatePicker.vue";

const props = defineProps({ modelValue: { type: Boolean, default: false } });
const emit = defineEmits(["update:modelValue", "created"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const saving = ref(false);
const customers = ref([]);
const customer = ref(null);
const planItems = ref([]);
const plan = ref(null);
const sessionDate = ref(null);
const loadingPlans = ref(false);

const selectedPlanEmployee = computed(
	() => planItems.value.find((p) => p.value === plan.value)?.employee || null,
);

async function searchCustomers(txt) {
	customers.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
}

async function loadPlans() {
	plan.value = null;
	planItems.value = [];
	sessionDate.value = null;
	if (!customer.value) return;
	loadingPlans.value = true;
	try {
		const plans = await call("treatments.get_active_treatment_plans", { customer: customer.value });
		planItems.value = plans.map((p) => ({
			title: `${p.name} · ${p.service_name || p.service} (${p.completed_sessions || 0}/${p.total_sessions})`,
			value: p.name,
			employee: p.employee,
		}));
		if (planItems.value.length === 1) plan.value = planItems.value[0].value; // auto-select
	} finally {
		loadingPlans.value = false;
	}
}

async function save() {
	saving.value = true;
	try {
		const name = await call("treatments.create_session", {
			treatment_plan: plan.value,
			appointment_date: sessionDate.value,
		});
		notifySuccess(__("Session {0} created", [name]));
		open.value = false;
		emit("created");
	} finally {
		saving.value = false;
	}
}

watch(open, (isOpen) => {
	if (!isOpen) return;
	customer.value = null;
	plan.value = null;
	planItems.value = [];
	sessionDate.value = null;
	searchCustomers("");
});
</script>
