frappe.provide("rrs_customizations");

(function () {
	["Sales Invoice", "Purchase Invoice"].forEach(function (doctype) {
		frappe.listview_settings[doctype] = frappe.listview_settings[doctype] || {};
		frappe.listview_settings[doctype].has_indicator_for_draft = true;
		frappe.listview_settings[doctype].has_indicator_for_cancelled = true;

		if (rrs_customizations.get_invoice_status_indicator) {
			const existing_get_indicator = frappe.listview_settings[doctype].get_indicator;
			frappe.listview_settings[doctype].get_indicator = function (doc) {
				return (
					rrs_customizations.get_invoice_status_indicator(doc, doctype) ||
					(existing_get_indicator ? existing_get_indicator(doc) : null)
				);
			};
		}
	});
})();
