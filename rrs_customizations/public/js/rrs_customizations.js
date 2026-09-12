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
