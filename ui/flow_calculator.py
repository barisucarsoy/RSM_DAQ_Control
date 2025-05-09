import cantera as ct

# Removed unused Message import
from textual import on
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from device_managers.device_manager_bronkhorst import DeviceManager



def calculate_flow_rate(
		flow_speed:     float,
		eq_ratio:       float,
		diameter:       float,
		temperature:    float,
		pressure:       float,
):
	"""Calculate the flow rate based on the given parameters."""
	area = (3.14159 * (diameter / 1000) ** 2) / 4  # Convert diameter from mm to m
	total_flowrate = flow_speed * area  # m^3/s
	
	gas_real = ct.Solution("gri30.yaml")
	gas_real.TP = temperature + 273.15, pressure * 1e5
	gas_real.set_equivalence_ratio(eq_ratio, "H2", "O2:1.0, N2:3.76")
	mixture_density = gas_real.density_mass
	mass_flowrate = total_flowrate * mixture_density  # kg/s
	
	Y_h2 = gas_real.Y[gas_real.species_index("H2")]
	Y_o2 = gas_real.Y[gas_real.species_index("O2")]
	Y_n2 = gas_real.Y[gas_real.species_index("N2")]
	
	# Calculate the mass flow rate of H2 and air
	mass_flow_h2 = mass_flowrate * Y_h2
	mass_flow_air = mass_flowrate * (Y_o2 + Y_n2)
	
	# Calculate Standard volumetric flows at 0°C and 1 atm -> actually normal conditions
	gas_std_air = ct.Solution("gri30.yaml")
	gas_std_air.TPX = 273.15, ct.one_atm, "O2:0.21, N2:0.79"
	std_density_air = gas_std_air.density_mass
	
	gas_std_h2 = ct.Solution("gri30.yaml")
	gas_std_h2.TPX = 273.15, ct.one_atm, "H2:1.0"
	std_density_h2 = gas_std_h2.density_mass
	
	vol_flow_std_h2 = mass_flow_h2 / std_density_h2
	vol_flow_std_air = mass_flow_air / std_density_air
	
	std_flowrates = {
			"H2": round(vol_flow_std_h2 * 3600, 5),  # Convert to m^3/h
			"Air": round(vol_flow_std_air * 3600, 5),  # Convert to m^3/h
			"mass_flow_rate": round(mass_flowrate * 1000, 5),  # g/s
	}
	return std_flowrates


