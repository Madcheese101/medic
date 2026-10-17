<template>
	<v-dialog v-model="open" max-width="560" :fullscreen="mobile" :retain-focus="false">
		<v-card>
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-medical-bag" class="mr-2" />
				{{ __("New Action") }}<span v-if="actionType" class="ml-1">— {{ actionType }}</span>
			</v-card-title>
			<v-divider />
			<v-card-text>
				<v-form ref="form">
					<v-row dense>
						<v-col cols="12" md="6">
							<v-autocomplete
								v-model="model.service_type"
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
								v-model="model.service"
								:items="options.service"
								:label="__('Service')"
								prepend-inner-icon="mdi-medical-bag"
								item-props
								:disabled="!model.service_type"
								:rules="[required]"
								@update:search="(t) => searchServices(t)"
							/>
						</v-col>
						<v-col v-if="showDiscount" cols="12" md="6">
							<v-text-field
								v-model.number="model.discount_percentage"
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
import { canDiscount, discountRule, maxDiscount } from "../discount.js";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	appointment: { type: String, default: null },
	serviceType: { type: String, default: null },
	actionType: { type: String, default: null },
});
const emit = defineEmits(["update:modelValue", "created"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const form = ref(null);
const saving = ref(false);
const options = reactive({ service_type: [], service: [] });
const model = reactive({ service_type: null, service: null, discount_percentage: null });
const showDiscount = computed(() => canDiscount() && props.actionType === "علاج");

const required = (value) => !!value || __("Required");

// Clinic service groups (children of the parent service group), excluding the appointment's own.
const serviceTypeFilters = computed(() => {
	const filters = { is_group: 0 };
	if (frappe.boot.parent_service) filters.parent_item_group = frappe.boot.parent_service;
	return filters;
});

async function searchServiceTypes(txt) {
	const rows = await searchLinkOptions("Item Group", txt, serviceTypeFilters.value, "name");
	// The action must be a different type than the appointment's service.
	options.service_type = rows.filter((r) => r.value !== props.serviceType);
}

async function searchServices(txt) {
	options.service = await searchLinkOptions("Item", txt, { item_group: model.service_type }, "item_name");
}

// Service is scoped to the chosen service type, so reset it when the type changes.
function onServiceTypeChange() {
	model.service = null;
	options.service = [];
	if (model.service_type) searchServices("");
}

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		await call("create_appointment_action", {
			name: props.appointment,
			service: model.service,
			action_type: props.actionType,
			discount_percentage: showDiscount.value ? model.discount_percentage : null,
		});
		notifySuccess(__("Action created"));
		open.value = false;
		emit("created");
	} finally {
		saving.value = false;
	}
}

// Reset and preload the type list each time the dialog opens.
watch(open, (isOpen) => {
	if (!isOpen) return;
	model.service_type = null;
	model.service = null;
	model.discount_percentage = null;
	options.service = [];
	form.value?.resetValidation();
	searchServiceTypes("");
});
</script>
