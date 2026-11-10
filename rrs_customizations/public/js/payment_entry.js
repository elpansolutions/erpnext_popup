frappe.ui.form.on("Payment Entry", {
	setup: function (frm) {
		ensure_bill_date_in_grid_settings(frm);
		override_get_outstanding_documents(frm);
		override_set_total_allocated_amount(frm);
	},

	refresh: function (frm) {
		ensure_bill_date_in_grid_settings(frm);
		sync_missing_bill_dates(frm);
	},
});

function ensure_bill_date_in_grid_settings(frm) {
	const grid = frm.fields_dict.references?.grid;
	if (!grid) return;

	let user_settings = frappe.get_user_settings("Payment Entry", "GridView");
	if (
		user_settings &&
		user_settings["Payment Entry Reference"] &&
		user_settings["Payment Entry Reference"].length
	) {
		let cols = user_settings["Payment Entry Reference"];
		let has_bill_date = cols.some((col) => col.fieldname === "bill_date");
		if (!has_bill_date) {
			let idx = cols.findIndex(
				(col) => col.fieldname === "bill_no" || col.fieldname === "due_date"
			);
			const new_col = { fieldname: "bill_date", columns: 2, sticky: 0 };
			if (idx !== -1) {
				cols.splice(idx + 1, 0, new_col);
			} else {
				cols.push(new_col);
			}
			grid.user_defined_columns = null;
			grid.visible_columns = null;
			grid.setup_visible_columns();
			if (grid.make_head) {
				grid.make_head();
			}
			grid.reset_grid();
		}
	}
}

function override_get_outstanding_documents(frm) {
	const old_fn = frm.events?.get_outstanding_documents;
	if (!old_fn || old_fn._rrs_wrapped) return;

	const new_fn = function () {
		const res = old_fn.apply(this, arguments);

		// Synchronize bill dates after get_outstanding_documents AJAX completes
		frappe.after_ajax(() => {
			sync_missing_bill_dates(frm);
		});

		return res;
	};

	new_fn._rrs_wrapped = true;
	frm.events.get_outstanding_documents = new_fn;
	const handlers = frappe.ui.form.handlers[frm.doctype];
	if (handlers && handlers["get_outstanding_documents"]) {
		handlers["get_outstanding_documents"] = handlers["get_outstanding_documents"].map((fn) =>
			fn === old_fn ? new_fn : fn
		);
	}
}

function override_set_total_allocated_amount(frm) {
	const old_fn = frm.events?.set_total_allocated_amount;
	if (!old_fn || old_fn._rrs_wrapped) return;

	const new_fn = function () {
		const res = old_fn.apply(this, arguments);
		sync_missing_bill_dates(frm);
		return res;
	};

	new_fn._rrs_wrapped = true;
	frm.events.set_total_allocated_amount = new_fn;
	const handlers = frappe.ui.form.handlers[frm.doctype];
	if (handlers && handlers["set_total_allocated_amount"]) {
		handlers["set_total_allocated_amount"] = handlers["set_total_allocated_amount"].map((fn) =>
			fn === old_fn ? new_fn : fn
		);
	}
}

function sync_missing_bill_dates(frm) {
	if (!frm.doc.references || !frm.doc.references.length) return;

	const missing_pi_rows = frm.doc.references.filter(
		(row) => row.reference_doctype === "Purchase Invoice" && row.reference_name && !row.bill_date
	);

	if (!missing_pi_rows.length) return;

	const pi_names = [...new Set(missing_pi_rows.map((row) => row.reference_name))];

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Purchase Invoice",
			filters: { name: ["in", pi_names] },
			fields: ["name", "bill_date"],
			limit: 500,
		},
		callback: function (r) {
			if (!r || !r.message || !r.message.length) return;
			const map = {};
			r.message.forEach((d) => {
				if (d.name && d.bill_date) {
					map[d.name] = d.bill_date;
				}
			});

			let modified = false;
			(frm.doc.references || []).forEach((row) => {
				if (
					row.reference_doctype === "Purchase Invoice" &&
					map[row.reference_name] &&
					!row.bill_date
				) {
					frappe.model.set_value(row.doctype, row.name, "bill_date", map[row.reference_name]);
					modified = true;
				}
			});

			if (modified) {
				frm.refresh_field("references");
			}
		},
	});
}

frappe.ui.form.on("Payment Entry Reference", {
	reference_name: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.reference_doctype === "Purchase Invoice" && row.reference_name && !row.bill_date) {
			frappe.db.get_value(
				"Purchase Invoice",
				row.reference_name,
				"bill_date",
				function (val) {
					if (val && val.bill_date) {
						frappe.model.set_value(cdt, cdn, "bill_date", val.bill_date);
					}
				}
			);
		}
	},
});

