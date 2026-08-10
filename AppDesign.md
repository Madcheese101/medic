# Design System — Vuetify + Frappe Desk Page

A reusable look-and-feel for a **Vue 3 + Vuetify 3 + Pinia** app mounted inside a **Frappe** desk page. Framework-specific, purpose-agnostic — swap the theme and the naming tokens below to fit any app.

### Naming tokens

Every app-specific identifier in this doc is written as a placeholder. Pick values once, use them consistently:

| Token | Meaning | Example |
| --- | --- | --- |
| `<app>` | Frappe app slug (asset path) | `medic` |
| `<page>` | Desk page name / bootstrap file | `medic_pos` |
| `<AppName>` | Human app title | `Medic` |
| `<scope>` | Root CSS scope class | `my-app` |
| `<theme>` | Vuetify theme name | `brandLight` |
| `<font>` | Font family + fontsource pkg | `IBM Plex Sans Arabic` |

All code samples below use these placeholders. Substitute your own values throughout.

---

## 1. Stack & Assets

| Concern | Choice |
| --- | --- |
| UI framework | Vue 3 (`<script setup>`, Composition API) |
| Component library | Vuetify 3 (Material Design 3) |
| Icons | Material Design Icons (`@mdi/font`, `mdi-*`) |
| State | Pinia (setup/composition stores) |
| Font | `<font>` (`@fontsource/...`) |
| Host | Frappe desk page (`frappe.ui.make_app_page`) |

CSS/font assets are injected into `<head>` at page load rather than bundled, so Vuetify and MDI ship as plain stylesheet links:

```js
// <page>.js — page bootstrap
$("head").append("<link href='/assets/<app>/node_modules/vuetify/dist/vuetify.min.css' rel='stylesheet'>");
$("head").append("<link href='/assets/<app>/node_modules/@mdi/font/css/materialdesignicons.min.css' rel='stylesheet'>");
["400","500","600","700"].forEach(w =>
  $("head").append(`<link href='/assets/<app>/node_modules/@fontsource/<font-pkg>/${w}.css' rel='stylesheet'>`)
);
```

Load only the font weights you use (400/500/600/700 = body, medium, semibold, bold).



## 3. Component Defaults (set once, applied everywhere)

Rather than repeating props on every component, global **defaults** are set in `createVuetify`. This gives the app a consistent shape: rounded bordered cards, pill inputs, no ALL-CAPS buttons.

```js
createVuetify({
  components, directives,
  theme: { defaultTheme: "<theme>", themes: { <theme> } },
  defaults: {
    VCard:         { rounded: "lg", flat: true, border: true },
    VBtn:          { rounded: "lg", style: "text-transform:none;letter-spacing:0;" },
    VTextField:    { variant: "outlined", rounded: "pill", density: "comfortable", hideDetails: "auto" },
    VAutocomplete: { variant: "outlined", rounded: "pill", density: "comfortable", hideDetails: "auto" },
    VSelect:       { variant: "outlined", rounded: "pill", density: "comfortable", hideDetails: "auto" },
    VList:         { rounded: "lg" },
    VDataTable:    { hover: true },
  },
});
```

Design rules encoded here:

- **Cards** — large radius, flat (no shadow), subtle border. Elevation comes from borders, not shadows → flat "paper" feel.
- **Buttons** — rounded, sentence case (`text-transform:none`), no letter-spacing. Never SHOUTY.
- **Inputs** (text/autocomplete/select) — outlined, **pill-shaped**, comfortable density, `hideDetails: "auto"` so they don't reserve empty space for helper text.
- **Tables** — hover highlighting on by default.

---


### Responsive strategy

`useDisplay()`'s `mobile` flag drives everything:

```js
const { mobile } = useDisplay();
// drawer collapses on mobile
watch(mobile, (m) => (drawer.value = !m), { immediate: true });
```

- Buttons render **icon-only** on mobile, **icon + label** on desktop (`v-if="mobile"` / `v-else` pairs).
- Selecting a nav item auto-closes the drawer on mobile.
- Spacing uses responsive utilities: `pa-3 pa-sm-6`, `mr-2 mr-sm-4`.
- Labels hidden on small screens with `d-none d-sm-inline`.

---

## 5. View Pattern (repeatable page template)

Every list view follows the same structure — a filter card on top of a data table, both inside one bordered card:

