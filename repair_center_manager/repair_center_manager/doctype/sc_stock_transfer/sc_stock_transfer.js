frappe.ui.form.on('SC Stock Transfer', {
    refresh: function(frm) {
        if (frm.doc.status === "Approved" || frm.doc.status === "Completed") {
            frm.set_read_only();
        }

        if (frm.doc.status === "Draft") {
            frm.add_custom_button('Request Transfer', function() {
                frappe.call({
                    method: "repair_center_manager.repair_center_manager.doctype.sc_stock_transfer.sc_stock_transfer.request_transfer",
                    args: { docname: frm.doc.name },
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            }, __("Actions"));
        }

        if (frm.doc.status === "Pending Approval" && frm.doc.from_service_center_user === frappe.session.user) {
            frm.add_custom_button('Approve Transfer', function() {
                frappe.call({
                    method: "repair_center_manager.repair_center_manager.doctype.sc_stock_transfer.sc_stock_transfer.approve_transfer",
                    args: { docname: frm.doc.name },
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            }, __("Actions"));
        }

        if (frm.doc.status === "Approved" && frm.doc.to_service_center_user === frappe.session.user) {
            frm.add_custom_button('Receive Stock', function() {
                frappe.call({
                    method: "repair_center_manager.repair_center_manager.doctype.sc_stock_transfer.sc_stock_transfer.receive_transfer",
                    args: { docname: frm.doc.name },
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            }, __("Actions"));
        }
    }
});
