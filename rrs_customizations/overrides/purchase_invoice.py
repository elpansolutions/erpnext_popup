# Copyright (c) 2026, RRSurgica and contributors
# For license information, please see license.txt

import erpnext
import frappe
from frappe import _, throw
from frappe.utils import get_link_to_form
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from erpnext.assets.doctype.asset.asset import is_cwip_accounting_enabled
from erpnext.assets.doctype.asset_category.asset_category import get_asset_category_account


class RRSPurchaseInvoice(PurchaseInvoice):
	"""
	Custom Purchase Invoice controller for RRSurgica.

	Upstream Reference:
	- App: ERPNext (version 16.32.1)
	- File: apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py
	- Class: PurchaseInvoice
	- Method: set_expense_account(self, for_validate=False)

	Customization Rationale:
	- In standard ERPNext, when saving a Purchase Invoice containing stock items under perpetual inventory,
	  informational popups (msgprint) with title "Expense Head Changed" are triggered whenever the system
	  automatically sets the correct expense account (e.g., Stock In Hand or Stock Received But Not Billed).
	- This subclass suppresses only those informational popups while strictly preserving the entire account
	  determination logic, stock ledger entry calculations, general ledger entry postings, perpetual inventory,
	  mandatory field validations, and error exceptions.

	Upgrade Note:
	- If upgrading ERPNext, review `erpnext.accounts.doctype.purchase_invoice.purchase_invoice.PurchaseInvoice.set_expense_account`
	  to verify if any new account resolution logic or parameters were added in newer versions.
	"""

	def set_expense_account(self, for_validate=False):
		auto_accounting_for_stock = erpnext.is_perpetual_inventory_enabled(self.company)

		if auto_accounting_for_stock:
			stock_not_billed_account = self.get_company_default("stock_received_but_not_billed")
			stock_items = self.get_stock_items()

		self.asset_received_but_not_billed = None

		inventory_account_map = {}
		if self.update_stock:
			self.validate_item_code()
			self.validate_warehouse(for_validate)
			if auto_accounting_for_stock:
				inventory_account_map = self.get_inventory_account_map()

		for item in self.get("items"):
			# in case of auto inventory accounting,
			# expense account is always "Stock Received But Not Billed" for a stock item
			# except opening entry, drop-ship entry and fixed asset items
			if (
				auto_accounting_for_stock
				and item.item_code in stock_items
				and self.is_opening == "No"
				and not item.is_fixed_asset
				and (
					not item.po_detail
					or not frappe.db.get_value("Purchase Order Item", item.po_detail, "delivered_by_supplier")
				)
			):
				if self.update_stock and item.warehouse and (not item.from_warehouse):
					_inv_dict = self.get_inventory_account_dict(item, inventory_account_map)

					# Suppress informational msgprint for:
					# "Row {0}: Expense Head changed to {1} because account {2} is not linked to warehouse {3} or it is not the default inventory account"
					item.expense_account = _inv_dict["account"]
				else:
					# check if 'Stock Received But Not Billed' account is credited in Purchase receipt or not
					if item.purchase_receipt:
						negative_expense_booked_in_pr = frappe.db.sql(
							"""select name from `tabGL Entry`
							where voucher_type='Purchase Receipt' and voucher_no=%s and account = %s""",
							(item.purchase_receipt, stock_not_billed_account),
						)

						if negative_expense_booked_in_pr:
							if (
								for_validate
								and item.expense_account
								and item.expense_account != stock_not_billed_account
							):
								msg = _(
									"Row {0}: Expense Head changed to {1} because expense is booked against this account in Purchase Receipt {2}"
								).format(
									item.idx,
									frappe.bold(stock_not_billed_account),
									frappe.bold(item.purchase_receipt),
								)
								frappe.msgprint(msg, title=_("Expense Head Changed"))

							item.expense_account = stock_not_billed_account
					else:
						# If no purchase receipt present then book expense in 'Stock Received But Not Billed'
						# This is done in cases when Purchase Invoice is created before Purchase Receipt
						# Suppress informational msgprint for:
						# "Row {0}: Expense Head changed to {1} as no Purchase Receipt is created against Item {2}..."
						item.expense_account = stock_not_billed_account
			elif item.is_fixed_asset:
				account = None
				if not item.pr_detail and item.po_detail:
					receipt_item = frappe.get_cached_value(
						"Purchase Receipt Item",
						{
							"purchase_order": item.purchase_order,
							"purchase_order_item": item.po_detail,
							"docstatus": 1,
						},
						["name", "parent"],
						as_dict=1,
					)
					if receipt_item:
						item.pr_detail = receipt_item.name
						item.purchase_receipt = receipt_item.parent

				if item.pr_detail:
					if not self.asset_received_but_not_billed:
						self.asset_received_but_not_billed = self.get_company_default(
							"asset_received_but_not_billed"
						)

					# check if 'Asset Received But Not Billed' account is credited in Purchase receipt or not
					arbnb_booked_in_pr = frappe.db.get_value(
						"GL Entry",
						{
							"voucher_type": "Purchase Receipt",
							"voucher_no": item.purchase_receipt,
							"account": self.asset_received_but_not_billed,
						},
						"name",
					)
					if arbnb_booked_in_pr:
						account = self.asset_received_but_not_billed

				if not account:
					account_type = (
						"capital_work_in_progress_account"
						if is_cwip_accounting_enabled(item.asset_category)
						else "fixed_asset_account"
					)
					account = get_asset_category_account(
						account_type, item=item.item_code, company=self.company
					)
					if not account:
						form_link = get_link_to_form("Asset Category", item.asset_category)
						throw(
							_("Please set Fixed Asset Account in {} against {}.").format(
								form_link, self.company
							),
							title=_("Missing Account"),
						)
				item.expense_account = account
			elif not item.expense_account and for_validate:
				throw(_("Expense account is mandatory for item {0}").format(item.item_code or item.item_name))
