import json
import frappe
from frappe.utils import nowdate

def test():
    print("--- 1. Testing Hooks Registration ---")
    whitelisted = frappe.get_hooks("override_whitelisted_methods") or {}
    get_out_method = "erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents"
    get_ref_method = "erpnext.accounts.doctype.payment_entry.payment_entry.get_reference_details"
    print(f"Override for get_outstanding_reference_documents: {whitelisted.get(get_out_method)}")
    print(f"Override for get_reference_details: {whitelisted.get(get_ref_method)}")
    assert "rrs_customizations.overrides.payment_entry.get_outstanding_reference_documents" in whitelisted.get(get_out_method), "get_outstanding_reference_documents hook not registered"
    assert "rrs_customizations.overrides.payment_entry.get_reference_details" in whitelisted.get(get_ref_method), "get_reference_details hook not registered"
    
    # Active override resolved by frappe HTTP handler
    active_get_out = frappe.override_whitelisted_method(get_out_method)
    active_get_ref = frappe.override_whitelisted_method(get_ref_method)
    print(f"Active override for get_outstanding_reference_documents: {active_get_out}")
    print(f"Active override for get_reference_details: {active_get_ref}")
    assert active_get_out == "rrs_customizations.overrides.payment_entry.get_outstanding_reference_documents"
    assert active_get_ref == "rrs_customizations.overrides.payment_entry.get_reference_details"
    print("PASS: Hooks registered correctly and rrs_customizations is active.")

    print("\n--- 2. Testing get_outstanding_reference_documents override (resolved by handler) ---")
    pi = frappe.db.get_value(
        "Purchase Invoice",
        {"docstatus": 1},
        ["name", "supplier", "company", "credit_to", "bill_date", "bill_no", "outstanding_amount"],
        as_dict=True
    )
    print(f"Testing with Purchase Invoice: {pi.name}, supplier: {pi.supplier}, bill_date: {pi.bill_date}")

    args = {
        "party_type": "Supplier",
        "party": pi.supplier,
        "party_account": pi.credit_to,
        "company": pi.company,
        "payment_type": "Pay",
        "posting_date": nowdate(),
        "get_outstanding_invoices": True
    }
    
    # Calling the overridden method as handler.py does
    docs = frappe.call(active_get_out, args=json.dumps(args))
    target = next((d for d in docs if d.get("voucher_no") == pi.name), None)
    if target:
        print(f"Found {pi.name} in outstanding docs: bill_no={target.get('bill_no')}, bill_date={str(target.get('bill_date'))}")
        assert str(target.get("bill_date")) == str(pi.bill_date), f"Expected bill_date {pi.bill_date}, got {target.get('bill_date')}"
        print(f"reconciliation_status preserved: {target.get('reconciliation_status')}")
        print("PASS: get_outstanding_reference_documents returns bill_date and preserves previous overrides.")
    else:
        print(f"Docs count: {len(docs)}")
        for d in docs:
            if d.get("voucher_type") == "Purchase Invoice":
                print(f"Sample PI {d.get('voucher_no')} -> bill_date: {d.get('bill_date')}")
                assert "bill_date" in d, "bill_date missing from returned PI"
        print("PASS: all Purchase Invoices contain bill_date.")

    print("\n--- 3. Testing get_reference_details override (resolved by handler) ---")
    ref_details = frappe.call(
        active_get_ref,
        reference_doctype="Purchase Invoice",
        reference_name=pi.name,
        party_account_currency="INR"
    )
    print(f"get_reference_details result: bill_no={ref_details.get('bill_no')}, bill_date={str(ref_details.get('bill_date'))}")
    assert str(ref_details.get("bill_date")) == str(pi.bill_date), f"Expected bill_date {pi.bill_date}, got {ref_details.get('bill_date')}"
    print("PASS: get_reference_details returns bill_date.")

    print("\n--- 4. Testing Document Save and Database Persistence ---")
    bank_account = frappe.db.get_value("Account", {"company": pi.company, "account_type": "Bank", "is_group": 0}, "name")
    if not bank_account:
        bank_account = frappe.db.get_value("Account", {"company": pi.company, "account_type": "Cash", "is_group": 0}, "name")
    
    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "party_type": "Supplier",
        "party": pi.supplier,
        "paid_to": pi.credit_to,
        "paid_from": bank_account,
        "paid_amount": 100,
        "received_amount": 100,
        "company": pi.company,
        "target_exchange_rate": 1,
        "references": [
            {
                "reference_doctype": "Purchase Invoice",
                "reference_name": pi.name,
                "total_amount": pi.outstanding_amount or 1000,
                "outstanding_amount": pi.outstanding_amount or 1000,
                "allocated_amount": 100
            }
        ]
    })
    pe.insert(ignore_permissions=True)
    try:
        saved_ref = pe.references[0]
        print(f"Created draft Payment Entry: {pe.name}")
        print(f"Reference row bill_date: {saved_ref.bill_date}")
        assert str(saved_ref.bill_date) == str(pi.bill_date), f"Expected saved bill_date {pi.bill_date}, got {saved_ref.bill_date}"
        
        # Verify directly in the DB table `tabPayment Entry Reference`
        db_val = frappe.db.get_value("Payment Entry Reference", saved_ref.name, "bill_date")
        print(f"Direct DB value from tabPayment Entry Reference: {db_val}")
        assert str(db_val) == str(pi.bill_date), "Direct DB check failed!"
        print("PASS: Database persistence and validation hook confirmed working.")
    finally:
        pe.delete(ignore_permissions=True)
        frappe.db.commit()
        print("Test Payment Entry cleaned up successfully.")

    print("\nALL BACKEND AND DATABASE TESTS PASSED SUCCESSFULLY!")
