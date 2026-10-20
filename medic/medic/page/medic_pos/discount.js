// Discounts: the server's discount roles (doctors and cashiers), up to Clinic Setup's cap.
// The server enforces both.
export const maxDiscount = Number(frappe.boot.max_discount_percentage) || 0;

export function hasDiscountRole() {
	return (frappe.boot.discount_roles || []).some((r) => frappe.user_roles.includes(r));
}

export function canDiscount() {
	return maxDiscount > 0 && hasDiscountRole();
}

export function discountRule(v) {
	return (!v || (v >= 0 && v <= maxDiscount)) || __("Must be between 0 and {0}", [maxDiscount]);
}
