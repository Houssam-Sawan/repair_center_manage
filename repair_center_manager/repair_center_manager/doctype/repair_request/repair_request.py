# Copyright (c) 2025, Houssam Sawan and contributors
# For license information, please see license.txt

from annotated_types import doc
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
	
	def validate(self):
		self.Validate_sn()
		self.log_status_change()
		if self.is_new():
			self.status = "Open"
		
		#if "Service Center Warehouse Manager" in frappe.get_roles(frappe.session.user) :
			#self.restrict_edits()
		#if self.status in ["In Progress","Pending Parts Allocation", "Pending for Spare Parts", "Parts Allocated"] and "Receptionist" in frappe.get_roles(frappe.session.user) :
			#self.restrict_edits_receptionist()
		#if self.status in ["Pending Parts Allocation", "Pending for Spare Parts", "Parts Allocated"] and "Technician" in frappe.get_roles(frappe.session.user) :
			#self.restrict_edits()		
		if self.status in ["Pending Parts Allocation", "Parts Allocated","Repaired", "Delivered", "Pending for Spare Parts"]:
			#self.restrict_edits()
			# Ensure at least one part is requested
			if not self.required_parts or len(self.required_parts) == 0:
				if self.resolution == "Parts Replacement":
					frappe.throw(_("Please add at least one required part before setting status to 'Pending Parts Allocation'."))

	def before_save(self):
		self.log_status_change()
		




	def on_submit(self):
		# Add any logic for on submit (if used)
		pass
	
	def on_update(self):
		self.handle_notifications()

	def Validate_sn(self):
		# IMEI/Serial Number validation
		if len(self.serial_no) < 11 and self.serial_no != "NA":
			frappe.throw(_("Invalid SN/IMEI number.\nMust be at least 11 characters or 'NA'."))
		
		# New IMEI/Serial Number validation for swapped devices
		if self.new_imei:
			if  self.resolution == "Swap" and self.status == "Swap Approved" and len(self.new_imei) < 11 :
				frappe.throw(_("Invalid SN/IMEI number.\nMust be at least 11 characters."))
				
	def restrict_edits(self):
		
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
		# 3. Status -> Any -> Assigned technichian changed notified
		if self.status in ["In Progress","Pending Parts Allocation", "Parts Allocated","Repaired", "Delivered", "Pending for Spare Parts"] :
			if self.get_doc_before_save().assigned_technician != self.assigned_technician:
				# Use the custom function to get users based on assignment DocType
				new_technician = self.assigned_technician
				self.create_notification(
					user=new_technician,
					subject=f"You have been assigned to Repair Request: {self.name}",
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
		notification.email_sent = 1
		notification.insert(ignore_permissions=True)
		frappe.db.commit() # Notifications need explicit commit



	def restrict_edits_role(self):
		# -------------------------------------------------
		# Basic guards
		# -------------------------------------------------
		if self.is_new():
			return

		user = frappe.session.user
		if user == "Administrator":
			return

		rules = get_edit_control_rules()
		status = self.status
		roles = set(frappe.get_roles(user))

		# -------------------------------------------------
		# 1️⃣ Fully locked status
		# -------------------------------------------------
		if status in rules["locked"]:
			frappe.throw(
				f"Document is locked in state <b>{status}</b>."
			)

		# -------------------------------------------------
		# 2️⃣ Full access role
		# -------------------------------------------------
		if roles & rules["full_access"].get(status, set()):
			return

		old = frappe.get_doc(self.doctype, self.name)
		meta = self.meta
		field_tab_map = get_field_tab_map(meta)

		skipped_parent = rules["skipped"]["parent"]
		skipped_child = rules["skipped"]["child"]

		# -------------------------------------------------
		# 3️⃣ Aggregate allowed permissions
		# -------------------------------------------------
		allowed_tabs = set()
		allowed_fields = set()
		allowed_child_fields = {}

		for role in roles:
			allowed_tabs |= rules["tabs"].get(status, {}).get(role, set())
			allowed_fields |= rules["fields"].get(status, {}).get(role, set())

			for parent, fields in rules["child_fields"].get(status, {}).get(role, {}).items():
				allowed_child_fields.setdefault(parent, set()).update(fields)

		# -------------------------------------------------
		# 4️⃣ Validate parent fields
		# -------------------------------------------------
		for field in meta.fields:
			fname = field.fieldname

			# Skip layout / system
			if field.fieldtype in ("Section Break", "Column Break"):
				continue

			if fname in skipped_parent:
				continue

			# -------------------------------------------------
			# Normal fields
			# -------------------------------------------------
			if field.fieldtype != "Table":
				if old.get(fname) != self.get(fname):
					tab = field_tab_map.get(fname)

					if (
						fname in allowed_fields or
						(tab and tab in allowed_tabs)
					):
						continue

					frappe.throw(
						f"You cannot modify <b>{field.label}</b> "
						f"in state <b>{status}</b>."
					)

			# -------------------------------------------------
			# Child tables
			# -------------------------------------------------
			else:
				validate_child_table(
					self=self,
					old=old,
					table_field=field,
					allowed_child_fields=allowed_child_fields,
					skipped_child=skipped_child,
					allowed_tabs=allowed_tabs,
					field_tab_map=field_tab_map,
					status=status
				)

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
	#doc.restrict_edits()  # Ensure no edits are made before requesting parts
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

	#Wdoc.restrict_edits()  # Ensure no edits are made before creating stock transfer
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
	se.set("purpose", "Material Transfer") #  ERPNext 14+
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
	doc.stock_transfer = se.name


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

	if doc.status != "Parts Allocated" and doc.resolution == "Parts Replacement":
		frappe.throw("Can only allocate parts when status is 'Parts Allocated'.")

	sc_details = frappe.get_doc("Service Center", doc.service_center)
	if not sc_details.store_warehouse or not sc_details.wip_warehouse:
		frappe.throw("Service Center is missing Store or WIP Warehouse configuration.")

	#doc.restrict_edits()  # Ensure no edits are made before completing repair
	# Update status on Repair Request
	doc.status = "Repaired"
	doc.add_log_entry(f"Repair marked as 'Repaired' by {frappe.session.user}.")
	doc.save()


@frappe.whitelist()
def complete_repair_without_parts(docname):
	"""
	Mark repair as 'Repaired' without parts replacement.
	Called from 'Complete Repair without Parts' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)

	if doc.status != "Parts Allocated" and doc.resolution == "Parts Replacement":
		frappe.throw("Can only allocate parts when status is 'Parts Allocated'.")
	

	if doc.status != "In Progress":
		frappe.throw("Can only complete repair when status is 'In Progress'.")

	#doc.restrict_edits()  # Ensure no edits are made before completing repair
	# Update status on Repair Request
	doc.status = "Repaired"
	if doc.resolution != "Parts replacement":
    	# This clears all rows in the child table if not parts are needed
		doc.set("required_parts", [])
    	
	doc.add_log_entry(f"Repair marked as 'Repaired' without parts by {frappe.session.user}.")
	doc.save()

#request_swap_approval: Request Swap approval from Brand manager
@frappe.whitelist()
def request_swap_approval(docname):
	doc = frappe.get_doc("Repair Request", docname)

	if not doc.brand_manager:
		frappe.throw("Please make sure to select correct brand manager")

	brand_manager = frappe.get_doc("Brand Manager", doc.brand_manager)
	#frappe.msgprint(_("Requesting swap approval from Brand Manager...{brand_manager.manager}"), alert=True)
		# Notify technician
	doc.create_notification(
		user=brand_manager.manager,
		subject=f"New Swap Request assigned: {doc.name} - Status set to Pending For Swap Approval.",
		channel="System Notification"
	)
	#Update the status to Pending For Swap Approval
	doc.status = "Pending For Swap Approval"
	doc.add_log_entry(f"Swap requested by {frappe.session.user}.")
	doc.save()


@frappe.whitelist()
def approve_swap(docname):
	doc = frappe.get_doc("Repair Request", docname)

	if doc.status != "Pending For Swap Approval":
		frappe.throw("Can only approve swap requests when status is 'Pending For Swap Approval'.")

	#Update the status to Swap Approved
	doc.status = "Swap Approved"
	doc.add_log_entry(f"Swap approved by {frappe.session.user}.")
	doc.save(ignore_permissions=True)

	# Notify technician
	doc.create_notification(
		user=doc.assigned_technician,
		subject=f"Swap Request approved: {doc.name} - Status set to In Progress.",
		channel="System Notification"
	)	

@frappe.whitelist()
def reject_swap(docname, reason):
	doc = frappe.get_doc("Repair Request", docname)

	if doc.status != "Pending For Swap Approval":
		frappe.throw("Can only reject swap requests when status is 'Pending For Swap Approval'.")

	#Update the status to In Progress
	doc.status = "In Progress"
	doc.add_comment(
		comment_type="Comment", 
		text=f"Swap Rejection Reason: {reason}"
	)
	doc.add_log_entry(f"Swap rejected by {frappe.session.user}. Reason: {reason}")
	doc.save(ignore_permissions=True)

	# Notify technician
	doc.create_notification(
		user=doc.assigned_technician,
		subject=f"Swap Request rejected: {doc.name} - Status set to Swap Rejected.",
		channel="System Notification"
	)


@frappe.whitelist()
def recieve_payment(docname):
	"""
	Set status to 'Paid' when the device is handed over to the customer.
	Called from 'Receive Payment' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	if doc.status != "Repaired":
		frappe.throw("Can only Pay when repair status is 'Repaired'.")
	
	if doc.total <= 0:
		frappe.throw("Total amount must be greater than zero to receive payment.")
	
	if doc.status == "Paid":
		frappe.throw("Payment has already been received for this repair.")
	
	# Create a Sales Invoice

	si = frappe.new_doc("Sales Invoice")
	si.customer = doc.customer
	sc_details = frappe.get_doc("Service Center", doc.service_center)
	si.company = sc_details.company
	si.posting_date = frappe.utils.nowdate()
	si.due_date = frappe.utils.nowdate()
	si.set_posting_time = 1
	si.custom_repair_request = doc.name

	for part in doc.required_parts:
		si.append("items", {
			"item_code": part.item_code,
			"qty": part.required_qty,
			"rate": part.price,
			"warehouse": sc_details.wip_warehouse
		})
	
	# Add labor charge as a separate item if applicable
	if doc.labor_charge and doc.labor_charge > 0:
		si.append("items", {
			"item_code": "Service Charge",  # Assuming a generic item for labor charge
			"qty": 1,
			"rate": doc.labor_charge,
			"warehouse": sc_details.wip_warehouse
		})

	si.insert(ignore_permissions=True)
	si.submit()

	# Create Payment Entry
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.posting_date = frappe.utils.nowdate()
	pe.mode_of_payment = sc_details.mode_of_payment
	pe.party_type = "Customer"
	pe.party = doc.customer
	pe.company = sc_details.company
	pe.paid_amount = doc.total
	pe.received_amount = doc.total
	pe.base_paid_amount = doc.total
	pe.base_received_amount = doc.total
	pe.target_exchange_rate = 1
	pe.source_exchange_rate = 1
	pe.paid_to = sc_details.default_cash_account
	pe.paid_to_account_currency = frappe.db.get_value("Account", sc_details.default_cash_account, "account_currency")
	#pe.custom_repair_request = doc.name

	pe.append("references", {
		"reference_doctype": "Sales Invoice",
		"reference_name": si.name,
		"total_amount": si.grand_total,
		"outstanding_amount": si.outstanding_amount,
		"allocated_amount": doc.total
	})

	pe.insert(ignore_permissions=True)
	pe.submit()


	# Update Repair Request
	doc.sales_invoice = si.name
	doc.payment_entry = pe.name
	doc.status = "Paid"
	doc.add_log_entry(f"Payment Recieved by {frappe.session.user}.")
	doc.save(ignore_permissions=True)

	return {
		"invoice": si.name,
		"payment": pe.name
	}

@frappe.whitelist()
def deliver_to_customer(docname):
	"""
	Set status to 'Delivered' when the device is handed over to the customer.
	Called from 'Deliver to Customer' button.
	"""
	doc = frappe.get_doc("Repair Request", docname)
	
	
	# Clear Spare Parts table
	if doc.resolution != "Parts replacement":
		
		doc.set("required_parts", [])

	doc.status = "Delivered"
	doc.add_log_entry("Device delivered to customer.")
	doc.save(ignore_permissions=True)
	doc.submit()

	frappe.msgprint(_("Device marked as 'Delivered'."), alert=True)


@frappe.whitelist()
#@frappe.cache()
def get_edit_control_rules():
    settings = frappe.get_single("Document Edit Control Settings")

    rules = {
        "locked": set(),
        "full_access": {},
        "tabs": {},
        "fields": {},
        "child_fields": {},
        "skipped": {
            "parent": set(),
            "child": {}
        }
    }

    for r in settings.status_lock_rules:
        if r.fully_locked:
            rules["locked"].add(r.status)

    for r in settings.full_access_role_rules:
        rules["full_access"].setdefault(r.status, set()).add(r.role)

    for r in settings.tab_edit_rules:
        rules["tabs"].setdefault(r.status, {}).setdefault(r.role, set()).add(r.section_break)

    for r in settings.field_edit_rules:
        rules["fields"].setdefault(r.status, {}).setdefault(r.role, set()).add(r.fieldname)

    for r in settings.child_field_edit_rules:
        rules["child_fields"]\
            .setdefault(r.status, {})\
            .setdefault(r.role, {})\
            .setdefault(r.parent_fieldname, set())\
            .add(r.child_fieldname)

    for r in settings.skipped_fields:
        if r.is_child:
            rules["skipped"]["child"]\
                .setdefault(r.parent_fieldname, set())\
                .add(r.fieldname)
        else:
            rules["skipped"]["parent"].add(r.fieldname)

    return rules


@frappe.whitelist()
def validate_child_table(
    self,
    old,
    table_field,
    allowed_child_fields,
    skipped_child,
    allowed_tabs,
    field_tab_map,
    status
):
    parent_field = table_field.fieldname
    tab = field_tab_map.get(parent_field)

    # Allow entire table via tab permission
    if tab and tab in allowed_tabs:
        return

    old_rows = {r.name: r for r in old.get(parent_field) or []}

    for row in self.get(parent_field) or []:
        old_row = old_rows.get(row.name)

        # Block row add/remove unless explicitly allowed
        if not old_row:
            frappe.throw(
                f"Adding rows to <b>{table_field.label}</b> "
                f"is not allowed in state <b>{status}</b>."
            )

        meta = frappe.get_meta(row.doctype)

        for f in meta.fields:
            cf = f.fieldname

            if f.fieldtype in ("Section Break", "Column Break"):
                continue

            if cf in skipped_child.get(parent_field, set()):
                continue

            if old_row.get(cf) != row.get(cf):
                if cf in allowed_child_fields.get(parent_field, set()):
                    continue

                frappe.throw(
                    f"You cannot modify <b>{table_field.label} → {f.label}</b> "
                    f"in state <b>{status}</b>."
                )


@frappe.whitelist()
def get_field_tab_map(meta):
    """
    Returns:
    {
        fieldname: tab_fieldname
    }
    """
    tab_map = {}
    current_tab = None

    for field in meta.fields:
        if field.fieldtype == "Section Break":
            current_tab = field.fieldname
        elif field.fieldtype not in ("Column Break"):
            tab_map[field.fieldname] = current_tab

    return tab_map


@frappe.whitelist()
def get_client_edit_matrix(doctype, docname):
    doc = frappe.get_doc(doctype, docname)
    user = frappe.session.user

    if user == "Administrator":
        return {"full_access": True}

    rules = get_edit_control_rules()
    status = doc.status
    roles = set(frappe.get_roles(user))

    if status in rules["locked"]:
        return {"locked": True}

    if roles & rules["full_access"].get(status, set()):
        return {"full_access": True}

    # Aggregate permissions (same logic as validator)
    allowed_tabs = set()
    allowed_fields = set()
    allowed_child_fields = {}

    for role in roles:
        allowed_tabs |= rules["tabs"].get(status, {}).get(role, set())
        allowed_fields |= rules["fields"].get(status, {}).get(role, set())
        for parent, fields in rules["child_fields"].get(status, {}).get(role, {}).items():
            allowed_child_fields.setdefault(parent, set()).update(fields)

    return {
        "allowed_tabs": list(allowed_tabs),
        "allowed_fields": list(allowed_fields),
        "allowed_child_fields": {
            k: list(v) for k, v in allowed_child_fields.items()
        }
    }
