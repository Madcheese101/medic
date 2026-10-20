# Medic — Clinic / Hospital Management App

Medic is a [Frappe](https://frappeframework.com/) + [ERPNext](https://erpnext.com/) app that adds a **point-of-sale front desk** for a clinic: patient files, doctor scheduling, appointments, treatment plans, prescriptions, pharmacy/lab checkout, and billing. The whole clinical/front-desk experience lives in a single Vue 3 + Vuetify single-page app mounted on a Frappe desk page (`Medic POS`); the backend is a thin whitelisted API over ERPNext's Customer, Sales Invoice, and Item doctypes plus a handful of Medic-specific doctypes.

- **App slug:** `medic` · **Version:** `0.0.1` · **License:** MIT · **Publisher:** Nawa Clinic
- **Requires:** Frappe v15, ERPNext (uses Customer, Item, Sales Invoice, POS Profile), Python ≥ 3.10
- **Primary UI:** desk page `medic-pos` (route `/app/medic-pos`)
- **Language:** built for Arabic / RTL; appointment and action statuses are stored as Arabic strings.

---

## 1. Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app medic
```

Frontend assets are built by Frappe's bundler (`app_include_js = "medic-pos.bundle.js"`). After JS/Vue changes:

```bash
bench build --app medic          # production build
bench watch                      # rebuild on change during development
```

Vuetify, MDI icons, and the `ibm-plex-sans-arabic` font are shipped from `node_modules` and linked into `<head>` at page load (see `medic_pos.js`), not bundled. Install them once:

```bash
cd apps/medic && npm install     # vuetify@3.7.19 (installed with --legacy-peer-deps)
```

### Contributing

`pre-commit` runs ruff, eslint, prettier, and pyupgrade:

```bash
cd apps/medic && pre-commit install
```

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser — Vue 3 SPA (Vuetify 3 + Pinia + vue-router)        │
│  mounted on Frappe desk page  /app/medic-pos                 │
│  views/  components/  stores/defaults.js  router/index.js    │
└───────────────┬─────────────────────────────────────────────┘
                │  frappe.call → whitelisted methods
                │  (client.js `call()` wrapper)
┌───────────────▼─────────────────────────────────────────────┐
│  medic/medic/page/medic_pos/api.py  (~40 whitelisted fns)    │
│  thin layer over ERPNext + Medic doctypes                    │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│  Doctypes                                                    │
│   ERPNext: Customer (patient), Item, Sales Invoice, POS      │
│            Profile, Employee                                 │
│   Medic:   Clinic Setup, Doctor Schedule, Patient            │
│            Appointment, Treatment Plan, Prescription,        │
│            Medical History, Illness, Appointment Actions     │
└──────────────────────────────────────────────────────────────┘
```

Key idea: **patients are ERPNext Customers** and **all money is ERPNext Sales Invoices**. Medic doctypes add the clinical layer on top and link back to invoices via custom fields.

### Directory map

| Path | Purpose |
| --- | --- |
| `medic/hooks.py` | App hooks — `doc_events`, `extend_bootinfo`, fixtures, asset include |
| `medic/boot.py` | Pushes Clinic Setup values into `frappe.boot` for the frontend |
| `medic/events.py` | Document event handlers (Employee / Customer / Sales Invoice) |
| `medic/fixtures/` | `custom_field.json`, `property_setter.json` (shipped customizations) |
| `medic/medic/doctype/` | Medic doctype definitions |
| `medic/medic/page/medic_pos/` | The desk page: Python API + Vue SPA |
| `AppDesign.md` | Design-system reference (Vuetify + Frappe conventions) |
| `medic_project.md` | Original project brief / requirements |

---

## 3. Configuration — `Clinic Setup`

A **Single** doctype holding clinic-wide settings. Read on the backend via `frappe.get_single("Clinic Setup")` and surfaced to the frontend through `extend_bootinfo` (`boot.py`).

| Field | Type | Used for |
| --- | --- | --- |
| `service_parent_item_group` | Link → Item Group (req) | Parent group under which billable services live |
| `doctors_default_designation` | Link → Designation (req) | Employees with this designation auto-get a Doctor Schedule |
| `enable_pharmacy` / `enable_test_lab` | Check | Feature toggles |
| `pharmacy_item_group` / `test_lab_item_group` | Link → Item Group | Item group filter for each POS context |
| `pharmacy_pos_profile` / `test_lab_pos_profile` | Link → POS Profile | POS Profile used at pharmacy / lab checkout |
| `prescription_print_format` | Link → Print Format | Print format for prescriptions |

`extend_bootinfo` exposes `parent_service`, `default_doctor_designation`, `pharmacy_item_group`, and `prescription_print_format` on `frappe.boot`.

---

## 4. Data model

### Custom fields (shipped as fixtures)

| Doctype | Field | Type | Purpose |
| --- | --- | --- | --- |
| **Customer** | `phone_number` | Phone | Patient mobile (filterable) |
| | `date_of_birth` | Date | |
| | `blood_type` | Select `A+…O-` | |
| | `allow_credit` | Check | Waives the final-session payment gate on treatment plans |
| **Sales Invoice** | `patient_appointment` | Link → Patient Appointment | Links invoice back to its appointment |
| | `treatment_plan` | Link → Treatment Plan | Links invoice to a plan |
| | `is_action_invoice` | Check | Marks an extra-service ("action") invoice vs. the main appointment invoice |
| **Stock Entry** | `patient_appointment`, `sales_invoice` | Link | Traceability |

### Medic doctypes

| Doctype | Kind | Autoname | Notes |
| --- | --- | --- | --- |
| **Clinic Setup** | Single | — | See §3 |
| **Doctor Schedule** | Document | `field:employee_name` | One per doctor; child table `schedule` of `Doctor Schedule Days` |
| **Doctor Schedule Days** | Child table | — | `day`, `is_active`, `maximum_appointments`, `from_time`, `to_time` |
| **Patient Appointment** | Submittable | `naming_series` `APP-.YY.-` | The central clinical record — see §6 |
| **Appointment Actions** | Child table | — | Extra billable services on an appointment: `invoice`, `invoice_type`, `action_type`, `paid` |
| **Treatment Plan** | Submittable | `naming_series` `TP-.YY.-` | Multi-session plan billed as one invoice — see §6 |
| **Prescription** | Document | hash | `patient`, `appointment`, `items`, `invoice_created`, `sales_invoice` |
| **Prescription Items** | Child table | — | `item`, `route`, `times`, `per` (Day/Week), `for` |
| **Medical History** | Document | `field:customer` | One per Customer; tables `medical_history` + `skin_illness`, plus `notes` |
| **Medical History Item** | Child table | — | Single Link → `Illness` |
| **Illness** | Document | `field:illness_name` | `illness_name`, `illness_type` (أخرى / جلدي) |

**Patient Appointment key fields:** `appointment_type` (كشف/علاج/مراجعة/متابعة دورية), `customer`, `employee` (doctor), `appointment_date`, `service_type` (Item Group) + `service` (Item), `appointment_status` (انتظار/غير مؤكد/مؤكد/مكتمل), `invoice`, `queue`, `session_no`, `treatment_plan`, child `actions`.

> **Status vocabulary is Arabic and load-bearing** — the backend compares against literal strings:
> `انتظار` = Pending · `غير مؤكد` = Not Confirmed · `مؤكد` = Confirmed/Paid · `مكتمل` = Completed. Treatment Plan status is English (`Pending/Active/Completed/Cancelled`).

---

## 5. Backend API

All endpoints are `@frappe.whitelist()` methods in `medic/medic/page/medic_pos/api.py`, called as `medic.medic.page.medic_pos.api.<fn>`. Complex reads use `frappe.qb.get_query` (per project convention).

**Defaults & profile**
- `load_defaults()` → `{pos_profile, roles, employee}` — the user's default POS Profile doc, their roles, and their linked Employee (if any). Cached client-side in the Pinia `defaults` store.
- `get_my_profile()` / `save_profile(language, user_image, new_password)` — edit the logged-in User's language, avatar, password.

**Patients** (ERPNext Customer)
- `get_patients(customer_name, mobile, file_no, limit)` — DB-filtered list (LIKE on name / phone / docname).
- `create_patient(...)` / `get_patient(name)` / `save_patient(...)` — CRUD over the patient fields.
- `_customer_balance` / `_medical_history` feed `get_patient`; `save_medical_history(customer, notes, medical_history, skin_illness)` saves the Medical History doc.

**Schedule**
- `get_my_schedule(employee)` / `save_schedule(rows, employee)` — the Doctor Schedule week grid.
- `get_doctor_availability(employee)` — which weekdays the doctor works; drives the frontend date picker.

**Appointments** (see §6 for the lifecycle)
- `get_appointments(...)`, `get_appointment(name)`, `create_appointment(...)`
- `confirm_appointment`, `confirm_appointment_invoice`, `pay_appointment`, `complete_appointment`, `check_in`
- `create_appointment_action`, `pay_appointment_action`, `save_appointment_notes`

**Treatment plans**
- `create_treatment_plan`, `create_treatment_plan_invoice`, `create_session`
- `get_treatment_plans`, `get_active_treatment_plans`, `list_treatment_plans`, `get_treatment_plan`

**Prescriptions**
- `create_prescription(appointment, items)`, `get_prescription(name)`, `update_prescription(name, items)`
- `list_prescriptions(customer, mobile, include_invoiced)`

**Invoices & payments**
- `get_sales_invoices(...)`, `get_sales_invoice(name)`, `get_payment_modes()`
- `add_payment(invoice, amount, mode_of_payment, ...)`, `record_payments(invoice, payments)`

**Pharmacy / Lab POS** (context = `"pharmacy"` or `"test_lab"`, resolved against Clinic Setup)
- `get_pos_context(context)`, `pos_search_items(context, txt)`, `pos_item_price(context, item_code, uom)`
- `get_prescription_cart(context, prescription)` — prefill cart from a prescription
- `create_pos_invoice(context, customer, items, payments, prescription=None)` — a real POS `is_pos` Sales Invoice with `update_stock`; prescription invoices must be paid in full.

**Search**
- `custom_search_link(...)` — a link-field autocomplete used by the SPA's search fields.

---

## 6. Core workflows

### Appointment lifecycle

Statuses flow **انتظار → غير مؤكد → مؤكد → مكتمل**:

1. **Create** — `create_appointment(...)` inserts and **submits** the Patient Appointment at status `انتظار` (Pending).
2. **Confirm** — `confirm_appointment` calls `_ensure_appointment_invoice`, creating a **draft** Sales Invoice (linked via `patient_appointment`) and moving to `غير مؤكد` (Not Confirmed). Idempotent.
3. **Pay** — `pay_appointment(name, payments)` submits the invoice if still draft, records each payment via `add_payment`, and flips to `مؤكد` (Confirmed) once `outstanding_amount <= 0`.
4. **Check in** — `check_in` assigns a per-doctor, per-day `queue` number. A non-plan appointment must be `مؤكد` (paid) first.
5. **Complete** — `complete_appointment` sets `مكتمل`; requires the appointment to have been checked in.

**Extra services (actions):** `create_appointment_action` drafts a *separate* invoice (`is_action_invoice = 1`) for a service from a **different item group** than the main appointment, recorded as a row in the `actions` child table and paid independently via `pay_appointment_action`. `get_appointment` decorates each action row with its own invoice totals.

### Treatment plans & sessions

1. `create_treatment_plan(customer, employee, service, total_sessions, notes)` — submits a plan at `Pending`.
2. `create_treatment_plan_invoice(name)` — creates **one** Sales Invoice for the whole plan (`qty = total_sessions`) and moves the plan to `Active`.
3. `create_session(treatment_plan, appointment_date)` — spawns the next Patient Appointment (`session_no` = count + 1). A **payment gate** (`_session_gate_ok`) governs when sessions may proceed:
   - Intermediate sessions need the plan invoice ≥ `DEPOSIT_PCT` (20%) paid, unless the plan has `skip_deposit`.
   - The **last** session requires the invoice fully paid, unless the Customer has `allow_credit`.
   A session that already clears the gate is created directly at `مؤكد`.
4. `check_in` on a session re-checks the gate and increments `completed_sessions`.

### Pharmacy / lab checkout

The pharmacy Prescription list (`list_prescriptions`) → open a prescription in the POS view → `get_prescription_cart` prefills items → `create_pos_invoice` writes a stock-updating POS Sales Invoice and stamps the Prescription (`invoice_created`, `sales_invoice`). Prescription invoices must be paid in full.

---

## 7. Document events (`hooks.py` → `events.py`)

| Doctype | Event | Handler | Effect |
| --- | --- | --- | --- |
| Employee | `after_insert` | `on_employee_create` | If designation == Clinic Setup default doctor designation, auto-create a filled `Doctor Schedule` |
| Customer | `after_insert` | `on_customer_create` | Auto-create a `Medical History` record for the new patient |
| Sales Invoice | `on_cancel` | `on_sales_invoice_cancel` | Revert a confirmed appointment (`مؤكد` → `غير مؤكد`) when its invoice is cancelled |

`on_sales_invoice_submit` exists but is **commented out** in `doc_events` — appointment/action paid-status is driven imperatively from the pay endpoints instead.

---

## 8. Frontend (Vue SPA)

Mounted by `medic_pos.js` via `frappe.MedicPos.Controller`. Uses HTML5 history routing under `/app/medic-pos` (`router/index.js`), with a shim that preserves Frappe's router history state.

### Views & routes

| Route name | Path | View |
| --- | --- | --- |
| `patients` | `/app/medic-pos` | `PatientsView` (patient list + new-patient) |
| `patient` | `/patient/:patient?` | `PatientView` (file + balance chip + medical history) |
| `appointments` | `/appointments` | `AppointmentsView` |
| `appointment` | `/appointment/:name?` | `AppointmentView` (lifecycle actions, prescriptions) |
| `treatments` | `/treatments` | `TreatmentsView` |
| `invoices` | `/invoices` | `InvoicesView` |
| `pharmacy-prescriptions` | `/pharmacy/prescriptions` | `PrescriptionsView` |
| `pharmacy-pos` | `/pharmacy/pos/:prescription?` | `PosView` (cart / checkout) |
| `profile` | `/profile` | `ProfileView` |
| `schedule` | `/schedule` | `ScheduleView` |

Sidebar nav (`app.vue`): Patients, Appointments, Treatments, Invoices, Pharmacy (Prescription, POS); the avatar menu offers Profile, Schedule, Logout.

### Components

Dialogs and forms: `NewPatientDialog`, `NewAppointmentForm`, `AppointmentActionDialog`, `NewTreatmentDialog` / `TreatmentDialog` / `NewSessionDialog`, `PrescriptionForm`, `InvoiceDetailsDialog`, `SplitPaymentDialog`, `DoctorDatePicker` (limits selectable days to the doctor's schedule), `IllnessTable`, `PatientTreatments`.

### State — `stores/defaults.js` (Pinia)

Holds the user's POS Profile doc, roles, and linked Employee. `load()` is de-duplicated (returns the in-flight promise for concurrent callers) and cached after first success. Getters: `currency`, `employeeName`, `isDoctor`, `hasRole(role)`.

### `constants.js`

Frontend mirrors of doctype Select options (blood types, appointment/action types, statuses, prescription routes) **and** status→color helpers (`appointmentStatusColor`, `treatmentStatusColor`, `invoiceStatusColor`). Keep these in sync with the doctype JSON / custom fields they mirror.

### Design system

See `AppDesign.md` for the full reference. Highlights:
- Vuetify global `defaults`: flat bordered rounded cards, pill outlined inputs, sentence-case buttons.
- Frappe integration gotchas — CSS scoped to the app root; a `body.medic-active` class lifts native Frappe modals above Vuetify overlays; font must also target `.v-overlay-container` (dialogs teleport to `<body>`).
- Mobile-first via `useDisplay().mobile` — drawer collapses, buttons go icon-only.
- Feedback defers to Frappe's native `frappe.msgprint` / `frappe.show_alert` / `frappe.confirm`.
- RTL and language follow Frappe's session locale (Arabic-first).

---

## 9. Roles & access

The `medic-pos` desk page is granted to: **Medic Doctor**, **Sales User**, **Accounts User**, **System Manager**. `load_defaults` returns `frappe.get_roles()` and the linked Employee so the SPA can gate doctor-only UI (`isDoctor`, `hasRole`).

---

## 10. Notes for maintainers

- **Arabic status strings are contractual.** Changing them means updating `constants.js`, every `appointment_status`/`action_type` comparison in `api.py` and `events.py`, and the doctype Select options together.
- **Money is never computed in the browser** — always through invoice totals / `format_currency`.
- **`frappe.qb.get_query`** is the house style for multi-filter reads.
- Read-after-submit fields (`invoice`, `appointment_status`, `queue`) are written with `db_set` to bypass submit locks.
- After editing any `.vue`/`.js`, run `bench build --app medic` (or `bench watch`).
