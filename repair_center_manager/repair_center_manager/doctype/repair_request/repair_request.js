// Copyright (c) 2025, Houssam Sawan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Repair Request", {

    required_parts_delete: function(frm){
        calculate_totals(frm);
    },
    
    brand: function(frm, cdt, cdn) {
        frm.set_value('device_model', null);
        frm.refresh_field('device_model');
        frm.set_value('brand_manager', null);
        frm.refresh_field('brand_manager');
    
        calculate_labor_charge(frm);
        frappe.db.get_value(
            'Brand Manager',
            { 'brand': frm.doc.brand },
            'name'
        ).then(r => {
            if (r && r.message && r.message.name) {
                frm.set_value('brand_manager', r.message.name);
                frm.refresh_field('brand_manager');
            }
        });

    },

    repair_type: function(frm, cdt, cdn) {
        calculate_labor_charge(frm);
    },

    resolution: function(frm, cdt, cdn) {
        calculate_labor_charge(frm);
    },

	    /**
     * Onload: Set filters
     */
    onload: function(frm) {


    },
 	refresh: function(frm) {

        
/*         frm.add_custom_button(__('Test Button'), function() {
            test_button();
        }).addClass('btn-secondary');
 */
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
        if(frm.doc.status === "Open" && (frappe.user.has_role("Receptionist") || frappe.user.has_role('SC Manager'))) {
            
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
            if (frm.doc.status === 'In Progress' && (frappe.user.has_role('Technician') || frappe.user.has_role('SC Manager'))) {
                //frappe.msgprint(__('You are logged in as: {0}', [frappe.session.user]));
               /*  frm.add_custom_button(__('Test Button'), function() {
                    if (frappe.user.has_role('Technician') ){
                        frappe.msgprint(__('You are a Technician {0}', [frm.doc.status]));
                        frappe.msgprint(__('Assigned Technician: {0} nad condition is {1}', [frm.doc.assigned_technician,frm.doc.assigned_technician === frappe.session.user]));
                    }
                }).addClass('btn-secondary'); */

                if (frm.doc.assigned_technician === frappe.session.user || frappe.user.has_role('SC Manager')) {
                        // Button to request parts
                    if (frm.doc.resolution === 'Parts replacement'){
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
                    }
                    else if (frm.doc.resolution === 'Swap') {
                        // Button to request swap approval from brand manager
                        frm.add_custom_button(__('Request Swap Approval'), function() {
                            if (!frm.doc.fault_category && !frm.doc.fault_description) {
                                frappe.msgprint(__("Please provide Fault Category and Description before requesting swap approval."));
                                return;
                            }
                            frappe.call({
                                method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.request_swap_approval",
                                args: { 
                                    docname: frm.doc.name 
                                },
                                callback: () => frm.reload_doc()
                            });
                        }).addClass('btn-primary');
                    }
                    else {
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
            }  

            // =================================================================
            // == STATUS: Pending Parts Allocation (Warehouse Action) ==
            // =================================================================
            if (frm.doc.status === 'Pending Parts Allocation' && (frappe.user.has_role('Service Center Warehouse Manager') || frappe.user.has_role('SC Manager')) ) {
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
            if (frm.doc.status === 'Pending for Spare Parts' && (frappe.user.has_role('Service Center Warehouse Manager') || frappe.user.has_role('SC Manager')) ) {
                // Button to mark as pending from main warehouse
                frm.add_custom_button(__('Spare Parts Received'), function() {
                    frappe.call({
                        method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.mark_spart_parts_received",
                        args: { 
                            docname: frm.doc.name 
                        },
                        callback: () => frm.reload_doc()
                    });
                }).addClass('btn-warning');
            }
            
            // =================================================================
            // == STATUS: Parts Allocated (Technician Action: COMPLETE) ==
            // =================================================================
            if (frm.doc.status === 'Parts Allocated' && (frappe.user.has_role('Technician') || frappe.user.has_role('SC Manager')) ) {
                 if (frm.doc.assigned_technician === frappe.session.user || frappe.user.has_role('SC Manager')) {
                     frm.add_custom_button(__('Complete Repair'), function() {
                        frappe.call({
                        method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.complete_repair",
                        args: { 
                            docname: frm.doc.name 
                        },
                        callback: () => frm.reload_doc()
                    });
                    }).addClass('btn-success');
                 }
            }
                        // =================================================================
            // == STATUS: Repaired (Receptionist Action: Receive Payment) ==
            // =================================================================
            if (frm.doc.status === 'Repaired' && (frappe.user.has_role('Receptionist') || frappe.user.has_role('SC Manager'))) {
                 frm.add_custom_button(__('Receive Payment'), function() {
                    frappe.call({
                        method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.recieve_payment",
                        args: { 
                            docname: frm.doc.name 
                        },
                        callback: (r) => {
                            if (r.message) {
                                frappe.msgprint(
                                    `Payment received successfully.<br>
                                    Invoice: ${r.message.invoice}<br>
                                    Payment Entry: ${r.message.payment}`
                                );
                                 frm.reload_doc()
                            }
                        } 
                    });
                }).addClass('btn-primary');
            }
                        // =================================================================
            // == STATUS: Paid (Receptionist Action: DELIVER) ==
            // =================================================================
            if (frm.doc.status === 'Paid' && (frappe.user.has_role('Receptionist') || frappe.user.has_role('SC Manager'))) {
                 frm.add_custom_button(__('Deliver to Customer'), function() {
                    frappe.call({
                        method: "repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.deliver_to_customer",
                        args: { 
                            docname: frm.doc.name 
                        },
                        callback: () => frm.reload_doc()
                    });
                }).addClass('btn-primary');
            }
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
                        }else {
                            frappe.model.set_value(cdt, cdn, 'available_qty', 0);
                            frapppe.model.set_value(cdt, cdn, 'required_qty', 0);
                            
                        }
                    }
                });
            } else {
                frappe.msgprint(__("Please set the Service Center first to check stock availability."));
            }

            // Fetch stock cost price from the service center's store
            if (frm.doc.service_center) {
                 frappe.call({
                    method: 'repair_center_manager.repair_center_manager.doctype.repair_request.repair_request.get_item_cost_price',
                    args: {
                        item_code: row.item_code,
                        service_center: frm.doc.service_center
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.model.set_value(cdt, cdn, 'item_cost', r.message);
                        }
                        else {
                            frappe.model.set_value(cdt, cdn, 'item_cost', 0);
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
                    calculate_totals(frm, cdt, cdn);
                } else {
                    frappe.model.set_value(cdt, cdn, 'price', 0);
                    //frappe.msgprint(__('No selling price found for this item'));
                }
            }
        });
        }
        calculate_totals(frm, cdt, cdn);
    },

    /**
     * Refresh child table rows
     */
    required_qty: function(frm) {
        // This is a placeholder for any logic on table refresh
        frappe.msgprint(__('Required Parts table refreshed'));
        calculate_totals(frm);
    },
   
    item_cost: function(frm) {
        // This is a placeholder for any logic on table refresh
        frappe.msgprint(__('Required Parts table refreshed'));
        calculate_totals(frm);
    },
    
    price: function(frm) {
        // This is a placeholder for any logic on table refresh
        frappe.msgprint(__('Required Parts table refreshed'));
        calculate_totals(frm);
    },


    required_parts_remove: function(frm, cdt, cdn) {
        calculate_totals(frm);
    },


    
    
});



