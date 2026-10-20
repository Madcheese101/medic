<template>
	<v-card>
		<v-card-text class="d-flex flex-wrap align-center ga-3">
			<v-text-field
				v-model="filters.customer_name"
				:label="__('Patient Name')"
				prepend-inner-icon="mdi-account-outline"
				clearable
				style="max-width: 220px"
				@keyup.enter="table.reload"
			/>
			<v-text-field
				v-model="filters.mobile"
				:label="__('Mobile Number')"
				prepend-inner-icon="mdi-phone-outline"
				clearable
				style="max-width: 200px"
				@keyup.enter="table.reload"
			/>
			<v-text-field
				v-model="filters.file_no"
				:label="__('File No')"
				prepend-inner-icon="mdi-file-document-outline"
				clearable
				style="max-width: 180px"
				@keyup.enter="table.reload"
			/>
			<v-btn color="primary" variant="tonal" icon="mdi-filter-outline" :title="__('Apply filters')" @click="table.reload" />
			<v-spacer />
			<v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="newOpen = true">
				{{ __("New Patient") }}
			</v-btn>
		</v-card-text>

		<v-data-table-server
			v-model:page="table.page"
			:headers="headers"
			:items="table.rows"
			:items-length="table.total"
			:loading="table.loading"
			density="comfortable"
			:no-data-text="__('No patients found')"
			@update:options="table.onOptions"
		>
			<template #item.date_of_birth="{ item }">
				{{ formatDate(item.date_of_birth) }}
			</template>
			<template #item.blood_type="{ item }">
				<v-chip v-if="item.blood_type" size="small" variant="tonal" color="error">
					{{ item.blood_type }}
				</v-chip>
				<span v-else class="text-medium-emphasis">&mdash;</span>
			</template>
			<template #item.actions="{ item }">
				<v-btn
					size="small"
					variant="tonal"
					color="primary"
					icon="mdi-eye"
					:title="__('View')"
					@click="view(item.name)"
				/>
			</template>
		</v-data-table-server>
	</v-card>

	<NewPatientDialog v-model="newOpen" @created="table.load" />
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { useServerTable } from "../serverTable.js";
import NewPatientDialog from "../components/NewPatientDialog.vue";

const emit = defineEmits(["navigate"]);

const newOpen = ref(false);
const filters = reactive({ customer_name: "", mobile: "", file_no: "" });
const table = useServerTable("patients.get_patients", () => filters);

const headers = computed(() => [
	{ title: __("File No"), key: "name" },
	{ title: __("Patient Name"), key: "customer_name" },
	{ title: __("Date of Birth"), key: "date_of_birth" },
	{ title: __("Mobile No"), key: "phone_number" },
	{ title: __("Gender"), key: "gender" },
	{ title: __("Blood Type"), key: "blood_type" },
	{ title: "", key: "actions", sortable: false, align: "end" },
]);

function formatDate(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

function view(name) {
	emit("navigate", "patient", { patient: name });
}
</script>
