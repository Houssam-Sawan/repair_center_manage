import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "warehouse",
            "label": _("Warehouse"),
            "fieldtype": "Data",
            "options": "Warehouse",
            "width": 150
        },
        {
            "fieldname": "actual_qty",
            "label": _("Actual Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "reserved_qty",
            "label": _("Reserved Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "ordered_qty",
            "label": _("Ordered Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "available_qty",
            "label": _("Available Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "valuation_rate",
            "label": _("Valuation Rate"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "stock_value",
            "label": _("Stock Value"),
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    # Build filters dict
    bin_filters = {"actual_qty": [">", 0]}
    
    if filters.get("item_code"):
        bin_filters["item_code"] = filters.get("item_code")
    
    if filters.get("warehouse"):
        bin_filters["warehouse"] = filters.get("warehouse")
    
    # Get data with ignore_permissions
    bins = frappe.get_all(
        "Bin",
        filters=bin_filters,
        fields=["item_code", "warehouse", "actual_qty", "reserved_qty", 
                "ordered_qty", "valuation_rate"],
        ignore_permissions=True
    )
    
    # Get item details
    data = frappe.get_all("Bin", 
		fields=["item_code", "warehouse", "actual_qty"],
		filters=bin_filters,
		ignore_permissions=True  # Explicitly bypass user permissions
		)
    
    return data

def get_conditions(filters):
    conditions = ""
    
    if filters.get("item_code"):
        conditions += " AND bin.item_code = %(item_code)s"
    
    if filters.get("warehouse"):
        conditions += " AND bin.warehouse = %(warehouse)s"
    
    if filters.get("item_group"):
        conditions += " AND item.item_group = %(item_group)s"
    
    if filters.get("show_zero_stock"):
        conditions = conditions.replace("bin.actual_qty != 0", "1=1")
    
    return conditions