frappe.provide("frappe.MedicPos");

import { createApp } from "vue";
import { createPinia } from "pinia";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";
import { ar, en } from "vuetify/locale";
import App from "../../../medic/page/medic_pos/app.vue";
import router from "../../../medic/page/medic_pos/router/index.js";

frappe.MedicPos.Controller = class {
	constructor({ wrapper }) {
		this.$wrapper = $(wrapper);
		this.mount();
	}

	mount() {
		const medicLight = {
			dark: false,
			colors: {
				background: "#fbf7e6",
				surface: "#fdfbf0",
				"surface-bright": "#ffffff",
				"surface-light": "#f3efdc",
				"surface-variant": "#e4dfc8",
				"on-surface-variant": "#5c5a4a",
				primary: "#2e5545",
				secondary: "#e0a83c",
				success: "#4c8a63",
				warning: "#e0a83c",
				error: "#c0553f",
				info: "#3f7a9c",
				"on-background": "#1c1c17",
				"on-surface": "#1c1c17",
				"on-primary": "#ffffff",
				"on-secondary": "#1c1c17",
			},
		};

		// Follow the language Frappe is running in; Vuetify flips to RTL for Arabic.
		const lang = (frappe.boot.lang || "en").startsWith("ar") ? "ar" : "en";

		const vuetify = createVuetify({
			components,
			directives,
			locale: {
				locale: lang,
				fallback: "en",
				messages: { ar, en },
				rtl: { ar: true, en: false },
			},
			theme: {
				defaultTheme: "medicLight",
				themes: { medicLight },
			},
			defaults: {
				VCard: { rounded: "lg", flat: true, border: true },
				VBtn: { rounded: "lg", style: "text-transform:none;letter-spacing:0;" },
				VTextField: {
					variant: "outlined",
					rounded: "pill",
					density: "comfortable",
					hideDetails: "auto",
				},
				VAutocomplete: {
					variant: "outlined",
					rounded: "pill",
					density: "comfortable",
					hideDetails: "auto",
				},
				VSelect: {
					variant: "outlined",
					rounded: "pill",
					density: "comfortable",
					hideDetails: "auto",
				},
				VList: { rounded: "lg" },
				VDataTable: { hover: true },
			},
		});

		const app = createApp(App);
		// Frappe's translation helper is a browser global; compiled templates resolve
		// identifiers against the component context, so expose it explicitly.
		app.config.globalProperties.__ = window.__;
		app.use(createPinia());
		app.use(vuetify);
		app.use(router);
		this.$component = app.mount(this.$wrapper.get(0));
	}
};
