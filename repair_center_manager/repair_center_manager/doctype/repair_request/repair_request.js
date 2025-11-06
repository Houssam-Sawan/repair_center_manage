// Copyright (c) 2025, Houssam Sawan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Repair Request", {

	    /**
     * Onload: Set filters
     */
    onload: function(frm) {
        // Filter for assigned_technician
        // Only show users who are 'Technician' role AND are linked to the selected Service Center 
        frm.set_query('assigned_technician', function(doc) {
            if (!doc.service_center) {
                frappe.throw(__("Please select a Service Center first."));
            }
            return {
                query: 'repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.get_technicians_by_service_center',
                filters: {
                   // 'service_center': doc.service_center
                }
            };
        });

        // Filter for customer contact
        frm.set_query('contact', function() {
            if (frm.doc.customer) {
                return {
                    filters: {
                        'link_doctype': 'Customer',
                        'link_name': frm.doc.customer
                    }
                };
            }
        });
    },
 	refresh: function(frm) {

        frm.set_intro("");
        let state = frm.doc.status;

        if (state !== "Not Saved") {
            frm.disable_save();
        }
        // Add "Assign & Start Repair" button only if docstatus is 0 (Draft)
        if(state === "Open" && (frappe.user.has_role("Receptionist") || frappe.user.has_role("System Manager"))) {
            frm.add_custom_button("Assign & Start Repair", () => {
                frappe.call({
                    method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.assign_technician_and_start",
                    args: { docname: frm.doc.name ,
                                assigned_technician: frm.doc.assigned_technician
                    },
                    callback: () => frm.reload_doc()
                });
            });
        }        

/*         if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('test Assign & Start Repair'), function() {
                        // This uses the newly assigned technician and starts the process.
                        frm.call('test');
                    }).addClass('btn-primary');
        } */
        
        // Display a helpful reminder message for the Receptionist.
        if (frm.doc.status === 'Open' && frm.doc.docstatus === 0 && !frm.doc.assigned_technician && frappe.user_has_role('Receptionist')) {
             frm.msg_box({
                title: __('Assignment Required'),
                indicator: 'orange',
                message: __('Please select an **Assigned Technician** before using the **Assign & Start** action button.')
            });
        }

        frm.set_query("customer_contact", function (doc) {
			return {
				filters: {
					customer: doc.customer,
                    }
			};
		});
	},

	    /**
     * Fetch Service Center Abbreviation
     */
/*     service_center: function(frm) {
        if (frm.doc.service_center) {
            frappe.db.get_value('Service Center', frm.doc.service_center, 'branch')
                .then(r => {
                    if (r.message && r.message.branch) {
                        // Assuming branch name is 'Service Center A (SCA)'
                        let matches = r.message.branch.match(/\((.*?)\)/);
                        let abbr = matches ? matches[1] : 'SC';
                        frm.set_value('service_center_abbr', abbr);
                    }
                });
            // Clear technician as filter has changed
            frm.set_value('assigned_technician', null);
            frm.refresh_field('assigned_technician');
        }
    }, */

	customer: function(frm) {
        if (frm.doc.customer) {
            frappe.db.get_value('Customer', frm.doc.customer, 'customer_name')
                .then(r => {
                    if (r.message) {
                        frm.set_value('customer_name', r.message.customer_name);
                    }
                });
            // Clear contact and refresh filter
            frm.set_value('contact', null);
            frm.refresh_field('contact');
        }
    },

	brand: function(frm) {
		frm.set_query("device_model", function (doc) {
			return {
				filters: [
					["Device Model", "device_brand", "=", doc.brand]
				]
			};
		});
	},
	
});

/**
 * Child Table: Repair Request Part
 */
frappe.ui.form.on('Repair Request Part', {
    /**
     * When item_code is selected, fetch details
     */
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_code) {
            // Fetch item details
            frappe.db.get_value('Item', row.item_code, ['item_name', 'description'])
                .then(r => {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
                        frappe.model.set_value(cdt, cdn, 'description', r.message.description);
                    }
                });
            
            // Fetch stock availability from the service center's store
            if (frm.doc.service_center) {
                 frappe.call({
                    method: 'repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.get_item_availability',
                    args: {
                        item_code: row.item_code,
                        service_center: frm.doc.service_center
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.model.set_value(cdt, cdn, 'available_qty', r.message);
                        }
                    }
                });
            } else {
                frappe.msgprint(__("Please set the Service Center first to check stock availability."));
            }
        }
    },

    /**
     * Refresh child table rows
     */
    required_parts_refresh: function(frm) {
        // This is a placeholder for any logic on table refresh
    }
});



function test_button() {
    frappe.call({
        method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.test",
    });
}