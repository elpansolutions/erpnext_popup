# Copyright (c) 2026, RRSurgica and contributors
# For license information, please see license.txt

from collections import defaultdict
from datetime import datetime, date
from typing import ClassVar

import frappe
from frappe import _
from frappe.utils import flt, getdate

from india_compliance.gst_india.utils import (
    get_data_file_path,
    get_period,
    validate_gstin_permission,
)
from india_compliance.gst_india.utils.exporter import (
    AMOUNT_FORMAT,
    DATE_FORMAT,
    PERCENT_FORMAT,
    ExcelExporter,
    ExcelWidth,
)
from india_compliance.gst_india.utils.gstr_1 import (
    HSN_BIFURCATION_FROM,
    JSON_CATEGORY_EXCEL_CATEGORY_MAPPING,
    GovExcelSheetName,
    GovJsonKey,
    GSTR1_Category,
    GSTR1_SubCategory,
    HSNKey,
)
from india_compliance.gst_india.utils.gstr_1 import GovExcelField as gov_xl
from india_compliance.gst_india.utils.gstr_1 import GSTR1_DataField as inv_f
from india_compliance.gst_india.utils.gstr_1 import GSTR1_ItemField as item_f
from india_compliance.gst_india.doctype.gstr_1.gstr_1 import get_gstr_1_from_and_to_date
from india_compliance.gst_india.doctype.gstr_1.gstr_1_export import GovExcel
from india_compliance.gst_india.doctype.gst_return_log.generate_gstr_1 import GenerateGSTR1
from india_compliance.gst_india.utils.gstr_1.gstr_1_json_map import GSTR1BooksData


