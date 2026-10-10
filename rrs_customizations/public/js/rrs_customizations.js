frappe.provide("rrs_customizations");

(function () {
	const original_savesubmit = frappe.ui.form.Form.prototype.savesubmit;
	const bypass_confirm_doctypes = ["Purchase Invoice", "Sales Invoice"];

	frappe.ui.form.Form.prototype.savesubmit = function (btn, callback, on_error) {
		const me = this;

		if (bypass_confirm_doctypes.includes(this.doctype)) {
			return new Promise((resolve) => {
				this.validate_form_action("Submit");
				frappe.validated = true;
				me.script_manager.trigger("before_submit").then(function () {
					if (!frappe.validated) {
						return me.handle_save_fail(btn, on_error);
					}

					me.save(
						"Submit",
						function (r) {
							if (r.exc) {
								me.handle_save_fail(btn, on_error);
							} else {
								frappe.utils.play_sound("submit");
								callback && callback();
								me.script_manager
									.trigger("on_submit")
									.then(() => resolve(me))
									.then(() => {
										if (frappe.route_hooks.after_submit) {
											let route_callback = frappe.route_hooks.after_submit;
											delete frappe.route_hooks.after_submit;
											route_callback(me);
										}
									});
							}
						},
						btn,
						on_error,
						true
					);
				});
			});
		}

		return original_savesubmit.call(this, btn, callback, on_error);
	};
})();

// Status Indicator Colors for Sales Invoice and Purchase Invoice
(function () {
	function get_invoice_status_indicator(doc, doctype) {
		const dt = doctype || (doc && doc.doctype);
		if (!doc || !dt || (dt !== "Sales Invoice" && dt !== "Purchase Invoice")) {
			return null;
		}

		if (doc.__unsaved) {
			return [__("Not Saved", null, dt), "orange"];
		}

		const docstatus = doc.docstatus != null ? Number(doc.docstatus) : 0;

		// 1. Cancelled -> darkgrey
		if (docstatus === 2 || doc.status === "Cancelled") {
			return [__("Cancelled", null, dt), "darkgrey", "docstatus,=,2"];
		}

		// 2. Draft -> blue
		if (docstatus === 0 || doc.status === "Draft") {
			return [__("Draft", null, dt), "blue", "docstatus,=,0"];
		}

		// 3. Purchase Invoice specific holds
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

		// 4. Status color mapping
		const status_colors = {
			Paid: "green",
			Unpaid: "orange",
			"Unpaid and Discounted": "orange",
			"Partly Paid": "yellow",
			"Partly Paid and Discounted": "yellow",
			Overdue: "red",
			"Overdue and Discounted": "red",
			Return: "gray",
			"Credit Note Issued": "gray",
			"Debit Note Issued": "gray",
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

	rrs_customizations.get_invoice_status_indicator = get_invoice_status_indicator;

	// Patch frappe.get_indicator globally so List, Form, Kanban, and Report views use the custom scheme
	if (frappe.get_indicator) {
		const orig_get_indicator = frappe.get_indicator;
		frappe.get_indicator = function (doc, doctype, show_workflow_state) {
			const custom = get_invoice_status_indicator(doc, doctype);
			if (custom) return custom;
			return orig_get_indicator.apply(this, arguments);
		};
	}

	// Configure listview settings for both doctypes
	["Sales Invoice", "Purchase Invoice"].forEach(function (dt) {
		frappe.listview_settings = frappe.listview_settings || {};
		const existing = frappe.listview_settings[dt] || {};
		frappe.listview_settings[dt] = Object.assign(existing, {
			has_indicator_for_draft: true,
			has_indicator_for_cancelled: true,
			get_indicator: function (doc) {
				return (
					get_invoice_status_indicator(doc, dt) ||
					(existing.get_indicator ? existing.get_indicator(doc) : null)
				);
			},
		});
	});
})();

