// Copyright (c) 2025, Houssam Sawan and contributors
// For license information, please see license.txt



frappe.query_reports["All Stock Report"] = {
    "filters": [
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "get_query": function() {
                return {
                    "ignore_user_permissions": 1,
                    "filters": {
                        "is_group": 0
                    }
                };
            }
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "show_zero_stock",
            "label": __("Show Zero Stock"),
            "fieldtype": "Check",
            "default": 0
        }
    ]
}