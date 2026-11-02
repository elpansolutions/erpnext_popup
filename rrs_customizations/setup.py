import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup_custom_fields():
	custom_fields = {
		"Customer": [
			{
				"fieldname": "custom_sales_person",
				"label": "Sales Person",
				"fieldtype": "Link",
				"options": "Sales Person",
				"allow_in_quick_entry": 1,
				"insert_after": "customer_name",
			}
		]
	}
	create_custom_fields(custom_fields, update=True)


def remove_quick_entry_from_sales_team():
	"""
	Ensure sales_team (Table field) does not have allow_in_quick_entry or reqd enabled
	which breaks Quick Entry in Frappe.
	"""
	frappe.db.delete(
		"Property Setter",
		{
			"doc_type": "Customer",
			"field_name": "sales_team",
			"property": ("in", ["allow_in_quick_entry", "reqd"]),
		},
	)
	frappe.clear_cache(doctype="Customer")


def unlock_transporter_fields():
	"""
	Ensure transporter_name is editable and visible across Sales Invoice and Delivery Note,
	removing the 'read_only_depends_on: eval: doc.ewaybill' lock.
	"""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for dt in ["Sales Invoice", "Delivery Note", "Purchase Invoice", "Stock Entry", "Subcontracting Receipt"]:
		cf_name = f"{dt}-transporter_name"
		if frappe.db.exists("Custom Field", cf_name):
			frappe.db.set_value(
				"Custom Field",
				cf_name,
				{
					"read_only": 0,
					"read_only_depends_on": "",
					"allow_on_submit": 1,
				},
				update_modified=False,
			)

		frappe.db.delete(
			"Property Setter",
			{
				"doc_type": dt,
				"field_name": "transporter_name",
				"property": "read_only_depends_on",
			},
		)

		try:
			make_property_setter(dt, "transporter_name", "read_only", 0, "Check", validate_fields_for_doctype=False)
			make_property_setter(dt, "transporter_name", "allow_on_submit", 1, "Check", validate_fields_for_doctype=False)
		except Exception:
			pass

		frappe.clear_cache(doctype=dt)

	frappe.db.commit()


def after_migrate():
	setup_custom_fields()
	remove_quick_entry_from_sales_team()
	unlock_transporter_fields()

