<template>
	<v-card :loading="loading" max-width="720">
		<v-card-title class="d-flex align-center">
			<v-btn
				variant="text"
				:icon="backIcon"
				:title="__('Back')"
				class="mr-2"
				@click="emit('back')"
			/>
			{{ __("Profile") }}
		</v-card-title>
		<v-divider />

		<v-card-text>
			<div class="d-flex align-center ga-4 mb-5">
				<v-avatar size="72" color="surface-variant">
					<v-img v-if="model.user_image" :src="model.user_image" :alt="model.full_name" />
					<span v-else class="text-h5">{{ initials }}</span>
				</v-avatar>
				<div>
					<div class="text-subtitle-1 font-weight-medium">{{ model.full_name }}</div>
					<div class="text-caption text-medium-emphasis mb-2">{{ model.name }}</div>
					<v-btn size="small" variant="tonal" prepend-icon="mdi-image-edit-outline" @click="pickImage">
						{{ __("Change Picture") }}
					</v-btn>
				</div>
			</div>

			<v-form ref="form">
				<v-row dense>
					<v-col cols="12" md="6">
						<v-select
							v-model="model.language"
							:items="languages"
							item-title="label"
							item-value="value"
							:label="__('Language')"
							prepend-inner-icon="mdi-translate"
							clearable
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-text-field
							v-model="password.new_password"
							type="password"
							:label="__('New Password')"
							prepend-inner-icon="mdi-lock-outline"
							autocomplete="new-password"
						/>
					</v-col>
					<v-col cols="12" md="6">
						<v-text-field
							v-model="password.confirm"
							type="password"
							:label="__('Confirm Password')"
							prepend-inner-icon="mdi-lock-check-outline"
							autocomplete="new-password"
							:rules="[matchesPassword]"
						/>
					</v-col>
				</v-row>
			</v-form>
		</v-card-text>

		<v-divider />
		<v-card-actions>
			<v-spacer />
			<v-btn color="primary" variant="flat" :loading="saving" @click="save">
				{{ __("Save") }}
			</v-btn>
		</v-card-actions>
	</v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRtl } from "vuetify";
import { call, notifySuccess } from "../client.js";

const emit = defineEmits(["back"]);

const { isRtl } = useRtl();
const backIcon = computed(() => (isRtl.value ? "mdi-arrow-right" : "mdi-arrow-left"));
const loading = ref(false);
const saving = ref(false);
const form = ref(null);
const languages = ref([]);
const model = reactive({ name: "", full_name: "", language: null, user_image: null });
const password = reactive({ new_password: "", confirm: "" });

const initials = computed(() => (model.full_name || "?").trim().charAt(0).toUpperCase());

function matchesPassword(value) {
	if (!password.new_password) return true;
	return value === password.new_password || __("Passwords do not match");
}

function pickImage() {
	new frappe.ui.FileUploader({
		allow_multiple: false,
		restrictions: { allowed_file_types: ["image/*"] },
		on_success: (file_doc) => {
			model.user_image = file_doc.file_url;
		},
	});
}

async function load() {
	loading.value = true;
	try {
		const data = await call("get_my_profile");
		Object.assign(model, {
			name: data.name,
			full_name: data.full_name,
			language: data.language,
			user_image: data.user_image,
		});
		languages.value = data.languages.map((l) => ({
			value: l.name,
			label: l.language_name || l.name,
		}));
	} finally {
		loading.value = false;
	}
}

async function save() {
	const { valid } = await form.value.validate();
	if (!valid) return;

	saving.value = true;
	try {
		await call("save_profile", {
			language: model.language,
			user_image: model.user_image,
			new_password: password.new_password || null,
		});
		password.new_password = "";
		password.confirm = "";
		notifySuccess(__("Profile saved. Reload to apply the language."));
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>
