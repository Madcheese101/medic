<template>
	<v-card v-if="!ctx" :loading="loadingCtx">
		<v-card-text class="text-medium-emphasis">
			{{ loadingCtx ? __("Loading…") : __("POS is not configured.") }}
		</v-card-text>
	</v-card>

	<v-row v-else dense>
		<!-- Left: customer + cart + totals -->
		<v-col cols="12" md="7">
			<v-card>
				<v-card-text class="d-flex flex-column" style="max-height: calc(100vh - 220px)">
					<div class="d-flex align-center ga-2 mb-3">
						<v-spacer />
						<v-btn
							variant="text"
							size="small"
							prepend-icon="mdi-printer"
							:disabled="!lastInvoice"
							@click="printInvoice(lastInvoice)"
						>
							{{ __("Print last") }}
						</v-btn>
						<v-btn
							variant="text"
							size="small"
							color="error"
							prepend-icon="mdi-cart-remove"
							:disabled="!cart.length"
							@click="clearCart"
						>
							{{ __("Clear") }}
						</v-btn>
					</div>

					<v-autocomplete
						v-model="customer"
						:items="customerOptions"
						:label="__('Customer')"
						prepend-inner-icon="mdi-account-outline"
						item-props
						hide-details
						class="mb-3"
						@update:search="searchCustomers"
					/>

					<div class="flex-grow-1 overflow-y-auto" style="min-height: 0">
						<v-table density="comfortable">
							<thead>
							<tr>
								<th>{{ __("Item") }}</th>
								<th style="width: 130px">{{ __("UOM") }}</th>
								<th style="width: 110px">{{ __("Qty") }}</th>
								<th class="text-end">{{ __("Rate") }}</th>
								<th class="text-end">{{ __("Amount") }}</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="(line, i) in cart" :key="i">
								<td>{{ line.item_name }}</td>
								<td>
									<v-select
										v-model="line.uom"
										:items="line.uoms"
										item-title="uom"
										item-value="uom"
										density="compact"
										variant="plain"
										hide-details
										@update:model-value="(uom) => onUomChange(line, uom)"
									/>
								</td>
								<td>
									<v-text-field
										v-model.number="line.qty"
										type="number"
										min="0"
										density="compact"
										variant="plain"
										hide-details
									/>
								</td>
								<td class="text-end">{{ formatCurrency(line.rate, ctx.currency) }}</td>
								<td class="text-end">{{ formatCurrency(amount(line), ctx.currency) }}</td>
								<td class="text-end">
									<v-btn
										icon="mdi-delete"
										size="small"
										variant="text"
										color="error"
										:title="__('Remove')"
										@click="cart.splice(i, 1)"
									/>
								</td>
							</tr>
							<tr v-if="!cart.length">
								<td colspan="6" class="text-center text-medium-emphasis py-4">
									{{ __("No items yet") }}
								</td>
							</tr>
						</tbody>
						</v-table>
					</div>

					<v-divider class="my-3" />
					<div class="d-flex justify-space-between text-body-2">
						<span class="text-medium-emphasis">{{ __("Total Qty") }}</span>
						<span>{{ totalQty }}</span>
					</div>
					<div class="d-flex justify-space-between text-subtitle-1 font-weight-medium mt-1">
						<span>{{ __("Total") }}</span>
						<span>{{ formatCurrency(netTotal, ctx.currency) }}</span>
					</div>

					<v-switch
						v-model="printOnPay"
						:label="__('Print receipt after payment')"
						color="primary"
						density="compact"
						hide-details
						class="mt-2"
					/>
					<v-btn
						color="primary"
						variant="flat"
						block
						class="mt-2"
						prepend-icon="mdi-cash-register"
						:disabled="!cart.length || !customer"
						@click="payOpen = true"
					>
						{{ __("Pay") }}
					</v-btn>
				</v-card-text>
			</v-card>
		</v-col>

		<!-- Right: item picker -->
		<v-col cols="12" md="5">
			<v-card>
				<v-card-text>
					<v-text-field
						v-model="search"
						:label="__('Search items')"
						prepend-inner-icon="mdi-magnify"
						clearable
						hide-details
						class="mb-3"
						@update:model-value="onSearch"
					/>
					<v-list
						:loading="loadingItems"
						density="comfortable"
						class="overflow-y-auto"
						style="max-height: calc(100vh - 220px)"
					>
						<v-list-item
							v-for="item in items"
							:key="item.item_code"
							:title="item.item_name"
							@click="addToCart(item)"
						>
							<template #subtitle>
								{{ __("Available") }}: {{ item.actual_qty }} {{ item.stock_uom }}
							</template>
							<template #append>
								{{ formatCurrency(item.price_list_rate, ctx.currency) }}
							</template>
						</v-list-item>
						<v-list-item v-if="!items.length && !loadingItems">
							<template #title>
								<span class="text-medium-emphasis">{{ __("No items") }}</span>
							</template>
						</v-list-item>
					</v-list>
				</v-card-text>
			</v-card>
		</v-col>
	</v-row>

	<SplitPaymentDialog
		v-if="ctx"
		v-model="payOpen"
		:title="__('Checkout')"
		:outstanding="netTotal"
		:currency="ctx.currency"
		:modes="payModes"
		require-full
		method="pos.create_pos_invoice"
		:extra-args="checkoutArgs"
		@paid="onPaid"
	/>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { call, formatCurrency, notifySuccess, searchLinkOptions } from "../client.js";