function test_button() {
    frm.call('test');
}

function calculate_totals(frm, cdt, cdn) {
    let total = 0;
    let total_cost = 0;
    let labor_charge = frm.doc.labor_charge || 0;
    (frm.doc.required_parts || []).forEach(row => {
        if (row.required_qty && row.price) {
            total += row.required_qty * row.price;
            row.amount = row.required_qty * row.price;
            frappe.model.set_value(cdt, cdn, 'amount', row.amount);
            refresh_field('required_parts');
        }
        if (row.required_qty && row.item_cost) {
            total_cost += row.required_qty * row.item_cost;
            row.amount_cost = row.required_qty * row.item_cost;
            frappe.model.set_value(cdt, cdn, 'amount_cost', row.amount_cost);
            refresh_field('required_parts');
        }
    });

    if (frm.doc.resolution !== 'Parts replacement') {
        total = 0;
        total_cost = 0;
    }
    if(frm.doc.repair_type === 'In Warranty')  {
        total = 0;
    }
    // Set total field value in parent doc
    frm.set_value('total', total);
    frm.set_value('total_cost', total_cost);
    frm.set_value('profit', labor_charge + total - total_cost);
    refresh_field('total');
}

function calculate_labor_charge(frm) {

    let labor_charge = frm.doc.labor_charge || 0;
    let total = frm.doc.total || 0;
    let total_cost = frm.doc.total_cost || 0;
    let repair_type = frm.doc.repair_type || '';
    let resolution = frm.doc.resolution || '';
    let brand = frm.doc.brand || '';

    if (repair_type == 'In Warranty') {
        //get labor charge document
        frappe.db.get_value('Labor Charge', { 'brand': brand , 'service_charge_type': resolution}, 'labor_charge')
        .then(r => {
            if (r.message) {
                //frappe.msgprint(r.message.labor_charge);
                labor_charge_usd = r.message.labor_charge || 0;
                //Get company exchange rate
                frappe.db.get_value('Company', frm.doc.company, 'default_currency')
                .then(comp => {
                    if (comp.message) {
                        let company_currency = comp.message.default_currency;
                        //Convert labor charge to company currency if needed
                        frappe.call({
                            method: 'erpnext.setup.utils.get_exchange_rate',
                            args: {
                                from_currency: 'USD', // Assuming labor charge is in USD
                                to_currency: company_currency
                            },
                            callback: function(conv) {
                                if (conv.message) {
                                    labor_charge = conv.message * labor_charge_usd;
                                    frm.set_value('labor_charge', labor_charge);
                                    frm.set_value('labor_charge_usd', labor_charge_usd);
                                    frm.set_value('profit', labor_charge + total - total_cost);
                                    refresh_field('labor_charge');
                                    refresh_field('labor_charge_usd');
                                    refresh_field('profit');
                                }
                            }
                        });
                    }
                });
            } else {
                frm.set_value('labor_charge', labor_charge);
                frm.set_value('profit', labor_charge + total - total_cost);
                refresh_field('labor_charge');
                refresh_field('profit');
            }
        });

    }



    frm.set_value('profit', labor_charge + total - total_cost);
    refresh_field('profit');
    refresh_field('labor_charge');
}