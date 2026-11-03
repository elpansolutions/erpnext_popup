# Copyright (c) 2026, RRSurgica and contributors
# For license information, please see license.txt

from datetime import datetime, date

import frappe
from frappe import _
from frappe.utils import flt, getdate

from india_compliance.gst_india.utils import (
    get_period,
    validate_gstin_permission,
)
from india_compliance.gst_india.utils.exporter import ExcelExporter
from india_compliance.gst_india.utils.gstr_1 import (
    HSN_BIFURCATION_FROM,
    JSON_CATEGORY_EXCEL_CATEGORY_MAPPING,
    GovJsonKey,
    GSTR1_SubCategory,
)
from india_compliance.gst_india.utils.gstr_1 import GSTR1_DataField as inv_f
from india_compliance.gst_india.utils.gstr_1 import GSTR1_ItemField as item_f
from india_compliance.gst_india.doctype.gstr_1.gstr_1 import get_gstr_1_from_and_to_date
from india_compliance.gst_india.doctype.gstr_1.gstr_1_export import GovExcel
from india_compliance.gst_india.doctype.gst_return_log.generate_gstr_1 import GenerateGSTR1
from india_compliance.gst_india.utils.gstr_1.gstr_1_json_map import GSTR1BooksData


class Gstr1RrsExcel(GovExcel):
    """
    GSTR-1 Excel generator for RRS:
    - Sheet 'b2b,sez,de': Regular B2B rows PLUS invoice-wise B2B exempt/nil-rated rows (Rate = 0).
    - Sheet 'b2cs': Original India Compliance standard format (unchanged).
    - Sheet 'exemp': Excluded from report per auditor requirements.
    - Other sheets (hsn, docs, cdnr, etc.): Original India Compliance format (unchanged).
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

        # 2. Extract invoice-wise B2B exempt/nil-rated invoices for registered persons
        exempt_b2b_invoices = self.extract_exempt_b2b_invoices(raw_books_data)

        # 3. Apply standard India Compliance aggregation
        agg_data = GenerateGSTR1.get_aggregate_data(raw_books_data)
        raw_books_data.update(agg_data)

        # 4. Normalize and process through standard GovExcel pipeline
        norm_data = GenerateGSTR1.normalize_data(dict(raw_books_data))
        self.format_dates_for_gov_excel(norm_data)
        processed_data = self.process_data(norm_data)

        # 5. Merge B2B exempt invoices into b2b sheet data
        b2b_data = processed_data.setdefault(GovJsonKey.B2B.value, [])
        self.append_exempt_to_b2b(b2b_data, exempt_b2b_invoices)

        # 6. Exclude exemp category data
        processed_data.pop(GovJsonKey.NIL_EXEMPT.value, None)

        # 7. Build Excel workbook without exemp sheet
        filename = f"GSTR-1-RRS-{company_gstin}-{self.period}"
        self.build_excel(processed_data, file, filename=filename)

    def build_excel(self, data, file=None, filename=None, sheet_names=None):
        excel = ExcelExporter(file)

        if excel.has_sheet("Sheet"):
            excel.remove_sheet("Sheet")

        # Exclude 'exemp' sheet per auditor requirements
        if excel.has_sheet("exemp"):
            excel.remove_sheet("exemp")

        if sheet_names and excel.is_loaded:
            self._filter_selected_section_sheets(excel, sheet_names)

        for category, cat_data in data.items():
            if category == GovJsonKey.NIL_EXEMPT.value:
                continue

            sheet_name = JSON_CATEGORY_EXCEL_CATEGORY_MAPPING.get(category)
            if not sheet_name or sheet_name == "exemp":
                continue

            if excel.is_loaded and excel.has_sheet(sheet_name):
                excel.insert_data(
                    sheet_name=sheet_name,
                    headers=self.get_category_headers(category),
                    data=cat_data,
                    start_row=5,
                )
            else:
                excel.create_sheet(
                    sheet_name=sheet_name or category,
                    headers=self.get_category_headers(category),
                    data=cat_data,
                    add_totals=False,
                    default_data_format={"height": 15},
                )

        excel.export(filename or f"GSTR-1-RRS-{self.gstin}-{self.period}")

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

    def extract_exempt_b2b_invoices(self, raw_data: dict) -> list:
        nil_raw = raw_data.get(GSTR1_SubCategory.NIL_EXEMPT.value, {})
        exempt_b2b = []

        if isinstance(nil_raw, dict):
            for subcat, inv_list in nil_raw.items():
                if not isinstance(inv_list, list):
                    continue
                if "registered" in subcat.lower() and "unregistered" not in subcat.lower():
                    exempt_b2b.extend(inv_list)

        return exempt_b2b

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


@frappe.whitelist()
@validate_gstin_permission(doctype="GST Return Log")
def download_gstr1_rrs(company_gstin: str, month_or_quarter: str, year: str, company: str | None = None):
    """
    Whitelisted endpoint called from GSTR-1 Form custom button.
    Generates GSTR-1-RRS workbook with invoice-wise exempt items in B2B.
    B2CS and other sheets remain identical to original India Compliance format.
    """
    frappe.has_permission("GSTR-1", "export", throw=True)
    exporter = Gstr1RrsExcel()
    exporter.generate(company_gstin, month_or_quarter, year, company)
