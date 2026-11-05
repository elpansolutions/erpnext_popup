frappe.ui.form.on("Payment Entry", {
	setup: function (frm) {
		const original_get_outstanding_documents = frm.events.get_outstanding_documents;
		frm.events.get_outstanding_documents = function (
			frm,
			filters,
			get_outstanding_invoices,
			get_orders_to_be_billed
		) {
			const res = original_get_outstanding_documents.apply(this, arguments);
			if (res && res.then) {
				res.then(function (r) {
					if (r && r.message && frm.doc.references) {
						const bill_date_map = {};
						r.message.forEach(function (d) {
							if (d.voucher_no && d.bill_date) {
								bill_date_map[d.voucher_no] = d.bill_date;
							}
						});

						(frm.doc.references || []).forEach(function (row) {
							if (
								row.reference_doctype === "Purchase Invoice" &&
								bill_date_map[row.reference_name]
							) {
								frappe.model.set_value(
									row.doctype,
									row.name,
									"bill_date",
									bill_date_map[row.reference_name]
								);
							}
						});
						frm.refresh_field("references");
					}
				});
			}
			return res;
		};
	},
});

frappe.ui.form.on("Payment Entry Reference", {
	reference_name: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.reference_doctype === "Purchase Invoice" && row.reference_name && !row.bill_date) {
			frappe.db.get_value("Purchase Invoice", row.reference_name, "bill_date", function (val) {
				if (val && val.bill_date) {
					frappe.model.set_value(cdt, cdn, "bill_date", val.bill_date);
				}
			});
		}
	},
});
