import base64
import os
import re
import frappe
from frappe import _
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
	Automatically generates and stores/attaches the Sales Invoice PDF
	into ERPNext Attachments with the invoice number (doc.name) as the file name.

	- Works in both Dev and Prod naming conventions (uses doc.name dynamically).
	- Dynamically detects the default or configured print format.
	- Inlines images as base64 for 100% reliable offline PDF rendering.
	- Generates in Landscape A4 format so all tables fit perfectly.
	- Runs server-side on submission without interfering with client scripts.
	"""
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	if doc.docstatus != 1:
		return

	file_name = f"{doc.name}.pdf"

	# Avoid duplicate attachments
	if frappe.db.exists(
		"File",
		{
			"attached_to_doctype": "Sales Invoice",
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
				{"doc_type": "Sales Invoice", "property": "default_print_format"},
				"value",
			)
			or frappe.get_meta("Sales Invoice").default_print_format
			or "v5"
		)

		html = frappe.get_print(
			doctype="Sales Invoice",
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
				"attached_to_doctype": "Sales Invoice",
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



