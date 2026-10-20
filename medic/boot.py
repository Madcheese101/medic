import frappe

from medic.billing import DISCOUNT_ROLES, mode_currency


def extend_boot_info(bootinfo):
	clinic_settings = frappe.get_single("Clinic Setup")
	bootinfo["parent_service"] = clinic_settings.service_parent_item_group
	bootinfo["default_doctor_designation"] = clinic_settings.doctors_default_designation
	bootinfo["pharmacy_item_group"] = clinic_settings.pharmacy_item_group
	bootinfo["max_discount_percentage"] = clinic_settings.doctor_max_discount_percentage
	bootinfo["discount_roles"] = list(DISCOUNT_ROLES)

	# Cashier POS Profile + its payment modes, so front-desk collections post under it.
	profile_name = clinic_settings.cashier_pos_profile
	bootinfo["cashier_pos_profile"] = profile_name
	bootinfo["cashier_payment_modes"] = _pos_profile_modes(profile_name) if profile_name else []

	# Service item groups (parent + descendants) for the treatment-plan service picker.
	parent = clinic_settings.service_parent_item_group
	if parent:
		from frappe.utils.nestedset import get_descendants_of

		bootinfo["service_item_groups"] = [parent, *get_descendants_of("Item Group", parent)]
	else:
		bootinfo["service_item_groups"] = []


def _pos_profile_modes(profile_name):
	"""The profile's payment modes with their type, shaped like get_payment_modes for the dialogs."""
	profile = frappe.get_cached_doc("POS Profile", profile_name)
	modes = []
	for row in profile.payments:
		modes.append(
			{
				"name": row.mode_of_payment,
				"type": frappe.db.get_value("Mode of Payment", row.mode_of_payment, "type"),
				"currency": mode_currency(row.mode_of_payment, profile.company),
			}
		)
	return modes
