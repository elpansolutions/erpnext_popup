# RRS Customizations (`rrs_customizations`)

A dedicated Frappe/ERPNext application to suppress specific informational **"Expense Head Changed"** popups on Purchase Invoice while strictly preserving all underlying accounting logic, General Ledger postings, Stock Ledger entries, inventory valuation, and error validations.

---

## Features

- **Suppresses Informational Popups**:
  - `Expense Head changed to [Warehouse Account] because account [COGS] is not linked to warehouse...`
  - `Expense Head changed to Stock Received But Not Billed as no Purchase Receipt is created against Item...`
- **100% Unaltered Accounting & Stock**:
  - Automatically determinations and assignments for Expense Head continue as standard.
  - GL Entries and Stock Ledger Entries are posted exactly as designed by ERPNext.
  - All critical errors (missing accounts, mandatory field errors, validation errors) remain fully operational.

---

## Installation & Setup on Other Sites

Follow these steps to install and enable `rrs_customizations` on any Frappe Bench and site:

### 1. Fetch the App

From your bench directory:

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/elpansolutions/erpnext_popup.git --branch version-16
```

### 2. Install on Your Site

Install the application onto your target site:

```bash
bench --site <your-site-name> install-app rrs_customizations
```

### 3. Run Migrations & Build Assets

```bash
bench --site <your-site-name> migrate
bench build --app rrs_customizations
bench --site <your-site-name> clear-cache
```

### 4. Restart Bench Services

```bash
bench restart
```

---

## Running Automated Tests

To run the automated test suite for this app on your site:

```bash
bench --site <your-site-name> run-tests --app rrs_customizations
```

---

## License

MIT License. See [license.txt](license.txt) for details.
