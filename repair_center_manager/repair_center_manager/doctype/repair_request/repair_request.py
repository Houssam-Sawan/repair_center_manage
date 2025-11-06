# Copyright (c) 2025, Houssam Sawan and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint, throw
from frappe.utils import get_link_to_form
from frappe.model.document import Document


class RepairRequest(Document):
		
	
	def validate(self):
		self.test_validate()
		self.log_status_change()
		if self.is_new():
			self.status = "Open"

	def before_save(self):
		self.log_status_change()
		


	def on_submit(self):
		# Add any logic for on submit (if used)
		pass
	
	def on_update(self):
		self.handle_notifications()

	def test_validate(self):
		# Example validation: Serial number should not be "12345"
		if self.serial_no == "12345":
			frappe.throw(_("Invalid SN/IMEI number."))


	def log_status_change(self):
		"""Adds a new row to the repair_log child table if status has changed."""
		try:
			if self.is_new():
				self.add_log_entry(f"Repair Request created by {frappe.session.user}")
				return

			if self.get_doc_before_save() and self.get_doc_before_save().status != self.status:
				self.add_log_entry(f"Status changed from '{self.get_doc_before_save().status}' to '{self.status}'")

		except Exception as e:
			frappe.log_error(f"Error in log_status_change: {e}", "Repair Request Log Error")

	def add_log_entry(self, action_text):
		"""Helper function to append a log entry."""
		self.append("repair_log", {
			"action": action_text,
			"user": frappe.session.user
		})

	def handle_notifications(self):
		"""Send notifications based on status changes, excluding initial assignment handled by the button."""

		# 1. Status -> Repaired -> Notify Receptionist
		if self.get_doc_before_save() and self.get_doc_before_save().status != 'Repaired' and self.status == 'Repaired':
			# Use the custom function to get users based on assignment DocType
			receptionists = self.get_users_by_role_and_service_center('Receptionist', self.service_center)
			for user in receptionists:
				self.create_notification(
					user=user,
					subject=f"Repair {self.name} is complete and ready for delivery."
				)

		# 2. Status -> Pending Parts -> Notify Warehouse Manager
		if self.get_doc_before_save() and self.get_doc_before_save().status != 'Pending Parts Allocation' and self.status == 'Pending Parts Allocation':
			# Use the custom function to get users based on assignment DocType
			warehouse_managers = self.get_users_by_role_and_service_center('Service Center Warehouse Manager', self.service_center)
			for user in warehouse_managers:
				self.create_notification(
					user=user,
					subject=f"Spare parts requested for Repair: {self.name}"
				)
	def get_users_by_role_and_service_center(self, role, service_center):
		"""
		Fetches list of users with a specific role at a specific service center
		by querying the Service Center Assignment DocType.
		"""
		# 1. Get Users assigned to this Service Center
		assigned_users = frappe.get_all(
			"Service Center Assignment",
			filters={"service_center": service_center},
			pluck="user"
		)

		# 2. Filter these users by the required Role
		return frappe.get_all(
			"User",
			filters={
				"name": ("in", assigned_users),
				# Note: We must check 'Has Role' since 'role_profile_name' is not a standard column for filtering
				"user_roles": {"role": role}
			},
			pluck="name"
		)

	@frappe.whitelist()
	def test(docname):
		frappe.msgprint("Test function called successfully.")

	def create_notification(self, user, subject, doc=None):
		"""Helper to create a standard Notification Log."""
		if not doc:
			doc = self

		notification = frappe.new_doc("Notification Log")
		notification.for_user = user
		notification.subject = subject
		notification.document_type = doc.doctype
		notification.document_name = doc.name
		notification.insert(ignore_permissions=True)
		frappe.db.commit() # Notifications need explicit commit

# --- Whitelisted Functions (Callable from Client) ---

@frappe.whitelist()
def assign_technician_and_start(docname,assigned_technician=None):
	"""
	Called by the Receptionist to assign the request, set status to In Progress,
	and notify the assigned technician.
	"""

	doc =  frappe.get_doc("Repair Request", docname)

	if doc.status != "Open":
		frappe.throw("Cannot assign and start a repair that is not in 'Open' status.")

	if not assigned_technician:
		frappe.throw("Please select an Assigned Technician before starting the repair.")

	doc.assigned_technician = assigned_technician
	doc.status = "In Progress"
	doc.add_log_entry(f"Assigned to {doc.assigned_technician} and set status to 'In Progress' by {frappe.session.user}")
	doc.save()

	# Notify technician
	doc.create_notification(
		user=doc.assigned_technician,
		subject=f"New Repair Request assigned: {doc.name} - Status set to In Progress."
	)

	frappe.msgprint(_(f"Repair successfully assigned to {doc.assigned_technician} and started."), alert=True)


