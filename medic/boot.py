import frappe
def extend_boot_info(bootinfo):
	clinic_settings = frappe.get_single("Clinic Setup")
	bootinfo["parent_service"] = clinic_settings.service_parent_item_group
	bootinfo["default_doctor_designation"] = clinic_settings.doctors_default_designation
	bootinfo["pharmacy_item_group"] = clinic_settings.pharmacy_item_group
