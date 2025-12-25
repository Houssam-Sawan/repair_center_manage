# Copyright (c) 2025, Houssam Sawan and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint, throw
from frappe.utils import get_link_to_form
from frappe.model.document import Document
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)


class RepairRequest(Document):
	# who can edit what in each workflow status
	EDIT_RULES = {
		"Technician": {
			"In Progress": ["required_parts", "fault_category", "fault_description", "repair_notes"],
			"Parts Allocated": [],
			"Pending Parts Allocation": [],
		},
		"Receptionist": {
			"Pending Parts Allocation": ["approval_comment"],
		},
		"Service Center Warehouse Managerr": {
			"Pending Parts Allocation": ["approval_comment"],
			"Parts Allocated": ["custom_notes"],
		},
		"SC Manager": {
			"Pending Parts Allocation": ["approval_comment"],
			"Parts Allocated": ["custom_notes"],
		},
		"Administrator": "__all__",  # can edit anything
	}

	def restrict_edits_role(self):
		"""Restrict edits based on workflow status and role-based field permissions."""
        # Skip check for new documents
		if self.is_new():
			return

        # Get user roles and workflow status
		user_roles = frappe.get_roles(frappe.session.user)
		status = self.status

        # Superuser bypass
		if frappe.session.user == "Administrator":
			return

        # Get old document for comparison
		old_doc = frappe.get_doc(self.doctype, self.name)
		changed_fields = []

        # Determine editable fields for this role and status
		editable_fields = []
		for role in user_roles:
			rules = self.EDIT_RULES.get(role)
			if not rules:
				continue
			if rules == "__all__":
				return  # full access
			if status in rules:
				editable_fields.extend(rules[status])

        # If no rule matches → block all edits
		if not editable_fields:
			editable_fields = []

		for field in self.meta.fields:
            # Skip automatically updated or system fields
			if field.fieldname in ("modified", "modified_by", "owner", "creation", "idx"):
				continue

            # Skip read-only or hidden fields (UI restrictions)
			if field.read_only or field.hidden:
				continue

            # Handle normal fields
			if field.fieldtype != "Table":
				old_value = old_doc.get(field.fieldname)
				new_value = self.get(field.fieldname)
				if old_value != new_value and field.fieldname not in editable_fields:
					changed_fields.append(field.label or field.fieldname)
			else:
                # Handle child tables
				for d_new in self.get(field.fieldname) or []:
					if not d_new.name:
						continue  # skip new rows (if not allowed, you can block instead)
					d_old = frappe.get_doc(d_new.doctype, d_new.name)
					child_meta = frappe.get_meta(d_new.doctype)
					for cfield in child_meta.fields:
						if cfield.fieldname in ("modified", "owner", "idx"):
							continue
						old_value = d_old.get(cfield.fieldname)
						new_value = d_new.get(cfield.fieldname)
						if old_value != new_value and field.fieldname not in editable_fields:
							changed_fields.append(f"{field.label} → {cfield.label}")

        # If any restricted fields changed → throw error
		if changed_fields:
			frappe.throw(
                f"You cannot modify this document in state <b>{status}</b>.<br>"
                f"Changed fields: {', '.join(changed_fields)}",
                title="Edit Restricted"
            )
			

	def validate(self):
		self.Validate_sn()
		self.log_status_change()
		if self.is_new():
			self.status = "Open"
		
		if "Service Center Warehouse Manager" in frappe.get_roles(frappe.session.user) :
			self.restrict_edits()
		if self.status in ["In Progress","Pending Parts Allocation", "Pending for Spare Parts", "Parts Allocated"] and "Receptionist" in frappe.get_roles(frappe.session.user) :
			self.restrict_edits_receptionist()
		if self.status in ["Pending Parts Allocation", "Pending for Spare Parts", "Parts Allocated"] and "Technician" in frappe.get_roles(frappe.session.user) :
			self.restrict_edits()		
		if self.status in ["Pending Parts Allocation", "Parts Allocated","Repaired", "Delivered", "Pending for Spare Parts"]:
			self.restrict_edits()
			# Ensure at least one part is requested
			if not self.required_parts or len(self.required_parts) == 0:
				frappe.throw(_("Please add at least one required part before setting status to 'Pending Parts Allocation'."))

	def before_save(self):
		self.log_status_change()
		




	def on_submit(self):
		# Add any logic for on submit (if used)
		pass
	
	def on_update(self):
		self.handle_notifications()

	def Validate_sn(self):
		# Example validation: Serial number should not be "12345"
		if len(self.serial_no) < 11 and self.serial_no != "NA":
			frappe.throw(_("Invalid SN/IMEI number.\nMust be at least 11 characters or 'NA'."))

	def restrict_edits(self):
		"""Prevent field edits after certain workflow states or by specific roles."""
		if self.status in ["Pending Parts Allocation", "Parts Allocated", "Repaired", "Delivered", "Pending for Spare Parts"]:
            # Bypass for managers or admins
			if "SC Manager" not in frappe.get_roles(frappe.session.user) and not frappe.session.user == "Administrator":
                # Compare current values with database values
				if not self.is_new():
					old_doc = frappe.get_doc(self.doctype, self.name)
					changed_fields = []
                    
					for field in self.meta.fields:
						# Skip automatically updated system fields
						# if field.fieldname in ("modified", "modified_by", "owner"):
						# continue
						if field.read_only or field.hidden:
							continue

						old_value = old_doc.get(field.fieldname)
						new_value = self.get(field.fieldname)
						
						if old_value != new_value:
							changed_fields.append(field.label or field.fieldname)
					if changed_fields:
						frappe.throw(
                            f"You cannot modify this document in state <b>{self.status}</b>. "
                            f"Changed fields: {', '.join(changed_fields)}"
                        )

	def restrict_edits_receptionist(self):
		"""Prevent field edits after certain workflow states or by specific roles."""
		if self.status in ["In Progress", "Pending Parts Allocation", "Parts Allocated","Repaired", "Delivered", "Pending for Spare Parts"]:
            # Bypass for managers or admins
			if "SC Manager" not in frappe.get_roles(frappe.session.user) and not  "Technician" not in frappe.get_roles(frappe.session.user) and not frappe.session.user == "Administrator":
                # Compare current values with database values
				if not self.is_new():
					old_doc = frappe.get_doc(self.doctype, self.name)
					changed_fields = []
                    
					for field in self.meta.fields:
						# Skip automatically updated system fields
						# if field.fieldname in ("modified", "modified_by", "owner"):
						# continue
						if field.read_only or field.hidden:
							continue

						old_value = old_doc.get(field.fieldname)
						new_value = self.get(field.fieldname)
						
						if old_value != new_value:
							changed_fields.append(field.label or field.fieldname)
					if changed_fields:
						frappe.throw(
                            f"You cannot modify this document in state <b>{self.status}</b>. "
                            f"Changed fields: {', '.join(changed_fields)}"
                        )

	def validate_Inprogress(self):
		# Example validation: Ensure assigned technician is set when status is In Progress
		if not self.assigned_technician:
			frappe.throw(_("Assigned Technician must be set when status is 'In Progress'."))
		if not self.fault_category or not self.fault_description:
			frappe.throw(_("Please provide the Fault Category and Fault Description before requesting parts."))

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
					subject=f"Repair {self.name} is complete and ready for delivery.",
					channel="System Notification"
				)

		# 2. Status -> Pending Parts -> Notify Warehouse Manager
		if self.get_doc_before_save() and self.get_doc_before_save().status != 'Pending Parts Allocation' and self.status == 'Pending Parts Allocation':
			# Use the custom function to get users based on assignment DocType
			warehouse_managers = self.get_users_by_role_and_service_center('Service Center Warehouse Manager', self.service_center)
			for user in warehouse_managers:
				self.create_notification(
					user=user,
					subject=f"Spare parts requested for Repair: {self.name}",
					channel="System Notification"
				)
	def get_users_by_role_and_service_center(self, role, service_center):
		"""
		Fetches list of users with a specific role at a specific service center
		by querying the Service Center Assignment DocType.
		"""
		users_with_role = frappe.get_all(
			"Has Role",
			filters={"role": role},
			pluck="parent"
    	)
		# 1. Get Users assigned to this Service Center
		assigned_users = frappe.get_all(
			"Service Center Assignment",
			filters={"service_center": service_center,
				 "user": ["in", users_with_role]},
			pluck="user"
		)

		# 2. Filter these users by the required Role
		return frappe.get_all(
			"User",
			filters={
				"name": ("in", assigned_users),
				"Enabled": 1,
			},
			pluck="name"
		)

	@frappe.whitelist()
	def test():
		frappe.msgprint("Test function called successfully.")


	def create_notification(self, user, subject, doc=None, channel="System Notification"):
		"""Helper to create a standard Notification Log."""
		if not doc:
			doc = self

		notification = frappe.new_doc("Notification Log")
		notification.for_user = user
		notification.subject = subject
		notification.document_type = doc.doctype
		notification.document_name = doc.name
		notification.channel = channel
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
		subject=f"New Repair Request assigned: {doc.name} - Status set to In Progress.",
		channel="System Notification"
	)

	frappe.msgprint(_(f"Repair successfully assigned to {doc.assigned_technician} and started."), alert=True)


