# RRS Customizations (`rrs_customizations`)

A custom Frappe & ERPNext application for **RRSurgica** designed to streamline invoice workflows, eliminate disruptive submit popups, automate invoice PDF generation, and optimize document printing.

---

## Key Features

### 1. Direct 1-Click Invoice Submission
- **Bypasses Submit Confirmation Modal**:
  - Eliminates the blocking *"Permanently Submit {docname}?"* popup on both **Purchase Invoice** and **Sales Invoice** forms.
  - Submits immediately on click while strictly preserving all standard lifecycle hooks (`before_submit`, validations, mandatory field checks, and `on_submit`).

### 2. Informational Popup Suppression
- **Suppresses "Expense Head Changed" Popups on Purchase Invoices**:
  - `Expense Head changed to [Warehouse Account] because account [COGS] is not linked to warehouse...`
  - `Expense Head changed to Stock Received But Not Billed as no Purchase Receipt is created against Item...`
- **100% Unaltered Accounting & Stock**:
  - Automatic determination and assignments for Expense Head continue as standard.
  - General Ledger (GL) and Stock Ledger (SLE) entries post exactly as designed by ERPNext.
  - All critical errors (missing accounts, validation failures) remain fully operational.

### 3. Automated Sales Invoice PDF Generation
- **Auto-Attach on Submission**:
  - Automatically generates and attaches the invoice PDF (`{doc.name}.pdf`) directly to the document attachments on submission.
  - Inlines all assets (images converted to Base64, stylesheets bundled directly) for 100% reliable, self-contained offline rendering.
  - Defaults to **A4 Landscape** format to ensure wide item tables render with full column clarity without truncation.

### 4. High-Quality Landscape PDF Download
- Overrides `download_pdf` to render fully self-contained HTML and produce clean, edge-to-edge landscape PDFs.

---

## Upgrading the App on Existing Sites

When new features or fixes are pushed to the repository, follow these steps to update your bench and site:

### Step 1: Pull the Latest Changes
From your `frappe-bench` directory:

```bash
cd /path/to/frappe-bench/apps/rrs_customizations
git pull origin version-16
```

### Step 2: Build Assets
Recompile the client-side JavaScript assets:

```bash
cd /path/to/frappe-bench
bench build --app rrs_customizations
```

### Step 3: Run Migrations & Clear Cache
Apply schema updates and clear site caches:

```bash
bench --site <your-site-name> migrate
bench --site <your-site-name> clear-cache
```

### Step 4: Restart Bench Services
Restart the bench supervisor / workers to ensure all backend changes take effect:

```bash
bench restart
```

---

## Fresh Installation & Setup

To install `rrs_customizations` on a new Frappe Bench environment:

### 1. Fetch the App
```bash
cd /path/to/frappe-bench
bench get-app https://github.com/elpansolutions/erpnext_popup.git --branch version-16
```

### 2. Install on Your Site
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

To run the automated test suite for this app:

```bash
bench --site <your-site-name> run-tests --app rrs_customizations
```

---

## License

MIT License. See [license.txt](license.txt) for details.
