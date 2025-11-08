// Copyright (c) 2025, Houssam Sawan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Repair Request", {

    required_parts_delete: function(frm){
        calculate_total(frm);
    },

	    /**
     * Onload: Set filters
     */
    onload: function(frm) {


    },
 	refresh: function(frm) {
        
        frm.add_custom_button(__('Test Button'), function() {
            test_button();
        }).addClass('btn-secondary');

        frm.set_intro("");

                // Filter for assigned_technician
        // Only show users who are 'Technician' role AND are linked to the selected Service Center 
        frm.set_query('assigned_technician', function(doc) {
            if (!doc.service_center) {
                frappe.throw(__("Please select a Service Center first."));
            }

            return {
                query: 'repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.get_technicians_by_service_center',
                filters: {
                    search_service_center: frm.doc.service_center
                }
               
            };
        });

/*         if (frm.doc.status !== "Not Saved") {
            frm.disable_save();
        }
 */
            // =================================================================
            // == STATUS: Open (Receptionist Action: ASSIGN & START) ==
            // =================================================================
        // Add "Assign & Start Repair" button only if docstatus is 0 (Draft)
        if(frm.doc.status === "Open" && (frappe.user.has_role("Receptionist") || frappe.user.has_role("SC Manager"))) {
            
            frm.add_custom_button("Assign & Start Repair", () => {
                frappe.call({
                    method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.assign_technician_and_start",
                    args: { docname: frm.doc.name ,
                                assigned_technician: frm.doc.assigned_technician
                    },
                    callback: () => frm.reload_doc()
                });
            }).addClass("btn-primary");
        }        

            // =================================================================
            // == STATUS: In Progress (Technician Action: REQUEST PARTS/COMPLETE) ==
            // =================================================================
            if (frm.doc.status === 'In Progress' && (frappe.user.has_role('Technician') || frappe.user.has_role("SC Manager"))) {
                //frappe.msgprint(__('You are logged in as: {0}', [frappe.session.user]));
               /*  frm.add_custom_button(__('Test Button'), function() {
                    if (frappe.user.has_role('Technician') ){
                        frappe.msgprint(__('You are a Technician {0}', [frm.doc.status]));
                        frappe.msgprint(__('Assigned Technician: {0} nad condition is {1}', [frm.doc.assigned_technician,frm.doc.assigned_technician === frappe.session.user]));
                    }
                }).addClass('btn-secondary'); */

                if (frm.doc.assigned_technician === frappe.session.user) {
                    // Button to request parts
                    frm.add_custom_button(__('Request Parts'), function() {
                        if (!frm.doc.required_parts || frm.doc.required_parts.length === 0) {
                            frappe.msgprint(__("Please add items to the 'Required Parts' table first."));
                            return;
                        }
                        if (!frm.doc.fault_category && !frm.doc.fault_description) {
                            frappe.msgprint(__("Please provide Fault Category and Description before requesting parts."));
                            return;
                        }
                        frappe.call({
                            method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.request_parts_from_warehouse",
                            args: { 
                                docname: frm.doc.name 
                            },
                            callback: () => frm.reload_doc()
                        });
                    }).addClass('btn-primary');
                    
                    // Button to complete without parts
                    frm.add_custom_button(__('Complete Repair'), function() {
                        if (!frm.doc.fault_category && !frm.doc.fault_description) {
                            frappe.msgprint(__("Please provide Fault Category and Description before requesting parts."));
                            return;
                        }
                        frm.set_value('status', 'Repaired');
                        frm.save();
                    }).addClass('btn-success');
                }
            }  

            // =================================================================
            // == STATUS: Pending Parts Allocation (Warehouse Action) ==
            // =================================================================
            if (frm.doc.status === 'Pending Parts Allocation' && (frappe.user.has_role('Service Center Warehouse Manager') || frappe.user.has_role("SC Manager")) ) {
                // Button to create Stock Entry (Material Transfer)
                frm.add_custom_button(__('Allocate Parts'), function() {
                    frappe.call({
                        method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.create_stock_transfer",
                        args: { 
                            docname: frm.doc.name 
                        },
                        callback: () => frm.reload_doc()
                    });
                    }).addClass('btn-primary');
                
                // Button to mark as pending from main warehouse
                frm.add_custom_button(__('Mark Pending'), function() {
                    frappe.call({
                        method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.mark_pending_from_main",
                        args: { 
                            docname: frm.doc.name 
                        },
                        callback: () => frm.reload_doc()
                    });
                }).addClass('btn-warning');
            }

                        // =================================================================
            // == STATUS:  Pending for Spare Parts (Warehouse Action) ==
            // =================================================================


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



	
});

/**
 * Child Table: Repair Request Part
 */
frappe.ui.form.on('Repair Request Material', {
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

            // Fetch latest selling price
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Item Price',
                fields: ['price_list_rate', 'price_list', 'valid_from'],
                filters: {
                    item_code: row.item_code,
                    selling: 1,
                    price_list: 'Standard Selling'
                },
                order_by: 'modified desc',
                limit_page_length: 1
            },
            callback: function(r) {
                if (r.message && r.message.length) {
                    let price = r.message[0].price_list_rate;
                    frappe.model.set_value(cdt, cdn, 'price', price);
                    calculate_total(frm, cdt, cdn);
                } else {
                    frappe.model.set_value(cdt, cdn, 'price', 0);
                    frappe.msgprint(__('No selling price found for this item'));
                }
            }
        });
        }
    },

    /**
     * Refresh child table rows
     */
    required_parts_refresh: function(frm) {
        // This is a placeholder for any logic on table refresh
        calculate_total(frm);
    },

    required_qty: calculate_total,
    price: calculate_total,
    required_parts_remove: function(frm, cdt, cdn) {
        calculate_total(frm);
    }
    
    
});



function test_button() {
    frm.call('test');
}

function calculate_total(frm, cdt, cdn) {
    let total = 0;
    (frm.doc.required_parts || []).forEach(row => {
        if (row.required_qty && row.price) {
            total += row.required_qty * row.price;
        }
    });

    // Set total field value in parent doc
    frm.set_value('total', total);
    refresh_field('total');
}