```vue
<v-card>
  <v-card-text class="d-flex flex-wrap align-center ga-3">
    <!-- filters: v-text-field / v-autocomplete with style="max-width: …px" -->
    <v-btn color="primary" variant="tonal" icon="mdi-filter-outline" @click="load" />
    <v-spacer />
    <v-btn color="primary" variant="flat" prepend-icon="mdi-plus">New …</v-btn>
  </v-card-text>

  <v-data-table :headers="headers" :items="rows" :loading="loading" density="comfortable">
    <template #item.status="{ item }">
      <v-chip size="small" variant="tonal" :color="statusColor(item.status)">{{ item.status }}</v-chip>
    </template>
    <template #item.amount="{ item }">{{ money(item.amount) }}</template>
    <template #item.actions="{ item }">
      <v-btn size="small" variant="tonal" prepend-icon="mdi-eye" @click="view(item.name)">View</v-btn>
    </template>
  </v-data-table>
</v-card>
```

Conventions:

- Filters are **width-capped inline** (`style="max-width: 200px"`) rather than in a grid.
- Numeric columns use `align: "end"` in the header definition; non-data columns (`actions`, icon flags) set `sortable: false` and an empty `title`.
- **Numbers always go through a formatter** (e.g. `formatCurrency` → Frappe's global `format_currency`); tables get `font-variant-numeric: tabular-nums` so digits line up.
- Status → `<v-chip variant="tonal" :color="statusColor(...)">`.

### Button variant vocabulary

| Variant | Meaning |
| --- | --- |
| `variant="flat"` | Primary action (e.g. "New …", submit) |
| `variant="tonal"` | Secondary / toolbar / row actions, status chips |
| `icon="mdi-…"` | Compact icon-only (mobile actions, filter apply) |

---

## 6. Dialog Pattern

Dialogs are consistent and mobile-aware:

```vue
<v-dialog v-model="dialog" max-width="720" :fullscreen="mobile" :retain-focus="false">
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon :icon="config.icon" class="mr-2" /> {{ config.title }}
    </v-card-title>
    <v-divider />
    <v-card-text>
      <v-row dense> <v-col cols="12" md="6"> … </v-col> </v-row>
    </v-card-text>
  </v-card>
</v-dialog>
```

- **Fullscreen on mobile**, capped width on desktop (`max-width="720"`).
- Title = leading icon + text, followed by a `<v-divider>`.
- Form bodies use `<v-row dense>` + responsive `<v-col cols="12" md="6">`.
- Every input has a `prepend-inner-icon` (`mdi-calendar`, `mdi-account-outline`, …) — icons as visual anchors.

---

## 7. Feedback / Notifications

Defer to Frappe's native toasts and dialogs instead of building custom ones, keeping it consistent with the surrounding desk:

```js
notifyError(err)   → frappe.msgprint({ title: __("Error"), indicator: "red", message });
notifySuccess(msg) → frappe.show_alert({ message, indicator: "green" });
confirmAction(msg) → frappe.confirm(...) wrapped in a Promise;
```

---

## 8. Scoped CSS & Frappe Integration Gotchas

Because this Vue app lives inside a Frappe desk page, a few overrides are needed. **All are scoped** to `<scope>` so they don't leak into the rest of the desk:

```css
/* Font on the app shell AND teleported overlays (dialogs render outside .<scope>) */
.<scope>.v-application,
.v-overlay-container { font-family: "<font>", "Segoe UI", sans-serif; }

/* Aligned monospaced digits in tables */
.<scope> .v-table, .<scope> .v-data-table { font-variant-numeric: tabular-nums; }

/* Lift Frappe's native Bootstrap modals above Vuetify overlays.
   Scoped to a body class toggled on mount/unmount. */
body.<scope>-active .modal-backdrop { z-index: 2600 !important; }
body.<scope>-active .modal          { z-index: 2610 !important; }
```

The body class is toggled in the component lifecycle:

```js
onMounted(()       => document.body.classList.add("<scope>-active"));
onBeforeUnmount(() => document.body.classList.remove("<scope>-active"));
```

The controller also strips Frappe's default chrome (`.sticky-top`, `.body-sidebar`) so the Vue shell owns the full page.

> ⚠️ **Gotcha:** Vuetify dialogs teleport to `.v-overlay-container` at the `<body>` root — any font/theme CSS must target that container too, not just `.<scope>`.

---

Everything else (which views, which columns, which filters) is app-specific and built on top of these primitives.
