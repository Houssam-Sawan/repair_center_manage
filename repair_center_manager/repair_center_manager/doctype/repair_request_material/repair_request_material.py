# Copyright (c) 2025, Houssam Sawan and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _, msgprint, throw
from frappe.model.document import Document


class RepairRequestMaterial(Document):
	def validate(self):
		if self.quantity <= 0:
			frappe.throw("Quantity must be greater than zero.")
		if self.rate < 0:
			frappe.throw("Rate cannot be negative.")
		if self.rate == 0 and not self.is_free_item:
			frappe.throw("Rate cannot be zero for non-free items.")