class FlowCalculator(Widget):
	"""A widget for calculating flow rates for Jet and Pilot."""
	
	CSS_PATH = "CSS_main.tcss"
	
	# --- Shared Reactive Variables ---
	temperature = reactive(20.00)  # Default Temp C
	pressure = reactive(1.00)  # Default Pressure bar
	
	# --- Jet Reactive Variables ---
	jet_flow_speed = reactive(100.00)
	jet_eq_ratio = reactive(0.40)
	jet_dia = reactive(2)
	jet_flow_rate_h2 = reactive(0.00)
	jet_flow_rate_air = reactive(0.00)
	jet_mass_flow_rate = reactive(0.00)
	
	# --- Pilot Reactive Variables ---
	pilot_flow_speed = reactive(1)  # Example default
	pilot_eq_ratio = reactive(0.40)  # Example default
	pilot_dia = reactive(30)
	pilot_flow_rate_h2 = reactive(0.00)
	pilot_flow_rate_air = reactive(0.00)
	pilot_mass_flow_rate = reactive(0.00)
	
	
	def __init__(self) -> None:
		super().__init__()
		self.manager = DeviceManager.get_instance()
		self.device_db = self.manager.device_db
		self.jet_mfcs = {"air": [], "h2": []}
		self.pilot_mfcs = {"air": [], "h2": []}
		
		# Populate MFC lists (assuming device_db has expected structure)
		for serial, device in self.device_db.items():
			if (
					hasattr(device, "tag")
					and hasattr(device, "target_fluid")
					and hasattr(device, "serial")
			):
				target_list = None
				if device.tag == "jet":
					target_list = self.jet_mfcs
				elif device.tag == "pilot":
					target_list = self.pilot_mfcs
				
				if target_list is not None:
					if device.target_fluid == "h2":
						target_list["h2"].append(device.serial)
					elif device.target_fluid == "air":
						target_list["air"].append(device.serial)
		
		# Keep serial lists directly accessible (optional, could use dict directly)
		self.jet_air_devices = self.jet_mfcs["air"]
		self.jet_h2_devices = self.jet_mfcs["h2"]
		self.pilot_air_devices = self.pilot_mfcs["air"]
		self.pilot_h2_devices = self.pilot_mfcs["h2"]
	
	def compose(self):
		# --- Shared Inputs (Top) ---
		with Horizontal(id="fixed_inputs_container"):
			with Vertical():
				temperature_input = Input(
						placeholder="[°C]",
						id="temperature",
						value=str(self.temperature),
						type="number",
				)
				temperature_input.border_title = "Temperature °C"
				yield temperature_input
				
				pressure_input = Input(
						placeholder="[bar]",
						id="pressure",
						value=str(self.pressure),
						type="number",
				)
				pressure_input.border_title = "Pressure bar"
				yield pressure_input
			
			with Vertical():
				jet_dia_input = Input(
						placeholder="[mm]",
						id="jet_dia",
						value=f"{self.jet_dia}",
						type="text",
				)  # Use text for scientific notation
				jet_dia_input.border_title = "Jet dia mm"
				yield jet_dia_input
				
				pilot_dia_input = Input(
						placeholder="[mm]",
						id="pilot_dia",
						value=f"{self.pilot_dia}",
						type="text",
				)  # Use text for scientific notation
				pilot_dia_input.border_title = "Pilot Dia mm"
				yield pilot_dia_input
		
		# --- Jet and Pilot Sections ---
		with Vertical(id="main_horizontal_layout"):
			# --- Jet Section ---
			with Vertical(id="jet_container", classes="input-section"):
				yield Label("[b]Jet Calculation[/b]")
				with Horizontal():
					with Vertical(id="jet_inputs"):
						jet_flow_input = Input(
								placeholder="[m/s]",
								id="jet_flow_speed",
								value=str(self.jet_flow_speed),
								type="number",
						)
						jet_flow_input.border_title = "Jet m/s "
						yield jet_flow_input
						
						jet_eq_ratio_input = Input(
								placeholder="Eq Ratio",
								id="jet_eq_ratio",
								value=str(self.jet_eq_ratio),
								type="number",
						)
						jet_eq_ratio_input.border_title = "Jet Eq Ratio"
						yield jet_eq_ratio_input
					
					with Vertical(id="jet_outputs"):
						jet_h2_flowrate_label = Label("0.0", id="jet_flowrate_label_h2")
						jet_h2_flowrate_label.border_title = "jet H2 m3n/h"
						yield jet_h2_flowrate_label
						
						jet_air_flowrate_label = Label(
								"0.0", id="jet_flowrate_label_air"
						)
						jet_air_flowrate_label.border_title = "jet air m3n/h"
						yield jet_air_flowrate_label
						
						jet_mass_flowrate_label = Label(
								"0.0", id="jet_mass_flowrate_label"
						)
						jet_mass_flowrate_label.border_title = "jet mass g/s"
						yield jet_mass_flowrate_label
					
					with Vertical():
						yield Button(
								"Calculate Jet",
								id="calculate_jet",
								variant="primary",
								classes="calculate_button",
						)
						yield Button(
								"Send Jet to MFCs",
								id="send_jet_button",
								variant="success",
								classes="send_button",
						)
			
			# --- Pilot Section ---
			with Vertical(id="pilot_container", classes="input-section"):
				yield Label("[b]Pilot Calculation[/b]")
				with Horizontal():
					with Vertical(id="pilot_inputs"):
						pilot_flow_input = Input(
								placeholder="[m/s]",
								id="pilot_flow_speed",
								value=str(self.pilot_flow_speed),
								type="number",
						)
						pilot_flow_input.border_title = "Pilot m/s "
						yield pilot_flow_input
						
						pilot_eq_ratio_input = Input(
								placeholder="Eq Ratio",
								id="pilot_eq_ratio",
								value=str(self.pilot_eq_ratio),
								type="number",
						)
						pilot_eq_ratio_input.border_title = "Pilot Eq Ratio"
						yield pilot_eq_ratio_input
					
					with Vertical(id="pilot_outputs"):
						pilot_h2_flowrate_label = Label(
								"0.0", id="pilot_flowrate_label_h2"
						)
						pilot_h2_flowrate_label.border_title = "pilot H2 m3n/h"
						yield pilot_h2_flowrate_label
						
						pilot_air_flowrate_label = Label(
								"0.0", id="pilot_flowrate_label_air"
						)
						pilot_air_flowrate_label.border_title = "pilot air m3n/h"
						yield pilot_air_flowrate_label
						
						pilot_mass_flowrate_label = Label(
								"0.0", id="pilot_mass_flowrate_label"
						)
						pilot_mass_flowrate_label.border_title = "pilot mass g/s"
						yield pilot_mass_flowrate_label
					
					with Vertical():
						yield Button(
								"Calculate Pilot",
								id="calculate_pilot",
								variant="primary",
								classes="calculate_button",
						)
						yield Button(
								"Send Pilot to MFCs",
								id="send_pilot_button",
								variant="success",
								classes="send_button",
						)
	
	# --- Watchers for Shared Inputs ---
	def watch_temperature(self, value: float) -> None:
		# Optional: Trigger recalculation if temp changes, or just update display
		pass  # Recalculations happen on button press
	
	def watch_pressure(self, value: float) -> None:
		# Optional: Trigger recalculation if pressure changes, or just update display
		pass  # Recalculations happen on button press
	
	# --- Calculation Methods ---
	@on(Button.Pressed, "#calculate_jet")
	def calculate_jet(self) -> None:
		"""Calculate the flow rate for the jet."""
		try:
			# Get shared values
			temperature = float(self.query_one("#temperature", Input).value)
			pressure = float(self.query_one("#pressure", Input).value)
			# Get jet-specific values
			flow_speed = float(self.query_one("#jet_flow_speed", Input).value)
			eq_ratio = float(self.query_one("#jet_eq_ratio", Input).value)
			diameter = float(self.query_one("#jet_dia", Input).value)  # Read dia
			
			# Store shared values (might be redundant if watched)
			self.temperature = temperature
			self.pressure = pressure
			
			# Calculate flow rates
			flow_rates = calculate_flow_rate(
					flow_speed=flow_speed,
					eq_ratio=eq_ratio,
					diameter=diameter,
					temperature=temperature,
					pressure=pressure,
			)
			
			# Update jet labels
			self.query_one("#jet_flowrate_label_h2", Label).update(
					f"{flow_rates['H2']:.5f}"
			)
			self.query_one("#jet_flowrate_label_air", Label).update(
					f"{flow_rates['Air']:.5f}"
			)
			self.query_one("#jet_mass_flowrate_label", Label).update(
					f"{flow_rates['mass_flow_rate']:.5f}"
			)
			
			# Store jet values in reactive variables
			self.jet_flow_speed = flow_speed
			self.jet_eq_ratio = eq_ratio
			self.jet_dia = diameter
			self.jet_flow_rate_h2 = flow_rates["H2"]
			self.jet_flow_rate_air = flow_rates["Air"]
			self.jet_mass_flow_rate = flow_rates["mass_flow_rate"]
		
		except ValueError as e:
			self.notify(
					f"Invalid Jet input: {e}",
					severity="error",
					title="Jet Calculation Error",
			)
		except Exception as e:
			self.notify(
					f"Jet Calculation error: {str(e)}",
					severity="error",
					title="Jet Calculation Error",
			)
	
	@on(Button.Pressed, "#calculate_pilot")
	def calculate_pilot(self) -> None:
		"""Calculate the flow rate for the pilot."""
		try:
			# Get shared values
			temperature = float(self.query_one("#temperature", Input).value)
			pressure = float(self.query_one("#pressure", Input).value)
			# Get pilot-specific values
			flow_speed = float(self.query_one("#pilot_flow_speed", Input).value)
			eq_ratio = float(self.query_one("#pilot_eq_ratio", Input).value)
			diameter = float(self.query_one("#pilot_dia", Input).value)
			
			# Store shared values (might be redundant if watched)
			self.temperature = temperature
			self.pressure = pressure
			
			# Calculate flow rates
			flow_rates = calculate_flow_rate(
					flow_speed=flow_speed,
					eq_ratio=eq_ratio,
					diameter=diameter,
					temperature=temperature,
					pressure=pressure,
			)
			
			# Update pilot labels
			self.query_one("#pilot_flowrate_label_h2", Label).update(
					f"{flow_rates['H2']:.5f}"
			)
			self.query_one("#pilot_flowrate_label_air", Label).update(
					f"{flow_rates['Air']:.5f}"
			)
			self.query_one("#pilot_mass_flowrate_label", Label).update(
					f"{flow_rates['mass_flow_rate']:.5f}"
			)
			
			# Store pilot values in reactive variables
			self.pilot_flow_speed = flow_speed
			self.pilot_eq_ratio = eq_ratio
			self.pilot_dia = diameter
			self.pilot_flow_rate_h2 = flow_rates["H2"]
			self.pilot_flow_rate_air = flow_rates["Air"]
			self.pilot_mass_flow_rate = flow_rates["mass_flow_rate"]
		
		except ValueError as e:
			self.notify(
					f"Invalid Pilot input: {e}",
					severity="error",
					title="Pilot Calculation Error",
			)
		except Exception as e:
			self.notify(
					f"Pilot Calculation error: {str(e)}",
					severity="error",
					title="Pilot Calculation Error",
			)
	
	# --- Send Logic ---
	# Helper function to send flow rates to specific MFCs
	def _send_to_mfcs(
			self, target_tag: str, h2_flow: float, air_flow: float, mfc_list: dict
	) -> None:
		if h2_flow <= 0 or air_flow <= 0:
			self.notify(
					f"Please calculate valid {target_tag} flow rates first",
					severity="warning",
					title=f"Send {target_tag.capitalize()} MFCs",
			)
			return
		
		# Find all MFC modules in the application (assuming this structure)
		try:
			# Ensure this import works within your application structure
			from ui.bronkhorst_widget import MFCModule
			
			mfc_modules = list(self.app.query(MFCModule))
		except ImportError as ime:
			self.notify(
					"Error: Could not import MFCModule. Sending disabled.", severity="error"
			)
			self.notify(str(ime), severity="error")
			return
		except Exception as e:
			self.notify(f"Error finding MFC modules: {e}", severity="error")
			return
		
		# Keep track of how many values we've set
		updates_applied = 0
		low_flowrates = []
		
		# Process H2 MFCs
		for h2_serial in mfc_list.get("h2", []):
			# Find the matching MFC module
			self.notify(f"{str(mfc_list.get('h2', []))}", severity="information")
			
			module_found = False
			for module in mfc_modules:
				if hasattr(module, "mfc_serial") and module.mfc_serial == h2_serial:
					module_found = True
					# Check capacity (using device_db if available)
					if h2_serial in self.device_db and hasattr(
							self.device_db[h2_serial], "target_capacity"
					):
						if h2_flow < self.device_db[h2_serial].target_capacity * 0.1:
							low_flowrates.append(f"H2 ({h2_serial})")
					else:
						self.notify(
								f"Warning: Capacity info missing for H2 MFC {h2_serial}",
								severity="warning",
						)
					
					# Set the flow value in the input field
					try:
						input_field = module.query_one("#flow_input", Input)
						input_field.value = f"{h2_flow:.5f}"  # Format consistently
						updates_applied += 1
					except Exception as e:
						self.notify(
								f"Error setting H2 flow for {h2_serial}: {e}",
								severity="error",
						)
					break  # Found the module for this serial
			if not module_found:
				self.notify(
						f"Warning: H2 MFC module with serial {h2_serial} not found in UI.",
						severity="warning",
				)
		
		# Process Air MFCs
		for air_serial in mfc_list.get("air", []):
			# Find the matching MFC module
			module_found = False
			for module in mfc_modules:
				if hasattr(module, "mfc_serial") and module.mfc_serial == air_serial:
					module_found = True
					# Check capacity (using device_db if available)
					if air_serial in self.device_db and hasattr(
							self.device_db[air_serial], "target_capacity"
					):
						if air_flow < self.device_db[air_serial].target_capacity * 0.1:
							low_flowrates.append(f"Air ({air_serial})")
					else:
						self.notify(
								f"Warning: Capacity info missing for Air MFC {air_serial}",
								severity="warning",
						)
					
					# Set the flow value in the input field
					try:
						input_field = module.query_one("#flow_input", Input)
						input_field.value = f"{air_flow:.5f}"  # Format consistently
						updates_applied += 1
					except Exception as e:
						self.notify(
								f"Error setting Air flow for {air_serial}: {e}",
								severity="error",
						)
					break  # Found the module for this serial
			if not module_found:
				self.notify(
						f"Warning: Air MFC module with serial {air_serial} not found in UI.",
						severity="warning",
				)
		
		# Report results
		if updates_applied > 0:
			self.notify(
					f"Applied {target_tag} flow rates to {updates_applied} MFC input(s)",
					severity="information",
					title=f"Send {target_tag.capitalize()} MFCs",
			)
			# Warn about low flowrates if any were detected
			if low_flowrates:
				low_flowrate_msg = ", ".join(low_flowrates)
				self.notify(
						f"Warning: Low flowrates (<10% capacity) for {target_tag}: {low_flowrate_msg}",
						severity="warning",
						title=f"Send {target_tag.capitalize()} MFCs",
				)
		else:
			self.notify(
					f"No MFCs were updated for {target_tag}.",
					severity="warning",
					title=f"Send {target_tag.capitalize()} MFCs",
			)
	
	@on(Button.Pressed, "#send_jet_button")
	def send_jet_flowrates(self):
		"""Send calculated jet flow rates to the corresponding MFCs."""
		try:
			self._send_to_mfcs(
					"jet", self.jet_flow_rate_h2, self.jet_flow_rate_air, self.jet_mfcs
			)
		except Exception as e:
			self.notify(
					f"Error sending jet flow rates: {str(e)}",
					severity="error",
					title="Send Jet MFCs Error",
			)
	
	@on(Button.Pressed, "#send_pilot_button")
	def send_pilot_flowrates(self):
		"""Send calculated pilot flow rates to the corresponding MFCs."""
		try:
			self._send_to_mfcs(
					"pilot",
					self.pilot_flow_rate_h2,
					self.pilot_flow_rate_air,
					self.pilot_mfcs,
			)
		except Exception as e:
			self.notify(
					f"Error sending pilot flow rates: {str(e)}",
					severity="error",
					title="Send Pilot MFCs Error",
			)
