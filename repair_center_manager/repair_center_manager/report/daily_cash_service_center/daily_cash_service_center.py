
import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate, cint, add_days

def execute(filters=None):
    """
    Main execution function for the Service Center Cash Collection Report
    Returns columns, data, message, chart, and report summary
    """
    if not filters:
        filters = {}
    
    validate_filters(filters)
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    report_summary = get_report_summary(data, filters)
    
    return columns, data, None, chart, report_summary

def validate_filters(filters):
    """
    Validate filter values
    """
    if not filters.get("from_date"):
        frappe.throw(_("From Date is mandatory"))
    
    if not filters.get("to_date"):
        frappe.throw(_("To Date is mandatory"))
    
    if getdate(filters.get("from_date")) > getdate(filters.get("to_date")):
        frappe.throw(_("From Date cannot be greater than To Date"))

def get_columns(filters):
    """
    Define report columns with all standard options
    """
    columns = [
        {
            "label": _("Service Center"),
            "fieldname": "service_center",
            "fieldtype": "Link",
            "options": "Service Center",
            "width": 180,
        },
        {
            "label": _("Service Center Name"),
            "fieldname": "service_center_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Territory"),
            "fieldname": "territory",
            "fieldtype": "Link",
            "options": "Territory",
            "width": 140,
        },
        {
            "label": _("Total Cash Collected"),
            "fieldname": "total_cash",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": _("Repairs Count"),
            "fieldname": "repairs_count",
            "fieldtype": "Int",
            "width": 140,
        },
        {
            "label": _("Average Per Repair"),
            "fieldname": "avg_per_repair",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": _("Total Invoices"),
            "fieldname": "total_invoices",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": _("Total Payments"),
            "fieldname": "total_payments",
            "fieldtype": "Int",
            "width": 140,
        }
    ]
    
    # Add conditional columns based on filters
    if filters.get("show_details"):
        columns.extend([
            {
                "label": _("First Payment Date"),
                "fieldname": "first_payment_date",
                "fieldtype": "Date",
                "width": 120,
            },
            {
                "label": _("Last Payment Date"),
                "fieldname": "last_payment_date",
                "fieldtype": "Date",
                "width": 120,
            }
        ])
    
    return columns

def get_conditions(filters):
    """
    Build SQL conditions based on filters
    """
    conditions = ["pe.docstatus = 1"]
    
    if filters.get("from_date"):
        conditions.append("pe.posting_date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("pe.posting_date <= %(to_date)s")
    
    if filters.get("service_center"):
        conditions.append("rr.service_center = %(service_center)s")
    
    if filters.get("territory"):
        conditions.append("sc.territory = %(territory)s")
    
    if filters.get("company"):
        conditions.append("pe.company = %(company)s")
    
    if filters.get("mode_of_payment"):
        conditions.append("pe.mode_of_payment = %(mode_of_payment)s")
    
    if filters.get("payment_type"):
        conditions.append("pe.payment_type = %(payment_type)s")
    
    return " AND ".join(conditions)

def get_data(filters):
    """
    Fetch and return report data
    """
    conditions = get_conditions(filters)
    
    # Build additional fields based on filters
    additional_fields = ""
    additional_group_by = ""
    
    if filters.get("show_details"):
        additional_fields = """,
            MIN(pe.posting_date) AS first_payment_date,
            MAX(pe.posting_date) AS last_payment_date
        """
    
    query = f"""
        SELECT
            rr.service_center AS service_center,
            sc.service_center_name AS service_center_name,
            sc.territory AS territory,
            SUM(per.allocated_amount) AS total_cash,
            COUNT(DISTINCT rr.name) AS repairs_count,
            COUNT(DISTINCT si.name) AS total_invoices,
            COUNT(DISTINCT pe.name) AS total_payments
            {additional_fields}
        FROM `tabPayment Entry` pe
        JOIN `tabPayment Entry Reference` per
            ON per.parent = pe.name
            AND per.reference_doctype = 'Sales Invoice'
        JOIN `tabSales Invoice` si
            ON si.name = per.reference_name
        JOIN `tabRepair Request` rr
            ON si.custom_repair_request = rr.name
        LEFT JOIN `tabService Center` sc
            ON sc.name = rr.service_center
        WHERE
            {conditions}
        GROUP BY rr.service_center, sc.service_center_name, sc.territory
        ORDER BY total_cash DESC
    """
    
    data = frappe.db.sql(query, filters, as_dict=1)
    
    # Calculate derived fields
    for row in data:
        if row.get("repairs_count"):
            row["avg_per_repair"] = flt(row.get("total_cash", 0)) / flt(row.get("repairs_count", 1))
        else:
            row["avg_per_repair"] = 0
    
    return data

def get_chart_data(data, filters):
    """
    Generate chart data for visualization
    """
    if not data:
        return None
    
    # Limit to top 10 service centers for better chart readability
    chart_data = data[:10] if len(data) > 10 else data
    
    labels = [d.get("service_center") or "Unknown" for d in chart_data]
    values = [flt(d.get("total_cash", 0)) for d in chart_data]
    
    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Cash Collected"),
                    "values": values
                }
            ]
        },
        "type": "bar",
        "colors": ["#29CD42"],
        "barOptions": {
            "stacked": False
        },
        "tooltipOptions": {
            "formatTooltipY": lambda d: frappe.format_value(d, {"fieldtype": "Currency"})
        }
    }
    
    return chart

def get_report_summary(data, filters):
    """
    Generate report summary cards with key metrics
    """
    if not data:
        return []
    
    total_cash = sum([flt(d.get("total_cash", 0)) for d in data])
    total_repairs = sum([cint(d.get("repairs_count", 0)) for d in data])
    total_service_centers = len(data)
    avg_per_center = total_cash / total_service_centers if total_service_centers else 0
    avg_per_repair = total_cash / total_repairs if total_repairs else 0
    
    # Get currency from company
    currency = frappe.defaults.get_global_default("currency")
    if filters.get("company"):
        currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency")
    
    # Calculate period
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    days = (to_date - from_date).days + 1
    
    summary = [
        {
            "value": total_cash,
            "label": _("Total Cash Collected"),
            "datatype": "Currency",
            "currency": currency,
            "indicator": "Green"
        },
        {
            "value": total_service_centers,
            "label": _("Service Centers"),
            "datatype": "Int",
            "indicator": "Blue"
        },
        {
            "value": total_repairs,
            "label": _("Total Repairs"),
            "datatype": "Int",
            "indicator": "Blue"
        },
        {
            "value": avg_per_center,
            "label": _("Avg Per Service Center"),
            "datatype": "Currency",
            "currency": currency,
            "indicator": "Orange"
        },
        {
            "value": avg_per_repair,
            "label": _("Avg Per Repair"),
            "datatype": "Currency",
            "currency": currency,
            "indicator": "Purple"
        },
        {
            "value": days,
            "label": _("Period (Days)"),
            "datatype": "Int",
            "indicator": "Gray"
        }
    ]
    
    return summary