class Gstr1RrsExcel(GovExcel):
    """
    GSTR-1 Excel generator for RRS Auditor.
    - Sheet 'b2b,sez,de': Regular B2B rows PLUS invoice-wise B2B exempt/nil-rated rows (Rate = 0).
    - Sheet 'b2cs': Invoice-wise B2C rows (taxable + exempt/nil-rated with Rate = 0).
    - Other sheets (exemp, hsn, docs, cdnr, etc.) preserved.
    """

    def generate(self, company_gstin: str, month_or_quarter: str, year: str, company: str | None = None):
        self.gstin = company_gstin
        self.month_or_quarter = month_or_quarter
        self.raw_year = year
        self.clean_year = str(year)[:4]
        self.period = get_period(month_or_quarter, self.clean_year)

        month = self.period[:2]
        filing_from = getdate(f"{self.clean_year}-{month}-01")
        is_hsn_bifurcated = filing_from >= HSN_BIFURCATION_FROM
        file_version = "V2.1" if is_hsn_bifurcated else "V2.0"
        file = self.TEMPLATE_EXCEL_FILE.get(file_version)

        # 1. Fetch raw unaggregated Books data
        raw_books_data = self.get_unaggregated_books_data(company_gstin, month_or_quarter, self.clean_year, company)

        # 2. Extract invoice-wise nil/exempt items (registered -> B2B, unregistered -> B2C)
        exempt_b2b_invoices, exempt_b2c_invoices = self.extract_exempt_invoices(raw_books_data)

        # 3. Extract unaggregated B2CS invoices
        b2cs_invoice_list = self.extract_b2cs_invoices(raw_books_data)

        # 4. Normalize and process through standard GovExcel pipeline
        norm_data = GenerateGSTR1.normalize_data(dict(raw_books_data))
        self.format_dates_for_gov_excel(norm_data)
        processed_data = self.process_data(norm_data)

        # 5. Merge B2B exempt invoices into b2b sheet data
        b2b_data = processed_data.setdefault(GovJsonKey.B2B.value, [])
        self.append_exempt_to_b2b(b2b_data, exempt_b2b_invoices)

        # 6. Format B2CS sheet as invoice-wise (taxable + exempt)
        b2cs_combined_data = self.build_invoice_wise_b2cs(b2cs_invoice_list, exempt_b2c_invoices)

        # 7. Aggregate 'exemp' summary rows cleanly by supply category
        self.aggregate_nil_exempt_summary(processed_data)

        # 8. Build Excel workbook
        filename = f"GSTR-1-RRS-{company_gstin}-{self.period}"
        self.build_rrs_excel(processed_data, b2cs_combined_data, file, filename)

    def aggregate_nil_exempt_summary(self, processed_data: dict):
        nil_category = GovJsonKey.NIL_EXEMPT.value
        raw_rows = processed_data.get(nil_category, [])
        if not raw_rows:
            return

        aggregated = {}
        for row in raw_rows:
            desc = row.get(inv_f.DOC_TYPE)
            if not desc:
                continue
            if desc not in aggregated:
                aggregated[desc] = {
                    inv_f.DOC_TYPE: desc,
                    inv_f.NIL_RATED_AMOUNT: 0,
                    inv_f.EXEMPTED_AMOUNT: 0,
                    inv_f.NON_GST_AMOUNT: 0,
                }
            aggregated[desc][inv_f.NIL_RATED_AMOUNT] += flt(row.get(inv_f.NIL_RATED_AMOUNT, 0))
            aggregated[desc][inv_f.EXEMPTED_AMOUNT] += flt(row.get(inv_f.EXEMPTED_AMOUNT, 0))
            aggregated[desc][inv_f.NON_GST_AMOUNT] += flt(row.get(inv_f.NON_GST_AMOUNT, 0))

        processed_data[nil_category] = list(aggregated.values())

    def get_unaggregated_books_data(self, company_gstin: str, month_or_quarter: str, year: str, company: str | None = None) -> dict:
        log_name = f"GSTR1-{self.period}-{company_gstin}"
        filing_preference = "Monthly"
        if frappe.db.exists("GST Return Log", log_name):
            filing_preference = frappe.db.get_value("GST Return Log", log_name, "filing_preference") or "Monthly"

        if not company:
            company = frappe.db.get_value("Address", {"gstin": company_gstin, "is_your_company_address": 1}, "company")
            if not company:
                company = frappe.defaults.get_user_default("Company") or "RRSurgica"

        from_date, to_date = get_gstr_1_from_and_to_date(month_or_quarter, year, filing_preference)
        filters = frappe._dict({
            "company": company,
            "company_gstin": company_gstin,
            "month_or_quarter": month_or_quarter,
            "year": year,
            "period": self.period,
            "from_date": from_date,
            "to_date": to_date,
            "filing_preference": filing_preference,
        })
        return GSTR1BooksData(filters).prepare_mapped_data()

    def extract_exempt_invoices(self, raw_data: dict) -> tuple[list, list]:
        nil_raw = raw_data.get(GSTR1_SubCategory.NIL_EXEMPT.value, {})
        exempt_b2b = []
        exempt_b2c = []

        if isinstance(nil_raw, dict):
            for subcat, inv_list in nil_raw.items():
                if not isinstance(inv_list, list):
                    continue
                if "registered" in subcat.lower() and "unregistered" not in subcat.lower():
                    exempt_b2b.extend(inv_list)
                else:
                    exempt_b2c.extend(inv_list)

        return exempt_b2b, exempt_b2c

    def extract_b2cs_invoices(self, raw_data: dict) -> list:
        b2cs_raw = raw_data.get(GSTR1_Category.B2CS.value, {})
        invoices = []
        if isinstance(b2cs_raw, dict):
            for group_key, inv_list in b2cs_raw.items():
                if isinstance(inv_list, list):
                    invoices.extend(inv_list)
        elif isinstance(b2cs_raw, list):
            invoices.extend(b2cs_raw)
        return invoices

    def format_dates_for_gov_excel(self, data: dict):
        for cat, doc_list in data.items():
            if isinstance(doc_list, list):
                for doc in doc_list:
                    if isinstance(doc, dict):
                        if isinstance(doc.get("document_date"), (date, datetime)):
                            doc["document_date"] = doc["document_date"].strftime("%Y-%m-%d")
                        if "items" in doc and isinstance(doc["items"], list):
                            for it in doc["items"]:
                                if isinstance(it.get("document_date"), (date, datetime)):
                                    it["document_date"] = it["document_date"].strftime("%Y-%m-%d")

    def parse_doc_date(self, val):
        if isinstance(val, (date, datetime)):
            return datetime(val.year, val.month, val.day)
        if isinstance(val, str) and val:
            try:
                return datetime.strptime(val[:10], "%Y-%m-%d")
            except Exception:
                return val
        return val

    def append_exempt_to_b2b(self, b2b_data: list, exempt_b2b_invoices: list):
        for inv in exempt_b2b_invoices:
            taxable_val = inv.get("exempted_amount") or inv.get("nil_rated_amount") or inv.get("total_taxable_value", 0)
            b2b_data.append({
                inv_f.CUST_GSTIN: inv.get("customer_gstin"),
                inv_f.CUST_NAME: inv.get("customer_name"),
                inv_f.DOC_NUMBER: inv.get("document_number"),
                inv_f.DOC_DATE: self.parse_doc_date(inv.get("document_date")),
                inv_f.DOC_VALUE: inv.get("document_value"),
                inv_f.POS: inv.get("place_of_supply"),
                inv_f.REVERSE_CHARGE: inv.get("reverse_charge") or "N",
                inv_f.DIFF_PERCENTAGE: None,
                inv_f.DOC_TYPE: "Regular B2B",
                inv_f.ECOMMERCE_GSTIN: inv.get("ecommerce_gstin"),
                item_f.TAX_RATE: 0,
                item_f.TAXABLE_VALUE: taxable_val,
                item_f.CESS: 0,
            })

    def build_invoice_wise_b2cs(self, taxable_invoices: list, exempt_invoices: list) -> list:
        b2cs_rows = []

        # 1. Taxable B2C invoices
        for doc in taxable_invoices:
            tax_rate = doc.get("tax_rate", 0)
            taxable_val = doc.get("total_taxable_value", 0)
            cess_val = doc.get("total_cess_amount", 0)
            b2cs_rows.append({
                "receiver_name": doc.get("customer_name"),
                "invoice_number": doc.get("document_number"),
                "invoice_date": self.parse_doc_date(doc.get("document_date")),
                "invoice_value": doc.get("document_value"),
                "pos": doc.get("place_of_supply"),
                "diff_percentage": doc.get("diff_percentage"),
                "type": doc.get("document_type") or "OE",
                "ecommerce_gstin": doc.get("ecommerce_gstin"),
                "rate": tax_rate,
                "taxable_value": taxable_val,
                "cess_amount": cess_val,
            })

        # 2. Exempt B2C invoices
        for inv in exempt_invoices:
            taxable_val = inv.get("exempted_amount") or inv.get("nil_rated_amount") or inv.get("total_taxable_value", 0)
            b2cs_rows.append({
                "receiver_name": inv.get("customer_name"),
                "invoice_number": inv.get("document_number"),
                "invoice_date": self.parse_doc_date(inv.get("document_date")),
                "invoice_value": inv.get("document_value"),
                "pos": inv.get("place_of_supply"),
                "diff_percentage": None,
                "type": "OE",
                "ecommerce_gstin": inv.get("ecommerce_gstin"),
                "rate": 0,
                "taxable_value": taxable_val,
                "cess_amount": 0,
            })

        return b2cs_rows

    def get_b2cs_invoice_wise_headers(self) -> list:
        return [
            {
                "label": _("Receiver Name"),
                "fieldname": "receiver_name",
                "header_format": {"width": ExcelWidth.XXL.value},
            },
            {
                "label": _("Invoice Number"),
                "fieldname": "invoice_number",
                "header_format": {"width": ExcelWidth.SM.value},
            },
            {
                "label": _("Invoice date"),
                "fieldname": "invoice_date",
                "data_format": {"number_format": self.DATE_FORMAT},
                "header_format": {"width": ExcelWidth.XS.value},
            },
            {
                "label": _("Invoice Value"),
                "fieldname": "invoice_value",
                "data_format": {"number_format": self.AMOUNT_FORMAT},
            },
            {
                "label": _(gov_xl.POS),
                "fieldname": "pos",
            },
            {
                "label": _(gov_xl.DIFF_PERCENTAGE),
                "fieldname": "diff_percentage",
                "data_format": {"number_format": self.PERCENT_FORMAT},
                "header_format": {"width": ExcelWidth.XS.value},
            },
            {
                "label": _("Type"),
                "fieldname": "type",
            },
            {
                "label": _(gov_xl.ECOMMERCE_GSTIN),
                "fieldname": "ecommerce_gstin",
                "header_format": {"width": ExcelWidth.SM.value},
            },
            {
                "label": _(gov_xl.TAX_RATE),
                "fieldname": "rate",
                "data_format": {"number_format": self.PERCENT_FORMAT},
                "header_format": {"width": ExcelWidth.XS.value},
            },
            {
                "label": _(gov_xl.TAXABLE_VALUE),
                "fieldname": "taxable_value",
                "data_format": {"number_format": self.AMOUNT_FORMAT},
            },
            {
                "label": _(gov_xl.CESS),
                "fieldname": "cess_amount",
                "data_format": {"number_format": self.AMOUNT_FORMAT},
            },
        ]

    def build_rrs_excel(self, data: dict, b2cs_data: list, file: str, filename: str):
        excel = ExcelExporter(file)

        if excel.has_sheet("Sheet"):
            excel.remove_sheet("Sheet")

        # 1. Populate all sheets except b2cs using standard mapping
        for category, cat_data in data.items():
            if category == GovJsonKey.B2CS.value:
                continue

            sheet_name = JSON_CATEGORY_EXCEL_CATEGORY_MAPPING.get(category)
            if not sheet_name or not excel.has_sheet(sheet_name):
                continue

            excel.insert_data(
                sheet_name=sheet_name,
                headers=self.get_category_headers(category),
                data=cat_data,
                start_row=5,
            )

        # 2. Populate b2cs with invoice-wise rows and custom headers
        if excel.has_sheet("b2cs"):
            b2cs_sheet = excel.wb["b2cs"]
            headers = self.get_b2cs_invoice_wise_headers()
            # Update row 4 headers
            for col_idx, h in enumerate(headers, 1):
                b2cs_sheet.cell(row=4, column=col_idx, value=h["label"])

            # Insert invoice-wise rows
            excel.insert_data(
                sheet_name="b2cs",
                headers=headers,
                data=b2cs_data,
                start_row=5,
            )

        excel.export(filename)


@frappe.whitelist()
@validate_gstin_permission(doctype="GST Return Log")
def download_gstr1_rrs(company_gstin: str, month_or_quarter: str, year: str, company: str | None = None):
    """
    Whitelisted endpoint called from GSTR-1 Form custom button.
    Generates GSTR-1-RRS workbook with invoice-wise exempt items in B2B and B2CS.
    """
    frappe.has_permission("GSTR-1", "export", throw=True)
    exporter = Gstr1RrsExcel()
    exporter.generate(company_gstin, month_or_quarter, year, company)
