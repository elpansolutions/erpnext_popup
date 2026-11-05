import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_outstanding_reference_documents as erpnext_get_outstanding_docs,
	get_reference_details as erpnext_get_ref_details,
)


@frappe.whitelist()
def get_outstanding_reference_documents(args, validate=False):
	data = erpnext_get_outstanding_docs(args, validate=validate)
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
	res = erpnext_get_ref_details(
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
