import time

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RichLog, Static, Switch

from device_managers.device_manager_bronkhorst import DeviceManager
from ui.custom_progress_bar import ProgressBar as CustomProgressBar

"""
Textual TUI widget for Bronkhorst flow meter control and monitoring.
"""

class MFCModule(Widget):
	CSS_PATH = "CSS_main.tcss"
	
	# Reactive properties to track state
	armed = reactive(False)
	set_percentage = reactive(0.00)
	current_percentage = reactive(0.00)
	current_valve = reactive(0.00)
	temperature = reactive(0.00)
	flowrate = reactive(0.00)
	
	def __init__(self, mfc_serial: str) -> None:
		super().__init__()
		self.manager = DeviceManager.get_instance()
		self.device_db = self.manager.device_db  # Access the device database
		self.mfc_serial = mfc_serial  # Serial number of the MFC
		self.mfc_data = self.device_db[
			mfc_serial
		]  # Get MFC data from the database according to serial number
		self.mfc_bundle = self.mfc_data.bundle  # Tag of the MFC
		self.mfc_fluid = self.mfc_data.user_fluid  # Target fluid of the MFC
		self.mfc_unit = "m3n/h"  # Unit of the MFC
		self.mfc_capacity = self.mfc_data.m3n_h_capacity  # Max capacity of the MFC
		
		self.is_input_percent = False  # Flag to check if input is in percent
	
	def log_message(self, message: str) -> None:
		"""Send log messages to the parent BronkhorstWidget"""
		# Find the parent BronkhorstWidget
		parent = self.app.query_one(BronkhorstWidget)
		parent.log_message(f"[{self.mfc_serial}] {message}")
	
	def compose(self) -> ComposeResult:
		container = Container(classes="mfc-container")
		container.border_title = (
				self.mfc_serial
				+ " - "
				+ self.mfc_bundle
				+ " - "
				+ self.mfc_fluid
				+ " - "
				+ str(self.mfc_capacity)
				+ " - "
				+ self.mfc_unit
		)
		
		flow_label = Label("NaN", id="flow_label", classes="flow_label")
		flow_label.border_title = self.mfc_unit
		
		temp_label = Label("NaN", id="temperature_label", classes="temperature_label")
		temp_label.border_title = "degC"
		
		with container:
			with Horizontal():
				# Arming Switch
				yield Switch(
						value=False,
						id="mfc_arm_switch",
						tooltip="Arm MFC",
						classes="mfc_arm_switch",
				)
				
				with Vertical(classes="progress_label_container"):
					yield Static("User Setpoint :", classes="progress_labels")
					yield Static("Measured Flow :", classes="progress_labels")
					yield Static("Valve Position:", classes="progress_labels")
				
				# Progress bars for set and actual opening percentage
				with Vertical(classes="progress_bars"):
					yield CustomProgressBar(
							total=100.00,
							show_eta=False,
							id="set_percent_bar",
							classes="mfc_progress_bar",
					)
					
					yield CustomProgressBar(
							total=100.00,
							show_eta=False,
							id="real_percent_bar",
							classes="mfc_progress_bar",
					)
					
					yield CustomProgressBar(
							total=100.00,
							show_eta=False,
							id="valve_percent_bar",
							classes="mfc_progress_bar",
					)
				
				yield flow_label
				# yield temp_label
				
				# Input field for setting MFC opening percentage
				yield Input(
						placeholder="m3n/h",
						id="flow_input",
						tooltip="Set MFC flow rate",
						classes="mfc_input disabled-input",
						type="text",
						validate_on=["submitted"],
				)
				
				# yield Input(
				# 		placeholder="%",
				# 		id="percent_input",
				# 		tooltip="Set MFC flow percentage",
				# 		classes="mfc_input disabled-input",
				# 		type="number",
				# 		validate_on=["submitted"],
				# )
				#
				# Send button
				yield Button(
						"Send",
						id="send_button",
						tooltip="Send MFC opening percentage",
						variant="success",
						classes="mfc_button disabled-button",
				)
		
		# Wink wink
		# yield Button("Blink", id="wink_button", tooltip="Wink", variant="primary", classes="wink_button")
	
	def on_mount(self) -> None:
		"""Initialize widget state when mounted"""
		# Set progress bars to initial values
		self.query_one("#set_percent_bar", CustomProgressBar).progress = float(
				self.set_percentage
		)
		self.query_one("#real_percent_bar", CustomProgressBar).progress = (
				self.current_percentage
		)
		self.query_one("#valve_percent_bar", CustomProgressBar).progress = (
				self.current_valve
		)
		
		# self.log_message(
		# 		"Pulled from database:"
		# 		+ " Max Capacity: "
		# 		+ str(self.mfc_capacity)
		# 		+ " "
		# 		+ self.mfc_unit
		# )
	
	@on(Switch.Changed, "#mfc_arm_switch")
	def handle_arm_switch(self, event: Switch.Changed) -> None:
		"""Handle arming switch changes"""
		self.armed = event.value
		
		# Enable/disable the input and button based on armed state
		input_field = self.query_one("#flow_input", Input)
		send_button = self.query_one("#send_button", Button)
		arm_switch = self.query_one("#mfc_arm_switch", Switch)
		
		if self.armed:
			input_field.remove_class("disabled-input")
			send_button.remove_class("disabled-button")
			send_button.disabled = False
			arm_switch.add_class("switch_armed")
			self.log_message("Armed")
		
		if not self.armed:
			if self.manager.is_connected:
				self.manager.write_setpoint_manual(self.mfc_serial, 0)
			else:
				self.log_message("MFC not connected")
			
			input_field.add_class("disabled-input")
			send_button.add_class("disabled-button")
			send_button.disabled = True
			arm_switch.remove_class("switch_armed")
			self.log_message("Disarmed")
			input_field.value = ""
	
	# ──────────────────────────────────────────────────────────────────────────────
	# INPUT VALIDATION
	# ──────────────────────────────────────────────────────────────────────────────
	@on(Input.Changed, "#flow_input")
	def validate_input(self, event: Input.Changed) -> None:
		"""Validate user input, supporting both absolute flow-rate and % modes."""
		self.is_input_percent = False
		
		# Make a local copy and trim whitespace at once
		raw_value = event.value.strip()
		
		try:
			# ── Percentage mode ────────────────────────────────────────────────
			if raw_value.startswith("%"):
				self.is_input_percent = True
				percent_str = raw_value.lstrip("%").strip()
				
				# Allow the user to type '%' and continue editing
				if percent_str in ("", "."):
					return
				
				percent_val = float(percent_str)
				if not 0 <= percent_val <= 100:
					self.log_message("Invalid percentage: must be 0–100 %.")
					event.input.value = "%"
					return
				
				# Update progress-bar directly with percentage
				self.set_percentage = f"{percent_val:.2f}"
				self.query_one("#set_percent_bar", CustomProgressBar).progress = percent_val
				return  # Nothing more to do in % mode
			
			# ── Absolute flow-rate mode ────────────────────────────────────────
			if raw_value in ("", "."):
				return  # User is still typing
			
			flow_val = float(raw_value)
			if not 0 <= flow_val <= self.mfc_capacity:
				self.log_message(
						f"Invalid value: {flow_val}. Must be between 0 and {self.mfc_capacity}."
				)
				event.input.value = ""
				return
			
			percentage = (flow_val / self.mfc_capacity) * 100.0
			self.set_percentage = f"{percentage:.2f}"
			self.query_one("#set_percent_bar", CustomProgressBar).progress = percentage
		
		except ValueError:
			# Not a valid number → clear the field
			event.input.value = ""
	
	# ──────────────────────────────────────────────────────────────────────────────
	# SEND BUTTON HANDLER
	# ──────────────────────────────────────────────────────────────────────────────
	@on(Button.Pressed, "#send_button")
	def send_flowrate(self) -> None:
		"""Send the user-entered set-point to the device."""
		if not self.armed:
			self.notify("MFC is not armed.", severity="warning")
			return
		
		input_field = self.query_one("#flow_input", Input)
		raw_value = input_field.value.strip()
		
		try:
			# Decide which mode we are in
			if self.is_input_percent or raw_value.startswith("%"):
				percent_val = float(raw_value.lstrip("%").strip())
				self.manager.write_setpoint_manual(
						self.mfc_serial, percent_val, is_percentage=True
				)
			else:
				flow_val = float(raw_value)
				self.manager.write_setpoint_manual(
						self.mfc_serial, flow_val, is_percentage=False
				)
		
		except ValueError:
			self.notify("Invalid input – please enter a number or %value.", severity="warning")
		except Exception as e:
			self.log_message(f"Error sending flow rate: {e}")
	
	# @on(Input.Changed, "#flow_input")
	# def validate_input(self, event: Input.Changed) -> None:
	# 	"""Validate and update percentage input"""
	# 	self.is_input_percent = False
	# 	try:
	# 		value = event.value
	#
	# 		# Check if the value starts with % character
	# 		if value.startswith("%"):
	# 			self.is_input_percent = True
	#
	# 			# implement seperate logic
	#
	# 		else:
	# 			is_value_percent = False
	#
	# 		value = float(value)
	# 		if value < 0 or value > self.mfc_capacity:
	# 			self.log_message(
	# 					f"Invalid value: {value}. Must be between 0 and {self.mfc_capacity}."
	# 			)
	# 			event.input.value = ""
	#
	# 		percentage = value / self.mfc_capacity * 100.00
	# 		# Update the set percentage bar to reflect input value
	# 		self.set_percentage = str(percentage)
	# 		self.query_one("#set_percent_bar", CustomProgressBar).progress = float(
	# 				self.set_percentage
	# 		)
	#
	# 	except ValueError:
	# 		# If not a valid number, reset to 0
	# 		event.input.value = ""
	#
	# @on(Button.Pressed, "#send_button")
	# def send_flowrate(self) -> None:
	# 	"""Send the percentage to the device"""
	# 	if not self.armed:
	# 		self.notify("MFC is not armed.", severity="warning")
	# 		return
	#
	# 	try:
	# 		# Get the percentage from the input field
	# 		input_field = self.query_one("#flow_input", Input)
	#
	# 		flowrate = float(input_field.value)
	#
	# 		self.manager.write_setpoint_manual(self.mfc_serial, flowrate)
	#
	# 	except Exception as e:
	# 		self.log_message(f"Error sending flow rate: {e}")
	
	@on(Button.Pressed, "#wink_button")
	def blink(self) -> None:
		"""Wink wink"""
		try:
			self.manager.blink(self.mfc_serial)
		except Exception as e:
			self.log_message(f"Error during blinking: {e}")
	
	def update_measurement_display(self) -> None:
		try:
			if self.mfc_serial in self.manager.data_package:
				device_data = self.manager.data_package[self.mfc_serial]
				
				# Update progress bars and labels with the data
				self.current_percentage = device_data["measure"] / self.mfc_capacity
				self.current_valve = device_data["valve_output"] * 100
				self.temperature = f"{device_data['temperature']:.2f}"
				self.flowrate = f"{device_data['measure']:.5f}"
				
				# Update UI elements
				self.query_one("#real_percent_bar", CustomProgressBar).progress = (
						self.current_percentage
				)
				self.query_one("#valve_percent_bar", CustomProgressBar).progress = (
						self.current_valve
				)
				# self.query_one("#temperature_label", Label).update(self.temperature)
				self.query_one("#flow_label", Label).update(self.flowrate)
		
		except Exception as e:
			if self.manager.is_connected:
				self.log_message(f"Error updating display: {e}")


