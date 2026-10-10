frappe.provide("rrs_customizations");

(function () {
	function get_custom_invoice_indicator(doc, doctype) {
		const dt = doctype || (doc && doc.doctype);
		if (!doc) return;

		if (doc.__unsaved) {
			return [__("Not Saved", null, dt), "orange"];
		}

		const docstatus = doc.docstatus != null ? Number(doc.docstatus) : 0;

		// 1. Cancelled -> purple (distinct from Return which is gray)
		if (docstatus === 2 || doc.status === "Cancelled") {
			return [__("Cancelled", null, dt), "purple", "docstatus,=,2"];
		}

		// 2. Draft -> blue (distinct from Overdue which is red)
		if (docstatus === 0 || doc.status === "Draft") {
			return [__("Draft", null, dt), "blue", "docstatus,=,0"];
		}

		// 3. Purchase Invoice holds & debit notes
		if (dt === "Purchase Invoice") {
			if (doc.status === "Debit Note Issued") {
				return [__(doc.status, null, dt), "gray", "status,=," + doc.status];
			}
			if (Number(doc.outstanding_amount || 0) > 0 && docstatus === 1 && Number(doc.on_hold || 0) === 1) {
				if (!doc.release_date) {
					return [__("On Hold", null, dt), "darkgrey"];
				} else if (frappe.datetime && frappe.datetime.get_diff(doc.release_date, frappe.datetime.nowdate()) > 0) {
					return [__("Temporarily on Hold", null, dt), "darkgrey"];
				}
			}
		}

		// 4. Return / Credit Note -> gray
		if (doc.status === "Return" || doc.status === "Credit Note Issued") {
			return [__(doc.status, null, dt), "gray", "status,=," + doc.status];
		}

		// 5. Normal status colors
		const status_colors = {
			Paid: "green",
			Unpaid: "orange",
			"Unpaid and Discounted": "orange",
			"Partly Paid": "yellow",
			"Partly Paid and Discounted": "yellow",
			Overdue: "red",
			"Overdue and Discounted": "red",
			"Internal Transfer": "darkgrey",
		};

		if (doc.status && status_colors[doc.status]) {
			return [__(doc.status, null, dt), status_colors[doc.status], "status,=," + doc.status];
		}

		if (doc.status) {
			return [__(doc.status, null, dt), frappe.utils ? frappe.utils.guess_colour(doc.status) : "gray", "status,=," + doc.status];
		}

		return null;
	}

	rrs_customizations.get_invoice_status_indicator = get_custom_invoice_indicator;

	function apply_settings() {
		["Sales Invoice", "Purchase Invoice"].forEach(function (doctype) {
			frappe.listview_settings[doctype] = frappe.listview_settings[doctype] || {};
			frappe.listview_settings[doctype].has_indicator_for_draft = true;
			frappe.listview_settings[doctype].has_indicator_for_cancelled = true;
			frappe.listview_settings[doctype].get_indicator = function (doc) {
				return get_custom_invoice_indicator(doc, doctype);
			};
		});

		if (frappe.get_indicator && !frappe.get_indicator.__rrs_patched) {
			const orig = frappe.get_indicator;
			frappe.get_indicator = function (doc, doctype, show_workflow_state) {
				const dt = doctype || (doc && doc.doctype);
				if (dt === "Sales Invoice" || dt === "Purchase Invoice") {
					const custom = get_custom_invoice_indicator(doc, dt);
					if (custom) return custom;
				}
				return orig.apply(this, arguments);
			};
			frappe.get_indicator.__rrs_patched = true;
		}
	}

	apply_settings();
})();
