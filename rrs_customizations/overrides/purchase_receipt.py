# Copyright (c) 2026, RRSurgica and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


class RRSPurchaseReceipt(PurchaseReceipt):
	"""
	Custom Purchase Receipt controller for RRSurgica.
	Includes custom_free_qty into batch bundle details and stock ledger entries,
	ensuring received free / bonus stock is physically booked in inventory and
	valuation rate is adjusted appropriately.
	"""

	def update_bundle_details(self, bundle_details, table_name, row, is_rejected=False, parent_details=None):
		super().update_bundle_details(bundle_details, table_name, row, is_rejected, parent_details)
		free_q = flt(row.get("custom_free_qty") or 0.0)
		if free_q > 0:
			tot_qty = (flt(row.qty) + free_q) * flt(row.conversion_factor or 1.0)
			bundle_details["qty"] = tot_qty
			if bundle_details.get("batches") and row.batch_no:
				bundle_details["batches"][row.batch_no] = tot_qty

	def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
		saved = {}
		for d in self.get("items"):
			free_q = flt(d.get("custom_free_qty") or 0.0)
			if free_q > 0:
				tot_q = flt(d.qty) + free_q
				saved[d.name] = (d.qty, d.stock_qty, d.valuation_rate)
				d.qty = tot_q
				d.stock_qty = tot_q * flt(d.conversion_factor or 1.0)
				net_amt = flt(d.base_net_amount or (flt(saved[d.name][0]) * flt(d.rate)))
				d.valuation_rate = net_amt / d.stock_qty if d.stock_qty else d.valuation_rate
		try:
			return super().update_stock_ledger(allow_negative_stock, via_landed_cost_voucher)
		finally:
			for d in self.get("items"):
				if d.name in saved:
					d.qty, d.stock_qty, d.valuation_rate = saved[d.name]
