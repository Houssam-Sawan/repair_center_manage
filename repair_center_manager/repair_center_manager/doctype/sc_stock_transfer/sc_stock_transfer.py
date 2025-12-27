# Copyright (c) 2025, Houssam Sawan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SCStockTransfer(Document):

    def before_submit(self):
        # Draft → Pending Approval automatically
        if self.status == "Draft":
            self.status = "Pending Approval"

    def validate(self):
        # Prevent editing after approval
        if self.status in ["Approved", "Completed"] and self._action != "receive":
            frappe.throw("You cannot modify this transfer after it has been approved.")

    def approve_transfer(self):
        if self.status != "Pending Approval":
            frappe.throw("Only Pending Approval transfers can be approved.")

        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.save()

        # Reserve stock in source warehouse
        for row in self.items:
            frappe.get_doc({
                "doctype": "Stock Reservation",
                "item_code": row.item_code,
                "warehouse": self.from_service_center,
                "quantity": row.qty,
                "reference_doctype": "SC Stock Transfer",
                "reference_name": self.name
            }).insert(ignore_permissions=True)

        frappe.msgprint(f"Transfer {self.name} approved. Stock reserved in {self.from_service_center}")

    def receive_transfer(self):
        if self.status != "Approved":
            frappe.throw("Only Approved transfers can be received.")

        # Create Stock Entry (Material Transfer)
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Transfer"
        se.from_warehouse = self.from_service_center
        se.to_warehouse = self.to_service_center

        for row in self.items:
            se.append("items", {
                "item_code": row.item_code,
                "qty": row.qty,
                "uom": row.uom
            })

        se.insert(ignore_permissions=True)
        se.submit()

        # Release reserved stock
        frappe.db.delete("Stock Reservation", {
            "reference_doctype": "SC Stock Transfer",
            "reference_name": self.name
        })

        self.status = "Completed"
        self.received_by = frappe.session.user
        self.save()
        self.submit()

        frappe.msgprint(f"Transfer {self.name} received. Stock Entry {se.name} created and submitted.")
