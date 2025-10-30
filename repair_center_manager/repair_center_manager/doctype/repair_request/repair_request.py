# Copyright (c) 2025, Houssam Sawan and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint, throw
from frappe.model.document import Document


class RepairRequest(Document):
	def validate(self):
		self.test_validate()

	def test_validate(self):

		if self.snimei == "12345":
			frappe.throw(_("Invalid SN/IMEI number."))
		
