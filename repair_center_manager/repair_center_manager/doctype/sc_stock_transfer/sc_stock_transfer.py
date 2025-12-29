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
            


@frappe.whitelist()
def request_transfer(docname):
	doc = frappe.get_doc("SC Stock Transfer", docname)
	if doc.status != "Draft":
		frappe.throw("Only Draft transfers can be requested for approval.")
	doc.status = "Pending Approval"
	doc.save()
	frappe.msgprint(f"Transfer {doc.name} is now Pending Approval.")

@frappe.whitelist()
def approve_transfer(docname):
	doc = frappe.get_doc("SC Stock Transfer", docname)
	if doc.status != "Pending Approval":
		frappe.throw("Only Pending Approval transfers can be approved.")

	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.save()

	# Reserve stock in source warehouse
	for row in doc.items:
		frappe.get_doc({
			"doctype": "Stock Reservation",
			"item_code": row.item_code,
			"warehouse": doc.from_service_center,
			"quantity": row.qty,
			"reference_doctype": "SC Stock Transfer",
			"reference_name": doc.name
		}).insert(ignore_permissions=True)

	frappe.msgprint(f"Transfer {doc.name} approved. Stock reserved in {doc.from_service_center}")

@frappe.whitelist()
def receive_transfer(docname):
	doc = frappe.get_doc("SC Stock Transfer", docname)
	if doc.status != "Approved":
		frappe.throw("Only Approved transfers can be received.")

	# Create Stock Entry (Material Transfer)
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.from_warehouse = doc.from_service_center
	se.to_warehouse = doc.to_service_center

	for row in doc.items:
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
		"reference_name": doc.name
	})

	doc.status = "Completed"
	doc.received_by = frappe.session.user
	doc.save()
	doc.submit()

	frappe.msgprint(f"Transfer {doc.name} received. Stock Entry {se.name} created and submitted.")
