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
		],
		"Payment Entry Reference": [
			{
				"fieldname": "bill_date",
				"label": "Supplier Invoice Date",
				"fieldtype": "Date",
				"in_list_view": 1,
				"columns": 2,
				"read_only": 1,
				"insert_after": "bill_no",
			}
		],
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


def sync_payment_entry_grid_settings():
	"""
	Ensure 'bill_date' is included in saved GridView column settings for Payment Entry Reference
	so that existing users who previously configured columns can see Supplier Invoice Date.
	"""
	import json

	settings = frappe.db.sql(
		"SELECT user, data FROM `__UserSettings` WHERE doctype='Payment Entry'",
		as_dict=True,
	)
	for s in settings:
		try:
			data = json.loads(s.data) if s.data else {}
			grid_view = data.get("GridView", {})
			cols = grid_view.get("Payment Entry Reference")
			if isinstance(cols, list) and cols:
				fieldnames = [c.get("fieldname") for c in cols if isinstance(c, dict)]
				if "bill_date" not in fieldnames:
					new_col = {"fieldname": "bill_date", "columns": 2, "sticky": 0}
					insert_idx = -1
					for target in ["bill_no", "due_date", "reference_name"]:
						if target in fieldnames:
							insert_idx = fieldnames.index(target)
							break
					if insert_idx != -1:
						cols.insert(insert_idx + 1, new_col)
					else:
						cols.append(new_col)

					frappe.db.sql(
						"UPDATE `__UserSettings` SET data = %s WHERE user = %s AND doctype = 'Payment Entry'",
						(json.dumps(data), s.user),
					)
		except Exception:
			pass

	frappe.clear_cache(doctype="Payment Entry")


def after_migrate():
	setup_custom_fields()
	remove_quick_entry_from_sales_team()
	unlock_transporter_fields()
	sync_payment_entry_grid_settings()