class BronkhorstWidget(Widget):
	CSS_PATH = "CSS_main.tcss"
	
	def __init__(self) -> None:
		super().__init__()
		self.manager = DeviceManager.get_instance()
		self.device_db = self.manager.device_db  # Access the device database
	
	def compose(self) -> ComposeResult:
		# MFC modules container
		mfc_box = Container(id="MFC_BOX")
		mfc_box.border_title = ""
		
		with mfc_box:
			for devices in self.device_db:
				device_serial = self.device_db[devices].serial
				yield MFCModule(mfc_serial=device_serial)
	
	def on_mount(self) -> None:
		"""Initialize widget state when mounted"""
	
	# TODO: Implement connection monitoring
	# TODO: Implement polling indicator
	# TODO: Add disconnection handling
	# TODO: Add abort button functionality
	
	@on(Button.Pressed, "#connect_button")
	def connect(self) -> None:
		self.log_message("Attempting to connect...")
		
		try:
			# Call init_sequence and let exceptions propagate
			self.manager.init_sequence()
			self.log_message(
					f"Connected to {len(self.manager.connected_devices)} device(s)"
			)
			self.log_message(
					"Connected devices: " + str(self.manager.connected_devices)
			)
			self.measurement_package_updates()
			
			if self.manager.disconnected_devices is not None:
				self.log_message(
						"Unable to connect to: " + str(self.manager.disconnected_devices)
				)
		
		except ConnectionError as e:
			# Handle the specific error with the original message
			self.log_message(f"{e}")
		except Exception as e:
			# Handle any other unexpected exceptions
			self.log_message(f"Connection error wid: {e}")
	
	@on(Button.Pressed, "#abort_button")
	def abort(self) -> None:
		self.log_message(time.strftime("%H:%M:%S") + " Aborting...")
		
		try:
			
			for aborted_device in self.manager.connected_devices:
				self.manager.write_setpoint_manual(aborted_device.get("serial"), 0)
				self.log_message(f"Setpoint for {aborted_device} set to 0.")
			
			# Update the arm switch reactives for all MFC modules
			for mfc in self.query(MFCModule):
				# Update the reactive property
				mfc.armed = False
				
				arm_switch = mfc.query_one("#mfc_arm_switch", Switch)
				arm_switch.value = False
			
			self.manager.stop()
			self.log_message("Disconnected.")
		
		except Exception as e:
			self.log_message(f"Error during disconnect: {e}")
	
	def log_message(self, message: str) -> None:
		"""Log messages from child widgets to the central log"""
		self.app.query_one("#connection_logs", RichLog).write(
				f"{time.strftime('%H:%M:%S')} {message}"
		)
	
	def measurement_package_updates(self) -> None:
		"""Handle multiple read requests for multiple devices in one go"""
		try:
			# Read multiple parameters from the device
			if self.manager.is_connected:
				self.set_interval(0.5, self.update_all_mfc_measurements)
			else:
				self.log_message("Devices not connected, cannot read parameters.")
		
		except Exception as e:
			self.log_message(f"Error getting measurement_package_updates: {e}")
	
	@work(exclusive=True, thread=True)  # Apply the @work decorator here
	def update_all_mfc_measurements(self) -> None:
		"""Update all MFC modules with the latest measurement data"""
		# First, read all parameters from all devices in one batch
		success = self.manager.read_multiple_parameters()
		
		if success:
			# Use batch_update to combine all DOM modifications into a single render pass
			with self.app.batch_update():
				# Then update each MFC module with its own data from the manager
				for mfc in self.query(MFCModule):
					serial = mfc.mfc_serial
					if serial in self.manager.data_package:
						# Call update_measurement_display without arguments
						# The method will access the data directly from the manager
						mfc.update_measurement_display()
					else:
						# Only log this message if we expect data for this device
						if serial in self.manager.matched_devices:
							self.log_message(f"No data available for {serial}")
		else:
			# Log when parameter reading fails
			self.log_message("Failed to read measurement data from devices")
