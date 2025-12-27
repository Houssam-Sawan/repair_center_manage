frappe.ui.form.on('SC Stock Transfer', {
    refresh: function(frm) {
        if (frm.doc.status === "Approved" || frm.doc.status === "Completed") {
            frm.set_read_only();
        }

        if (frm.doc.status === "Pending Approval" && frm.doc.from_service_center_user === frappe.session.user) {
            frm.add_custom_button('Approve Transfer', function() {
                frappe.call({
                    method: "your_app.your_module.doctype.sc_stock_transfer.sc_stock_transfer.SCStockTransfer.approve_transfer",
                    args: { "name": frm.doc.name },
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            }, __("Actions"));
        }

        if (frm.doc.status === "Approved" && frm.doc.to_service_center_user === frappe.session.user) {
            frm.add_custom_button('Receive Stock', function() {
                frappe.call({
                    method: "your_app.your_module.doctype.sc_stock_transfer.sc_stock_transfer.SCStockTransfer.receive_transfer",
                    args: { "name": frm.doc.name },
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            }, __("Actions"));
        }
    }
});
