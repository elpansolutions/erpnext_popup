import frappe


def _get_base_method(original_method_name: str, my_override: str):
	"""
	Return the previous override in the chain (e.g. India Compliance) or the original ERPNext method.
	"""
	overrides = frappe.get_hooks("override_whitelisted_methods", {}).get(original_method_name, [])
	for override in reversed(overrides):
		if override != my_override:
			return frappe.get_attr(override)
	return frappe.get_attr(original_method_name)


@frappe.whitelist()
def get_outstanding_reference_documents(args, validate=False):
	method_name = "erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents"
	base_fn = _get_base_method(
		method_name,
		"rrs_customizations.overrides.payment_entry.get_outstanding_reference_documents",
	)
	data = base_fn(args, validate=validate)
	if not data:
		return data

	pi_names = [
		d.get("voucher_no")
		for d in data
		if d.get("voucher_type") == "Purchase Invoice" and d.get("voucher_no")
	]
	if pi_names:
		bill_dates = dict(
			frappe.get_all(
				"Purchase Invoice",
				filters={"name": ["in", pi_names]},
				fields=["name", "bill_date"],
				as_list=True,
			)
		)
		for d in data:
			if d.get("voucher_type") == "Purchase Invoice":
				d["bill_date"] = bill_dates.get(d.get("voucher_no"))

	return data


@frappe.whitelist()
def get_reference_details(
	reference_doctype, reference_name, party_account_currency, party_type=None, party=None
):
	method_name = "erpnext.accounts.doctype.payment_entry.payment_entry.get_reference_details"
	base_fn = _get_base_method(
		method_name,
		"rrs_customizations.overrides.payment_entry.get_reference_details",
	)
	res = base_fn(
		reference_doctype,
		reference_name,
		party_account_currency,
		party_type=party_type,
		party=party,
	)
	if reference_doctype == "Purchase Invoice" and reference_name:
		res["bill_date"] = frappe.db.get_value("Purchase Invoice", reference_name, "bill_date")

	return res


def validate_payment_entry(doc, method=None):
	for ref in doc.get("references") or []:
		if ref.reference_doctype == "Purchase Invoice" and ref.reference_name and not ref.get("bill_date"):
			ref.bill_date = frappe.db.get_value("Purchase Invoice", ref.reference_name, "bill_date")
