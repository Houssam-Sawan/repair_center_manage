// Copyright (c) 2025, Houssam Sawan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Repair Request", {
 	refresh: function(frm) {
        frm.set_query("customer_contact", function (doc) {
			return {
				filters: {
					//status: "Active",
                    }
			};
		});
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


