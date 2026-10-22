frappe.provide("rrs_customizations");

(function () {
	const original_savesubmit = frappe.ui.form.Form.prototype.savesubmit;
	const bypass_confirm_doctypes = ["Purchase Invoice", "Sales Invoice", "Delivery Note", "Purchase Receipt"];

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
		if (!doc || !dt || (dt !== "Sales Invoice" && dt !== "Purchase Invoice" && dt !== "Delivery Note" && dt !== "Purchase Receipt")) {
			return null;
		}

		if (doc.__unsaved) {
			return [__("Not Saved", null, dt), "orange"];
		}

		const docstatus = doc.docstatus != null ? Number(doc.docstatus) : 0;

		// 1. Cancelled -> purple (visually distinct from Return which is gray)
		if (docstatus === 2 || doc.status === "Cancelled") {
			return [__("Cancelled", null, dt), "purple", "docstatus,=,2"];
		}

		// 2. Draft -> blue (distinct from Overdue which is red)
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

		// 4. Return -> gray
		if (doc.status === "Return" || doc.status === "Credit Note Issued") {
			return [__(doc.status, null, dt), "gray", "status,=," + doc.status];
		}

		// 5. Status color mapping
		const status_colors = {
			Paid: "green",
			Unpaid: "orange",
			"Unpaid and Discounted": "orange",
			"Partly Paid": "yellow",
			"Partly Paid and Discounted": "yellow",
			Overdue: "red",
			"Overdue and Discounted": "red",
			"Internal Transfer": "darkgrey",
			"To Bill": "orange",
			Completed: "green",
			Closed: "darkgrey",
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

	let _orig_get_indicator = frappe.get_indicator;

	function setup_indicator_interceptor() {
		if (frappe.__rrs_indicator_interceptor_set) return;

		Object.defineProperty(frappe, "get_indicator", {
			configurable: true,
			enumerable: true,
			get: function () {
				return function (doc, doctype, show_workflow_state) {
					const dt = doctype || (doc && doc.doctype);
					if (dt === "Sales Invoice" || dt === "Purchase Invoice" || dt === "Delivery Note" || dt === "Purchase Receipt") {
						const custom = get_invoice_status_indicator(doc, dt);
						if (custom) return custom;
					}
					if (typeof _orig_get_indicator === "function") {
						return _orig_get_indicator.apply(this, arguments);
					}
				};
			},
			set: function (fn) {
				_orig_get_indicator = fn;
			},
		});

		frappe.__rrs_indicator_interceptor_set = true;
	}

	function patch_listview_settings() {
		["Sales Invoice", "Purchase Invoice", "Delivery Note", "Purchase Receipt"].forEach(function (dt) {
			frappe.listview_settings = frappe.listview_settings || {};
			frappe.listview_settings[dt] = frappe.listview_settings[dt] || {};
			frappe.listview_settings[dt].has_indicator_for_draft = true;
			frappe.listview_settings[dt].has_indicator_for_cancelled = true;
			frappe.listview_settings[dt].get_indicator = function (doc) {
				return get_invoice_status_indicator(doc, dt);
			};
		});
	}

	setup_indicator_interceptor();
	patch_listview_settings();
	$(document).ready(function () {
		setup_indicator_interceptor();
		patch_listview_settings();
	});
	$(document).on("page-change", function () {
		setup_indicator_interceptor();
		patch_listview_settings();
	});
})();


