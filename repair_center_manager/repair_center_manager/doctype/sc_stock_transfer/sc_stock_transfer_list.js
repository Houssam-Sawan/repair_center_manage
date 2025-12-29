frappe.listview_settings["Repair Request"] = {
	
    add_fields: ['ID', 'status', 'from_service_center', 'to_service_center'],
    has_indicator_for_draft: true,
    hide_name_column: true, // hide the last column which shows the `name`
    hide_name_filter: true, // hide the default filter field for the name column
	get_indicator: function (doc) {

		const status_colors = {
			"Draft": "red",
			"Pending Approval": "orange",
			"Approved": "blue",
			"Completed": "green",
			"Cancelled": "red"
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	}


}