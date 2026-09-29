import frappe


def sync_sales_person(doc, method=None):
	"""
	If a Sales Person is chosen in custom_sales_person (Quick Entry or Form),
	ensure it is reflected in the sales_team child table.
	"""
	if doc.get("custom_sales_person"):
		existing = [row.sales_person for row in (doc.get("sales_team") or []) if row.sales_person]
		if doc.custom_sales_person not in existing:
			doc.append(
				"sales_team",
				{
					"sales_person": doc.custom_sales_person,
					"allocated_percentage": 100 if not existing else 0,
				},
			)
	elif doc.get("sales_team") and len(doc.sales_team) > 0:
		primary = doc.sales_team[0].sales_person
		if primary and not doc.get("custom_sales_person"):
			doc.custom_sales_person = primary
