<template>
	<v-dialog v-model="open" max-width="520" :fullscreen="mobile" :retain-focus="false">
		<v-card :loading="loading">
			<v-card-title class="d-flex align-center">
				<v-icon icon="mdi-receipt-text-plus-outline" class="mr-2" />
				{{ __("Create Invoice") }}
			</v-card-title>
			<v-divider />
			<v-card-text>
				<p class="text-medium-emphasis text-body-2 mb-2">
					{{ __("Choose the tests to invoice.") }}
				</p>
				<v-list density="comfortable" class="py-0">
					<v-list-item v-for="row in rows" :key="row.item" class="px-0">
						<template #prepend>
							<v-checkbox v-model="row.checked" hide-details density="compact" />
						</template>
						<v-list-item-title>{{ row.item_name || row.item }}</v-list-item-title>
						<v-list-item-subtitle v-if="row.item_name">{{ row.item }}</v-list-item-subtitle>
					</v-list-item>
					<v-list-item v-if="!rows.length && !loading" class="text-medium-emphasis px-0">
						{{ __("No tests on this request") }}
					</v-list-item>
				</v-list>
			</v-card-text>
			<v-divider />
			<v-card-actions>
				<v-spacer />
				<v-btn variant="text" @click="open = false">{{ __("Cancel") }}</v-btn>
				<v-btn color="primary" variant="flat" :disabled="!selected.length" :loading="saving" @click="create">
					{{ __("Create Draft Invoice") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { call, notifySuccess } from "../client.js";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	name: { type: String, default: null },
});
const emit = defineEmits(["update:modelValue", "created"]);

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const { mobile } = useDisplay();
const loading = ref(false);
const saving = ref(false);
const rows = ref([]);

const selected = computed(() => rows.value.filter((r) => r.checked).map((r) => r.item));

async function loadItems() {
	loading.value = true;
	try {
		const data = await call("lab.get_test_request", { name: props.name });
		// All items checked by default; the user unchecks any to exclude them.
		rows.value = (data.items || []).map((it) => ({ item: it.item, item_name: it.item_name, checked: true }));
	} finally {
		loading.value = false;
	}
}

async function create() {
	saving.value = true;
	try {
		const invoice = await call("lab.create_test_request_invoice", { name: props.name, items: selected.value });
		notifySuccess(__("Draft invoice {0} created", [invoice]));
		open.value = false;
		emit("created", invoice);
	} finally {
		saving.value = false;
	}
}

watch(open, (isOpen) => {
	if (isOpen) loadItems();
});
</script>