import SplitPaymentDialog from "../components/SplitPaymentDialog.vue";

const props = defineProps({
	prescription: { type: String, default: null },
});
const emit = defineEmits(["navigate"]);

const route = useRoute();
const router = useRouter();
// Route name → POS context, so the same view serves Pharmacy now and Test Lab later.
const CONTEXT_BY_ROUTE = { "pharmacy-pos": "pharmacy", "test-lab-pos": "test_lab" };
const context = CONTEXT_BY_ROUTE[route.name] || "pharmacy";

const ctx = ref(null);
const loadingCtx = ref(true);
const cart = ref([]);
const customer = ref(null);
const customerOptions = ref([]);
const items = ref([]);
const search = ref("");
const loadingItems = ref(false);
const payOpen = ref(false);
const printOnPay = ref(true);
const lastInvoice = ref(null);

const payModes = computed(() =>
	(ctx.value?.payment_modes || []).map((m) => ({ name: m.mode_of_payment, type: m.type }))
);
const totalQty = computed(() => cart.value.reduce((s, l) => s + (Number(l.qty) || 0), 0));
const netTotal = computed(() =>
	Number(cart.value.reduce((s, l) => s + amount(l), 0).toFixed(2))
);
const checkoutArgs = computed(() => ({
	context,
	customer: customer.value,
	prescription: props.prescription || null,
	items: cart.value.map((l) => ({
		item_code: l.item_code,
		qty: l.qty,
		uom: l.uom,
		conversion_factor: l.conversion_factor,
		rate: l.rate,
	})),
}));

function amount(line) {
	return Number(((Number(line.qty) || 0) * (Number(line.rate) || 0)).toFixed(2));
}

async function searchCustomers(txt) {
	customerOptions.value = await searchLinkOptions("Customer", txt, {}, "customer_name");
}

async function onSearch() {
	loadingItems.value = true;
	try {
		items.value = await call("pos.pos_search_items", { context, txt: search.value || "" });
	} finally {
		loadingItems.value = false;
	}
}

function addToCart(item) {
	const existing = cart.value.find((l) => l.item_code === item.item_code && l.uom === item.uom);
	if (existing) {
		existing.qty += 1;
	} else {
		cart.value.push({ ...item, uoms: [...item.uoms] });
	}
}

async function onUomChange(line, uom) {
	const { price_list_rate, conversion_factor } = await call("pos.pos_item_price", {
		context,
		item_code: line.item_code,
		uom,
	});
	line.rate = price_list_rate;
	line.price_list_rate = price_list_rate;
	line.conversion_factor = conversion_factor;
}

function clearCart() {
	cart.value = [];
	customer.value = ctx.value?.customer || null;
	// Drop the prescription from the URL so a refresh doesn't re-seed the cart.
	if (props.prescription) router.replace({ name: route.name });
}

function printInvoice(name) {
	if (!name) return;
	// Pharmacy POS receipt uses the POS Profile's print format.
	const fmt = ctx.value?.print_format
		? `&format=${encodeURIComponent(ctx.value.print_format)}`
		: "";
	window.open(
		`/printview?doctype=Sales%20Invoice&name=${encodeURIComponent(name)}${fmt}&trigger_print=1`,
		"_blank"
	);
}

function onPaid(result) {
	notifySuccess(__("Invoice {0} created", [result?.name]));
	lastInvoice.value = result?.name || null;
	if (printOnPay.value) printInvoice(lastInvoice.value);
	clearCart();
	if (props.prescription) emit("navigate", "pharmacy-prescriptions");
}

onMounted(async () => {
	try {
		ctx.value = await call("pos.get_pos_context", { context });
	} finally {
		loadingCtx.value = false;
	}
	if (!ctx.value) return;

	if (props.prescription) {
		const seeded = await call("pos.get_prescription_cart", { context, prescription: props.prescription });
		customer.value = seeded.customer;
		cart.value = seeded.items;
	} else {
		customer.value = ctx.value.customer;
	}
	searchCustomers("");
	onSearch();
});
</script>