@frappe.whitelist()
def get_item_availability(item_code, service_center):
	"""
	Checks the available quantity of an item in the service center's main store.
	"""
	if not service_center:
		return 0

	# Get the warehouse associated with the service center
	warehouse = frappe.db.get_value("Service Center", service_center, "store_warehouse")
	if not warehouse:
		frappe.throw(f"No 'Store Warehouse' configured for Service Center: {service_center}")
		return 0

	try:
		qty = frappe.db.sql(f"""
			SELECT `actual_qty`
			FROM `tabBin`
			WHERE `item_code` = %s AND `warehouse` = %s
		""", (item_code, warehouse))

		return qty[0][0] if qty else 0

	except Exception as e:
		frappe.log_error(f"Error fetching stock for {item_code} in {warehouse}: {e}")
		return 0

@frappe.whitelist()
def get_technicians_by_service_center(doctype, txt, search_service_center, start, page_len, filters):
	"""
	Whitelisted function to filter Technicians for the assigned_technician link field.
	This replaces the standard frappe.set_query logic which is less flexible for joins.
	"""
	# 1. Get users linked to the specified service_center
	assigned_users = frappe.get_all(
		"Service Center Assignment",
		filters={"service_center": search_service_center},
		pluck="user"
	)

	if not assigned_users:
		return []

	# 2. Filter these assigned users by role 'Technician' and search text (txt)
	users = frappe.get_all(
		"User",
		filters={
			"name": ("in", assigned_users),
			"user_roles": {"role": "Technician"},
			"full_name": ("like", f"%{txt}%")
		},
		limit_start=start,
		limit_page_length=page_len,
		order_by="full_name asc",
		fields=["name", "full_name"]
	)

	return [[user.name, user.full_name] for user in users]


@frappe.whitelist()
def request_parts_from_warehouse(docname):
	"""
	Set status to 'Pending Parts Allocation' and notify warehouse.
	Called from 'Request Parts' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "In Progress":
		frappe.throw("Can only request parts when repair is 'In Progress'.")

	doc.status = "Pending Parts Allocation"
	doc.save()
	frappe.msgprint(_("Parts requested successfully. Warehouse manager has been notified."), alert=True)


@frappe.whitelist()
def mark_pending_from_main(docname):
	"""
	Set status to 'Pending for Spare Parts' and notify technician.
	Called from 'Mark Pending (Main)' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "Pending Parts Allocation":
		frappe.throw("Can only mark as pending from 'Pending Parts Allocation' status.")

	doc.status = "Pending for Spare Parts"
	doc.add_log_entry("Marked as 'Pending for Spare Parts' by Warehouse Manager.")
	doc.save()

	# Notify technician
	doc.create_notification(
		user=doc.assigned_technician,
		subject=f"Repair {doc.name} is 'Pending for Spare Parts' from main."
	)

	# Suggest creating a Material Request
	frappe.msgprint(_("Status set to 'Pending for Spare Parts'. Please create a Material Request to the Main Warehouse."), alert=True)

@frappe.whitelist()
def test(docname):
	frappe.msgprint("Test function called successfully.")

@frappe.whitelist()
def create_stock_transfer(docname):
	"""
	Creates and returns a new Stock Entry (Material Transfer)
	for the warehouse manager to fulfill.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "Pending Parts Allocation":
		frappe.throw("Can only allocate parts when status is 'Pending Parts Allocation'.")

	sc_details = frappe.get_doc("Service Center", doc.service_center)
	if not sc_details.store_warehouse or not sc_details.wip_warehouse:
		frappe.throw("Service Center is missing Store or WIP Warehouse configuration.")

	# Create the Stock Entry
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.set("purpose", "Material Transfer") # ERPNext 14+
	se.from_warehouse = sc_details.store_warehouse
	se.to_warehouse = sc_details.wip_warehouse
	se.custom_repair_request = doc.name # Link it back

	# Add items
	total_issued = 0
	for item in doc.required_parts:
		if item.required_qty > item.issued_qty:
			qty_to_issue = item.required_qty - item.issued_qty

			# Check availability
			available_qty = get_item_availability(item.item_code, doc.service_center)
			if qty_to_issue > available_qty:
				frappe.throw(f"Not enough stock for {item.item_code}. Required: {qty_to_issue}, Available: {available_qty}")

			se.append("items", {
				"item_code": item.item_code,
				"qty": qty_to_issue,
				"s_warehouse": sc_details.store_warehouse,
				"t_warehouse": sc_details.wip_warehouse,
				"inventory_type": "Stock", # ERPNext 15+
				"reference_doctype": "Repair Request", # Link line item
				"reference_docname": doc.name # Link line item
			})
			total_issued += 1

	if total_issued == 0:
		frappe.throw("No parts to issue or all parts have already been issued.")

	# Save and return to client
	se.insert()
	frappe.db.commit()

	# Update status on Repair Request
	doc.status = "Parts Allocated"
	doc.add_log_entry(f"Stock Entry {se.name} created for parts transfer.")

	# Update issued qty (Ideally, this happens on Stock Entry submit, but for simplicity we do it here)
	for item in doc.required_parts:
		item.issued_qty = item.required_qty

	doc.save()

	# Notify technician
	doc.create_notification(
		user=doc.assigned_technician,
		subject=f"Parts for Repair {doc.name} have been allocated."
	)

	# Open the new Stock Entry for the user to submit
	frappe.response["open_doc"] = get_link_to_form("Stock Entry", se.name)


