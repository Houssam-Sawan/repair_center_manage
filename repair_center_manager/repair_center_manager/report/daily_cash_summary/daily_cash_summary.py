# Copyright (c) 2025, Houssam Sawan and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    # Date range (required)
    conditions.append("pe.posting_date BETWEEN %(from_date)s AND %(to_date)s")
    values["from_date"] = filters.get("from_date")
    values["to_date"] = filters.get("to_date")


    # Service Center (optional)
    if filters.get("service_center_filter"):
        conditions.append("rr.service_center = %(service_center)s")
        values["service_center"] = filters.get("service_center")

    where_clause = " AND ".join(conditions)

    data = frappe.db.sql(f"""
            SELECT
                rr.service_center AS service_center,
                SUM(per.allocated_amount) AS total_cash,
                COUNT(DISTINCT rr.name) AS repairs_count
            FROM `tabPayment Entry` pe
            JOIN `tabPayment Entry Reference` per
                ON per.parent = pe.name
                AND per.reference_doctype = 'Sales Invoice'
            JOIN `tabSales Invoice` si
                ON si.name = per.reference_name
            JOIN `tabRepair Request` rr
                ON si.custom_repair_request = rr.name
            WHERE
                pe.docstatus = 1
                AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY rr.service_center
    """, values, as_dict=1)

    columns = [
        {
            "label": "Service Center",
            "fieldname": "service_center",
            "fieldtype": "Link",
            "options": "Service Center",
            "width": 180,
        },
        {
            "label": "Total Cash",
            "fieldname": "total_cash",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Repairs Count",
            "fieldname": "repairs_count",
            "fieldtype": "Int",
            "width": 140,
        },
    ]

    return columns, data
