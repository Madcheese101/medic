import frappe
def extend_boot_info(bootinfo):
	clinic_settings = frappe.get_single("Clinic Setup")
	bootinfo["parent_service"] = clinic_settings.service_parent_item_group
	bootinfo["default_doctor_designation"] = clinic_settings.doctors_default_designation
	bootinfo["pharmacy_item_group"] = clinic_settings.pharmacy_item_group
	bootinfo["prescription_print_format"] = clinic_settings.prescription_print_format

	# Service item groups (parent + descendants) for the treatment-plan service picker.
	parent = clinic_settings.service_parent_item_group
	if parent:
		from frappe.utils.nestedset import get_descendants_of

		bootinfo["service_item_groups"] = [parent, *get_descendants_of("Item Group", parent)]
	else:
		bootinfo["service_item_groups"] = []
