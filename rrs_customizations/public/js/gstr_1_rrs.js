// Copyright (c) 2026, RRSurgica and contributors
// For license information, please see license.txt

frappe.ui.form.on("GSTR-1", {
    refresh(frm) {
        setup_rrs_gstr1_actions(frm);
    },
    load_gstr1_data(frm) {
        setup_rrs_gstr1_actions(frm);
    },
});

function setup_rrs_gstr1_actions(frm) {
    if (!frm) return;

    // Add custom button ONLY at the top of the GSTR-1 form header
    frm.add_custom_button(__("Download GSTR-1 (RRS)"), () => {
        trigger_gstr1_rrs_download(frm);
    });
}

function trigger_gstr1_rrs_download(frm) {
    const doc = frm.doc;
    if (!doc.company_gstin || !doc.month_or_quarter || !doc.year) {
        frappe.msgprint({
            title: __("Missing Filter"),
            indicator: "orange",
            message: __("Please select Company GSTIN, Year, and Month/Quarter to download GSTR-1 (RRS)."),
        });
        return;
    }

    frappe.show_alert({
        message: __("Preparing GSTR-1 (RRS) with invoice-wise exempt details..."),
        indicator: "blue",
    });

    const post_args = {
        company_gstin: doc.company_gstin,
        month_or_quarter: doc.month_or_quarter,
        year: doc.year,
        company: doc.company || "",
    };

    open_url_post(
        "/api/method/rrs_customizations.gstr1_rrs.download_gstr1_rrs",
        post_args
    );
}