@frappe.whitelist()
def get_item_availability(item_code, service_center, warehouse_type="store_warehouse"):
	"""
	Checks the available quantity of an item in the service center's main store.
	"""
	if not service_center:
		return 0

	# Get the warehouse associated with the service center
	warehouse = frappe.db.get_value("Service Center", service_center, warehouse_type)
	if not warehouse:
		frappe.throw(f"No {warehouse_type} configured for Service Center: {service_center}")
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
def get_item_cost_price(item_code, service_center, warehouse_type="store_warehouse"):
	"""
	Checks the cost price (Valuation Rateof an item in the service center's main store.
	"""
	if not service_center:
		return 0

	# Get the warehouse associated with the service center
	warehouse = frappe.db.get_value("Service Center", service_center, warehouse_type)
	if not warehouse:
		frappe.throw(f"No {warehouse_type} configured for Service Center: {service_center}")
		return 0

	try:
		qty = frappe.db.sql(f"""
			SELECT `valuation_rate`
			FROM `tabBin`
			WHERE `item_code` = %s AND `warehouse` = %s
		""", (item_code, warehouse))

		return qty[0][0] if qty else 0

	except Exception as e:
		frappe.log_error(f"Error fetching stock for {item_code} in {warehouse}: {e}")
		return 0

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_technicians_by_service_center(doctype, txt, searchfield, start, page_len, filters):
	"""
	Whitelisted function to filter Technicians for the assigned_technician link field.
	This replaces the standard frappe.set_query logic which is less flexible for joins.
	"""
	search_service_center = filters.get("search_service_center") if filters else None
	users_with_role = frappe.get_all(
        "Has Role",
        filters={"role": "Technician"},
        pluck="parent"
    )

	if not users_with_role:
		return []
	
	# 1. Get users linked to the specified service_center
	assigned_users = frappe.get_all(
		"Service Center Assignment",
		filters={"service_center": search_service_center ,
				 "user": ["in", users_with_role]},
		pluck="name"
	) 	

	if not assigned_users:
		return []

	# 2. Filter these assigned users by role 'Technician' and search text (txt)
	users = frappe.get_all(
		"User",
		filters={
			"name": ("in", assigned_users),
			"Enabled": 1,
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
	frappe.msgprint(_("Requesting parts..."), alert=True)
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "In Progress":
		frappe.throw("Can only request parts when repair is 'In Progress'.")
	doc.restrict_edits()  # Ensure no edits are made before requesting parts
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
		subject=f"Repair {doc.name} is 'Pending for Spare Parts' from main.",
		channel="System Notification"
	)

	# Suggest creating a Material Request
	frappe.msgprint(_("Status set to 'Pending for Spare Parts'. Please create a Material Request to the Main Warehouse."), alert=True)

@frappe.whitelist()
def mark_spart_parts_received(docname):
	"""
	Set status to 'In Progress' and notify technician.
	Called from 'Mark Parts Received' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "Pending for Spare Parts":
		frappe.throw("Can only mark parts received when status is 'Pending for Spare Parts'.")

	doc.status = "Pending Parts Allocation"
	doc.add_log_entry("Parts received and status set back to 'Pending Parts Allocation'.")
	doc.save()


	frappe.msgprint(_("Status set back to 'Pending Parts Allocation'."), alert=True)

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

	doc.restrict_edits()  # Ensure no edits are made before creating stock transfer
	existing = frappe.db.exists("Stock Entry", {"custom_repair_request": doc.name})
	if existing:
		
		link = get_link_to_form("Stock Entry", existing)
		frappe.msgprint(f"Material Transfer already exists: {link}")
		# Update status on Repair Request
		doc.status = "Parts Allocated"
		doc.add_log_entry(f"Stock Entry {link} created for parts transfer.")

		# Update issued qty (Ideally, this happens on Stock Entry submit, but for simplicity we do it here)
		for item in doc.required_parts:
			item.issued_qty = item.required_qty

		doc.save()

	# Notify technician
		doc.create_notification(
			user=doc.assigned_technician,
			subject=f"Parts for Repair {doc.name} have been allocated.",
			channel="System Notification"
		)
		return
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
			available_qty = get_item_availability(item.item_code, doc.service_center, "store_warehouse")
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
	se.insert(ignore_permissions=True)
	se.submit()
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
		subject=f"Parts for Repair {doc.name} have been allocated.",
		channel="System Notification"
	)

	# Open the new Stock Entry for the user to submit
	frappe.response["open_doc"] = get_link_to_form("Stock Entry", se.name)

@frappe.whitelist()
def complete_repair(docname):
	"""
	Creates and returns a new Stock Entry (Material Issue)
	for the warehouse manager to fulfill.
	"""
	doc = frappe.get_doc("Repair Request", docname)

	if doc.status != "Parts Allocated":
		frappe.throw("Can only allocate parts when status is 'Parts Allocated'.")

	sc_details = frappe.get_doc("Service Center", doc.service_center)
	if not sc_details.store_warehouse or not sc_details.wip_warehouse:
		frappe.throw("Service Center is missing Store or WIP Warehouse configuration.")

	doc.restrict_edits()  # Ensure no edits are made before creating stock transfer
	existing = frappe.db.exists("Stock Entry", {"stock_entry_type":"Material Issue","custom_repair_request": doc.name})
	if existing:
		
		link = get_link_to_form("Stock Entry", existing)
		frappe.msgprint(f"Material issue already exists: {link}")
		# Update status on Repair Request
		doc.status = "Repaired"
		doc.add_log_entry(f"Stock Entry {link} created for parts transfer.")
		doc.save()

	# Create the Stock Entry
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Issue"
	se.set("purpose", "Material Issue") # ERPNext 14+
	se.from_warehouse = sc_details.wip_warehouse
	se.custom_repair_request = doc.name # Link it back

	# Add items
	total_issued = 0
	for item in doc.required_parts:
		qty_to_issue = item.issued_qty

		# Check availability
		available_qty = get_item_availability(item.item_code, doc.service_center,"wip_warehouse")
		if qty_to_issue > available_qty:
			frappe.throw(f"Not enough stock for {item.item_code}. Required: {qty_to_issue}, Available: {available_qty}")

		se.append("items", {
			"item_code": item.item_code,
			"qty": qty_to_issue,
			"s_warehouse": sc_details.wip_warehouse,
			#"t_warehouse": sc_details.wip_warehouse,
			"inventory_type": "Stock", # ERPNext 15+
			"reference_doctype": "Repair Request", # Link line item
			"reference_docname": doc.name # Link line item
		})
		total_issued += 1

	if total_issued == 0:
		frappe.throw("No parts to issue or all parts have already been issued.")
	# Save and return to client
	se.insert(ignore_permissions=True)
	se.submit()
	# Update status on Repair Request
	doc.status = "Repaired"
	doc.add_log_entry(f"Stock Entry {se.name} created for parts Consumption.")

	doc.save()

@frappe.whitelist()
def deliver_to_customer(docname):
	"""
	Set status to 'Paid' when the device is handed over to the customer.
	Called from 'Receive Payment' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "Repaired":
		frappe.throw("Can only Pay when repair status is 'Repaired'.")

	doc.status = "Paid"
	doc.add_log_entry("Payment Recieved")
	doc.save(ignore_permissions=True)

@frappe.whitelist()
def deliver_to_customer(docname):
	"""
	Set status to 'Delivered' when the device is handed over to the customer.
	Called from 'Deliver to Customer' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "Paid":
		frappe.throw("Can only deliver when repair status is 'Paid'.")

	doc.status = "Delivered"
	doc.add_log_entry("Device delivered to customer.")
	doc.save(ignore_permissions=True)
	doc.submit()

	frappe.msgprint(_("Device marked as 'Delivered'."), alert=True)


