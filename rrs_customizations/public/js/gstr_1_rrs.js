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

    // 1. Add primary custom button to the form header
    frm.add_custom_button(__("Download GSTR-1 (RRS)"), () => {
        trigger_gstr1_rrs_download(frm);
    });

    // Style the button slightly to make it easily recognizable by auditor
    frm.page.set_inner_btn_group_as_primary?.(__("Download GSTR-1 (RRS)"));

    // 2. Also inject into tab custom-button-group next to "Download Excel"
    inject_tab_button(frm);
}

function inject_tab_button(frm) {
    setTimeout(() => {
        if (!frm?.$wrapper) return;
        const button_groups = frm.$wrapper.find(".custom-button-group");
        button_groups.each(function () {
            const $grp = $(this);
            if (!$grp.find(".btn-gstr1-rrs").length) {
                $(`<button class="btn btn-default btn-gstr1-rrs ellipsis" style="margin-left: 8px;">
                    ${__("Download Excel (RRS)")}
                </button>`)
                    .appendTo($grp)
                    .on("click", (e) => {
                        e.preventDefault();
                        trigger_gstr1_rrs_download(frm);
                    });
            }
        });
    }, 400);
}

// Re-inject tab button on tab clicks
$(document).on("click", ".nav-tabs .nav-link, .nav-pills .nav-link", function () {
    if (cur_frm && cur_frm.doctype === "GSTR-1") {
        inject_tab_button(cur_frm);
    }
});

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
