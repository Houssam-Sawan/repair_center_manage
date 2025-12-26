// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// render
frappe.listview_settings["Repair Request"] = {
	
    add_fields: ['ID', 'status', 'assigned_technician', 'service_center'],
    has_indicator_for_draft: true,
    hide_name_column: true, // hide the last column which shows the `name`
    hide_name_filter: true, // hide the default filter field for the name column
	get_indicator: function (doc) {

		const status_colors = {
			"Not Saved": "red",
			"Open": "orange",
			"In Progress": "blue",
			"Pending Parts Allocation": "purple",
			"Pending for Spare Parts": "orange",
			"Parts Allocated": "light-blue",
			"Repaired": "green",
			"Paid": "green",
			"Delivered": "green",
			"Cancelled": "red"
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	}
	//right_column: "grand_total",


}
