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


def after_migrate():
	setup_custom_fields()
	remove_quick_entry_from_sales_team()
