import base64
import os
import re
import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf


def inline_assets_for_pdf(html):
	"""
	Inlines all images (as base64) and stylesheets directly into the HTML
	so wkhtmltopdf can render 100% self-contained without needing any network requests.
	"""
	# 1. Inline images as base64
	def replace_img(match):
		src = match.group(1)
		if src.startswith("data:"):
			return match.group(0)

		clean_src = src.split("?")[0]
		file_path = None
		if clean_src.startswith("/files/"):
			file_path = frappe.get_site_path("public", clean_src.lstrip("/"))
		elif clean_src.startswith("/private/files/"):
			file_path = frappe.get_site_path(clean_src.lstrip("/"))
		elif clean_src.startswith("/assets/"):
			file_path = os.path.join(frappe.get_site_path(), "assets", clean_src.replace("/assets/", "", 1))
		elif not clean_src.startswith("http://") and not clean_src.startswith("https://"):
			file_path = frappe.get_site_path("public", "files", clean_src.lstrip("/"))

		if file_path and os.path.exists(file_path):
			try:
				ext = os.path.splitext(file_path)[1].lower().lstrip(".")
				if ext in ["jpg", "jpeg"]:
					mime = "image/jpeg"
				elif ext == "png":
					mime = "image/png"
				elif ext == "svg":
					mime = "image/svg+xml"
				elif ext == "webp":
					mime = "image/webp"
				else:
					mime = "image/png"

				with open(file_path, "rb") as f:
					b64 = base64.b64encode(f.read()).decode("utf-8")
				return f'src="data:{mime};base64,{b64}"'
			except Exception:
				pass
		return match.group(0)

	html = re.sub(r'src=["\']([^"\']+)["\']', replace_img, html)

	# 2. Inline stylesheet links
	def replace_css_link(match):
		full_tag = match.group(0)
		href_match = re.search(r'href=["\']([^"\']+)["\']', full_tag)
		if not href_match:
			return full_tag

		href = href_match.group(1).split("?")[0]
		# Strip host if present
		if "://" in href:
			href = "/" + href.split("://", 1)[1].split("/", 1)[1] if "/" in href.split("://", 1)[1] else href

		if href.startswith("/assets/"):
			rel_path = href.replace("/assets/", "", 1)
			css_path = os.path.join(frappe.get_site_path(), "assets", rel_path)
			if not os.path.exists(css_path):
				# fallback to bench-level sites/assets
				css_path = os.path.join(frappe.utils.get_bench_path(), "sites", "assets", rel_path)

			if os.path.exists(css_path):
				try:
					with open(css_path, "r", encoding="utf-8") as f:
						css_content = f.read()
					return f"<style>\n{css_content}\n</style>"
				except Exception:
					pass
		return ""

	html = re.sub(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', replace_css_link, html)
	html = re.sub(r'<link[^>]+href=["\'][^"\']+\.css[^"\']*["\'][^>]*>', replace_css_link, html)

	return html


def get_pdf_options(html=""):
	"""
	Returns optimal wkhtmltopdf options for invoice printing in Landscape orientation.
	"""
	return {
		"orientation": "Landscape",
		"page-size": "A4",
		"margin-top": "4mm",
		"margin-bottom": "4mm",
		"margin-left": "4mm",
		"margin-right": "4mm",
		"load-error-handling": "ignore",
	}


def auto_attach_pdf(doc, method=None):
	"""
	Automatically generates and stores/attaches the PDF
	into ERPNext Attachments with the document number (doc.name) as the file name.
	Supports Sales Invoice and Delivery Note.
	"""
	if isinstance(doc, str):
		return

	if doc.docstatus != 1:
		return

	dt = doc.doctype
	file_name = f"{doc.name}.pdf"

	# Avoid duplicate attachments
	if frappe.db.exists(
		"File",
		{
			"attached_to_doctype": dt,
			"attached_to_name": doc.name,
			"file_name": file_name,
		},
	):
		return

	try:
		# Dynamically resolve default print format
		print_format = (
			doc.get("print_format")
			or frappe.db.get_value(
				"Property Setter",
				{"doc_type": dt, "property": "default_print_format"},
				"value",
			)
			or frappe.get_meta(dt).default_print_format
			or ("v5" if dt == "Sales Invoice" else "Delivery Note Standard")
		)

		html = frappe.get_print(
			doctype=dt,
			name=doc.name,
			print_format=print_format,
			as_pdf=False,
			doc=doc,
		)

		html = inline_assets_for_pdf(html)
		pdf_content = get_pdf(html, options=get_pdf_options(html))

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": dt,
				"attached_to_name": doc.name,
				"content": pdf_content,
				"is_private": 1,
			}
		)
		file_doc.insert(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(
			title=f"Auto Attach PDF Failed: {doc.name}",
			message=frappe.get_traceback(),
		)


@frappe.whitelist(allow_guest=True)
def download_pdf(
	doctype: str,
	name: str,
	format: str | None = None,
	doc=None,
	no_letterhead: bool | int = 0,
	language: str | None = None,
	letterhead: str | None = None,
	pdf_generator: str | None = None,
):
	"""
	Overrides standard download_pdf to render self-contained HTML with inlined assets,
	guaranteeing the PDF downloads cleanly in Landscape orientation with doc.name.pdf.
	"""
	from frappe.utils.print_format import print_language, validate_print_permission

	if isinstance(doc, str):
		doc = frappe.get_doc(doctype, doc)
	doc = doc or frappe.get_doc(doctype, name)
	validate_print_permission(doc)

	with print_language(language):
		html = frappe.get_print(
			doctype,
			name,
			format,
			doc=doc,
			as_pdf=False,
			letterhead=letterhead,
			no_letterhead=no_letterhead,
		)
		html = inline_assets_for_pdf(html)
		pdf_file = get_pdf(html, options=get_pdf_options(html))

	clean_name = str(name).replace(" ", "-").replace("/", "-")
	frappe.local.response.filename = f"{clean_name}.pdf"
	frappe.local.response.filecontent = pdf_file
	frappe.local.response.type = "pdf"


def sync_sales_invoice_addresses(doc, method=None):
	"""
	Ensure unsubmitted Sales Invoices and Delivery Notes (docstatus == 0) always have their
	address_display and shipping_address synced with the latest Address records.
	Also auto-populates customer_address and shipping_address_name if missing.
	"""
	if doc.docstatus != 0:
		return

	from frappe.contacts.doctype.address.address import get_default_address, render_address
	from erpnext.accounts.party import get_party_shipping_address

	# 1. Billing Address
	if not doc.customer_address and doc.customer:
		doc.customer_address = get_default_address("Customer", doc.customer, "is_primary_address")

	if doc.customer_address and frappe.db.exists("Address", doc.customer_address):
		doc.address_display = render_address(doc.customer_address)
		gstin = frappe.db.get_value("Address", doc.customer_address, "gstin")
		if gstin and hasattr(doc, "billing_address_gstin"):
			doc.billing_address_gstin = gstin

	# 2. Shipping Address
	if not doc.shipping_address_name and doc.customer:
		doc.shipping_address_name = get_party_shipping_address("Customer", doc.customer) or doc.customer_address

	if doc.shipping_address_name and frappe.db.exists("Address", doc.shipping_address_name):
		doc.shipping_address = render_address(doc.shipping_address_name)


def get_saved_sales_invoice_qty(item_code, batch_no=None, warehouse=None, exclude_invoice=None, exclude_doctype=None):
	"""
	Returns total quantity of an item/batch reserved in saved (draft, docstatus=0)
	Sales Invoices and Delivery Notes (excluding returns and optionally excluding a given document).
	Includes both billed qty and custom_free_qty.
	"""
	if not item_code:
		return 0.0

	total_reserved = 0.0

	# 1. Draft Sales Invoices
	si_conditions = [
		"si.docstatus = 0",
		"si.is_return = 0",
		"sii.item_code = %(item_code)s"
	]
	si_params = {"item_code": item_code}

	if exclude_invoice and (not exclude_doctype or exclude_doctype == "Sales Invoice"):
		si_conditions.append("si.name != %(exclude_invoice)s")
		si_params["exclude_invoice"] = exclude_invoice

	if batch_no:
		si_conditions.append("(sii.batch_no = %(batch_no)s OR sii.custom_batch_id_all = %(batch_no)s)")
		si_params["batch_no"] = batch_no

	if warehouse:
		si_conditions.append("sii.warehouse = %(warehouse)s")
		si_params["warehouse"] = warehouse

	si_query = f"""
		SELECT 
			SUM(
				(COALESCE(sii.qty, 0) + COALESCE(sii.custom_free_qty, 0)) 
				* COALESCE(sii.conversion_factor, 1.0)
			) AS reserved_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
		WHERE {" AND ".join(si_conditions)}
	"""
	res_si = frappe.db.sql(si_query, si_params, as_dict=True)
	if res_si and res_si[0].reserved_qty:
		total_reserved += flt(res_si[0].reserved_qty)

	# 2. Draft Delivery Notes
	dn_conditions = [
		"dn.docstatus = 0",
		"dn.is_return = 0",
		"dni.item_code = %(item_code)s"
	]
	dn_params = {"item_code": item_code}

	if exclude_invoice and (not exclude_doctype or exclude_doctype == "Delivery Note"):
		dn_conditions.append("dn.name != %(exclude_invoice)s")
		dn_params["exclude_invoice"] = exclude_invoice

	if batch_no:
		dn_conditions.append("(dni.batch_no = %(batch_no)s OR dni.custom_batch_id_all = %(batch_no)s)")
		dn_params["batch_no"] = batch_no

	if warehouse:
		dn_conditions.append("dni.warehouse = %(warehouse)s")
		dn_params["warehouse"] = warehouse

	dn_query = f"""
		SELECT 
			SUM(
				(COALESCE(dni.qty, 0) + COALESCE(dni.custom_free_qty, 0)) 
				* COALESCE(dni.conversion_factor, 1.0)
			) AS reserved_qty
		FROM `tabDelivery Note Item` dni
		INNER JOIN `tabDelivery Note` dn ON dni.parent = dn.name
		WHERE {" AND ".join(dn_conditions)}
	"""
	res_dn = frappe.db.sql(dn_query, dn_params, as_dict=True)
	if res_dn and res_dn[0].reserved_qty:
		total_reserved += flt(res_dn[0].reserved_qty)

	return total_reserved


def validate_sales_invoice_stock(doc, method=None):
	"""
	Validates that quantities being billed/delivered in a Sales Invoice or Delivery Note (including custom_free_qty)
	do not exceed available stock after accounting for other saved (unsubmitted) Sales Invoices & Delivery Notes.
	"""
	if doc.is_return or doc.docstatus != 0:
		return

	if doc.doctype == "Sales Invoice" and not doc.update_stock:
		return

	requested_map = {}
	row_map = {}
	for row in doc.get("items", []):
		if not row.item_code:
			continue

		is_stock_item = frappe.get_cached_value("Item", row.item_code, "is_stock_item")
		if not is_stock_item:
			continue

		warehouse = row.warehouse or doc.set_warehouse
		if not warehouse:
			continue

		batch_no = row.batch_no or row.get("custom_batch_id_all")
		if batch_no and not frappe.db.exists("Batch", batch_no):
			found = frappe.db.get_value("Batch", {"item": row.item_code, "custom_batch_id_all": batch_no}, "name")
			if not found:
				found = frappe.db.get_value("Batch", {"item": row.item_code, "batch_id": batch_no}, "name")
			if found:
				batch_no = found

		key = (row.item_code, batch_no, warehouse)
		req_qty = (flt(row.qty) + flt(row.get("custom_free_qty") or 0.0)) * flt(row.conversion_factor or 1.0)
		requested_map[key] = requested_map.get(key, 0.0) + req_qty
		if key not in row_map:
			row_map[key] = row

	for (item_code, batch_no, warehouse), total_requested in requested_map.items():
		if total_requested <= 0:
			continue

		if batch_no:
			from erpnext.stock.doctype.batch.batch import get_batch_qty
			avail_stock = get_batch_qty(batch_no=batch_no, warehouse=warehouse, item_code=item_code)
			if avail_stock is None:
				avail_stock = flt(frappe.db.get_value("Batch", batch_no, "batch_qty") or 0.0)
			avail_stock = flt(avail_stock)
		else:
			bin_data = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, ["actual_qty", "reserved_qty"], as_dict=True)
			actual_qty = flt(bin_data.actual_qty) if bin_data else 0.0
			reserved_qty = flt(bin_data.reserved_qty) if bin_data else 0.0
			avail_stock = actual_qty - reserved_qty

		other_draft_qty = get_saved_sales_invoice_qty(
			item_code=item_code,
			batch_no=batch_no,
			warehouse=warehouse,
			exclude_invoice=doc.name,
			exclude_doctype=doc.doctype
		)

		effective_available = max(0.0, avail_stock - other_draft_qty)

		if total_requested > effective_available:
			row = row_map[(item_code, batch_no, warehouse)]
			batch_str = f" for Batch {frappe.bold(batch_no)}" if batch_no else ""
			action_verb = "deliver" if doc.doctype == "Delivery Note" else "bill"
			doc_type_label = "Delivery Notes & Sales Invoices"
			msg = _(
				"Row #{0}: Cannot {1} {2} units of Item {3}{4} in Warehouse {5}. "
				"Available quantity is only {6} units (Total stock: {7}, already reserved in other saved {8}: {9})."
			).format(
				row.idx,
				action_verb,
				frappe.bold(total_requested),
				frappe.bold(item_code),
				batch_str,
				frappe.bold(warehouse),
				frappe.bold(effective_available),
				avail_stock,
				doc_type_label,
				other_draft_qty
			)
			frappe.throw(msg, title=_("Insufficient Stock in Saved Documents"))


def update_doc_total_qty(doc, method=None):
	"""
	Ensures Total Quantity on Sales Invoice and Delivery Note includes both billed qty and custom_free_qty.
	"""
	if not doc.get("items"):
		return

	tot_qty = 0.0
	for item in doc.get("items", []):
		tot_qty += flt(item.qty) + flt(item.get("custom_free_qty") or 0.0)

	doc.total_qty = tot_qty
