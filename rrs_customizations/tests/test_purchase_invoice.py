# Copyright (c) 2026, RRSurgica and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, flt
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from rrs_customizations.overrides.purchase_invoice import RRSPurchaseInvoice


class TestRRSPurchaseInvoice(FrappeTestCase):
	def setUp(self):
		frappe.flags.ignore_account_permission = True
		self.company = "RRSurgica"
		self.warehouse = "Stores - RRS"
		self.supplier = "_Test Supplier RRS"
		self.item_code = "_Test Stock Item RRS"

		self.ensure_test_prerequisites()
		frappe.local.message_log = []

	def tearDown(self):
		frappe.local.message_log = []

	def ensure_test_prerequisites(self):
		# Ensure test supplier exists for RRSurgica
		if not frappe.db.exists("Supplier", self.supplier):
			sup = frappe.new_doc("Supplier")
			sup.supplier_name = self.supplier
			sup.supplier_group = "All Supplier Groups"
			sup.supplier_type = "Company"
			sup.insert(ignore_permissions=True)

		# Ensure test stock item exists
		if not frappe.db.exists("Item", self.item_code):
			item = frappe.new_doc("Item")
			item.item_code = self.item_code
			item.item_name = self.item_code
			item.item_group = "All Item Groups"
			item.is_stock_item = 1
			item.stock_uom = "Nos"
			item.valuation_rate = 100.0
			item.gst_hsn_code = "01011010"
			item.insert(ignore_permissions=True)

		self.cogs_account = frappe.db.get_value(
			"Account",
			{"account_name": "Cost of Goods Sold", "company": self.company},
			"name",
		) or "Cost of Goods Sold - RRS"

		self.stock_in_hand = frappe.db.get_value(
			"Account",
			{"account_name": "Stock In Hand", "company": self.company},
			"name",
		) or "Stock In Hand - RRS"

		self.stock_received_but_not_billed = frappe.db.get_value(
			"Account",
			{"account_name": "Stock Received But Not Billed", "company": self.company},
			"name",
		) or "Stock Received But Not Billed - RRS"

	def _has_expense_head_changed_message(self):
		messages = frappe.get_message_log()
		for msg in messages:
			if isinstance(msg, dict):
				title = msg.get("title") or ""
				message = msg.get("message") or ""
				if "Expense Head Changed" in title or "Expense Head changed" in message:
					return True
			elif isinstance(msg, str) and ("Expense Head Changed" in msg or "Expense Head changed" in msg):
				return True
		return False

	def test_controller_override(self):
		"""Verify that Purchase Invoice resolves to the RRSPurchaseInvoice subclass."""
		pi = frappe.new_doc("Purchase Invoice")
		self.assertIsInstance(pi, RRSPurchaseInvoice)
		self.assertIsInstance(pi, PurchaseInvoice)

	def test_1_direct_stock_purchase_invoice(self):
		"""
		Test 1: Direct stock Purchase Invoice (Update Stock = 1)
		- Stock item, update_stock=1, no Purchase Receipt
		- Expense Head initially set to COGS
		- ERPNext changes it to Stock In Hand
		- No 'Expense Head Changed' informational message is produced
		- Stock Ledger Entry and GL Entry remain correct
		"""
		frappe.local.message_log = []
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = self.supplier
		pi.posting_date = today()
		pi.update_stock = 1
		pi.append(
			"items",
			{
				"item_code": self.item_code,
				"qty": 2,
				"rate": 150.0,
				"warehouse": self.warehouse,
				"expense_account": self.cogs_account,
			},
		)

		pi.save()
		# Validate expense account was corrected to Stock In Hand without popup
		self.assertEqual(pi.items[0].expense_account, self.stock_in_hand)
		self.assertFalse(self._has_expense_head_changed_message())

		pi.submit()
		self.assertFalse(self._has_expense_head_changed_message())

		# Verify Stock Ledger Entry
		sle = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_type": "Purchase Invoice", "voucher_no": pi.name, "is_cancelled": 0},
			["actual_qty", "warehouse", "stock_value_difference"],
			as_dict=1,
		)
		self.assertIsNotNone(sle)
		self.assertEqual(flt(sle.actual_qty), 2.0)
		self.assertEqual(sle.warehouse, self.warehouse)
		self.assertEqual(flt(sle.stock_value_difference), 300.0)

		# Verify GL Entries
		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Purchase Invoice", "voucher_no": pi.name, "is_cancelled": 0},
			fields=["account", "debit", "credit"],
		)
		debit_accounts = {gle.account: flt(gle.debit) for gle in gl_entries if flt(gle.debit) > 0}
		self.assertIn(self.stock_in_hand, debit_accounts)
		self.assertEqual(debit_accounts[self.stock_in_hand], 300.0)

	def test_2_invoice_before_receipt(self):
		"""
		Test 2: Invoice before receipt (Update Stock = 0)
		- Stock item, update_stock=0, no Purchase Receipt
		- ERPNext selects Stock Received But Not Billed
		- No 'Expense Head Changed' informational message is produced
		- GL posting remains correct
		"""
		frappe.local.message_log = []
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = self.supplier
		pi.posting_date = today()
		pi.update_stock = 0
		pi.append(
			"items",
			{
				"item_code": self.item_code,
				"qty": 3,
				"rate": 200.0,
				"warehouse": self.warehouse,
				"expense_account": self.cogs_account,
			},
		)

		pi.save()
		# Validate expense account resolved to Stock Received But Not Billed without popup
		self.assertEqual(pi.items[0].expense_account, self.stock_received_but_not_billed)
		self.assertFalse(self._has_expense_head_changed_message())

		pi.submit()
		self.assertFalse(self._has_expense_head_changed_message())

		# Verify GL Entries (Debit Stock Received But Not Billed)
		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Purchase Invoice", "voucher_no": pi.name, "is_cancelled": 0},
			fields=["account", "debit", "credit"],
		)
		debit_accounts = {gle.account: flt(gle.debit) for gle in gl_entries if flt(gle.debit) > 0}
		self.assertIn(self.stock_received_but_not_billed, debit_accounts)
		self.assertEqual(debit_accounts[self.stock_received_but_not_billed], 600.0)

	def test_3_invoice_against_purchase_receipt(self):
		"""
		Test 3: Invoice against Purchase Receipt
		- Purchase Receipt exists
		- Purchase Invoice is created from the Purchase Receipt
		- Reconciliation account remains correct
		- No accounting logic is altered
		"""
		frappe.local.message_log = []
		# 1. Create and submit Purchase Receipt
		pr = frappe.new_doc("Purchase Receipt")
		pr.company = self.company
		pr.supplier = self.supplier
		pr.posting_date = today()
		pr.append(
			"items",
			{
				"item_code": self.item_code,
				"qty": 4,
				"rate": 250.0,
				"warehouse": self.warehouse,
			},
		)
		pr.save()
		pr.submit()

		# 2. Create Purchase Invoice from Purchase Receipt
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
			make_purchase_invoice as make_pi_from_pr,
		)

		pi = make_pi_from_pr(pr.name)
		pi.save()
		self.assertEqual(pi.items[0].expense_account, self.stock_received_but_not_billed)
		self.assertFalse(self._has_expense_head_changed_message())

		pi.submit()
		self.assertFalse(self._has_expense_head_changed_message())

		# Verify GL Entries for PI
		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Purchase Invoice", "voucher_no": pi.name, "is_cancelled": 0},
			fields=["account", "debit", "credit"],
		)
		debit_accounts = {gle.account: flt(gle.debit) for gle in gl_entries if flt(gle.debit) > 0}
		self.assertIn(self.stock_received_but_not_billed, debit_accounts)
		self.assertEqual(debit_accounts[self.stock_received_but_not_billed], 1000.0)

	def test_4_unrelated_purchase_invoice_validation(self):
		"""
		Test 4: Unrelated Purchase Invoice validation
		- Trigger an unrelated validation failure (e.g. missing item_code)
		- Confirm it is still raised / displayed and not suppressed.
		"""
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = self.supplier
		pi.posting_date = today()
		pi.append(
			"items",
			{
				"item_code": "",  # Missing item_code triggers Item Code required error
				"qty": 1,
				"rate": 100.0,
			},
		)

		with self.assertRaises(frappe.exceptions.ValidationError):
			pi.save()

	def test_5_other_doctypes_unaffected(self):
		"""
		Test 5: Other DocTypes
		- Confirm Sales Invoice and Purchase Receipt use standard controllers and are unaffected.
		"""
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt

		si = frappe.new_doc("Sales Invoice")
		self.assertIsInstance(si, SalesInvoice)
		self.assertNotIsInstance(si, RRSPurchaseInvoice)

		pr = frappe.new_doc("Purchase Receipt")
		self.assertIsInstance(pr, PurchaseReceipt)
		self.assertNotIsInstance(pr, RRSPurchaseInvoice)
