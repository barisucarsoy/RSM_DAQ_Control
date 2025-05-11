import cantera as ct

from textual import on
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from device_managers.device_manager_bronkhorst import DeviceManager
from ui.bronkhorst_widget import BronkhorstWidget, MFCModule

def calculate_flow_rate(
    temperature :float, # [degC]
    pressure    :float, # [bar]
    
    flow_speed_jet  :float, # [m/s]
    eq_ratio_jet    :float, # [-]
    diameter_jet    :float, # [mm]
    
    flow_speed_pilot:float, # [m/s]
    eq_ratio_pilot  :float, # [-]
    diameter_pilot  :float, # [mm]
    ):
    
    """Calculate the flow rate of the pilot and the jet based on the given parameters."""
    
    jet_area      = (3.14159 * (diameter_jet   / 1000) ** 2) / 4 # converted to [m] from [mm]
    pilot_surface = (3.14159 * (diameter_pilot / 1000) ** 2) / 4 # converted to [m] from [mm]
    
    pilot_area = pilot_surface - jet_area # Net pilot area after subtracting central jet
    
    jet_flowrate   = flow_speed_jet * jet_area
    pilot_flowrate = flow_speed_pilot * pilot_area
    
    # Creating required cantera objects
    gas_real_jet    = ct.Solution("gri30.yaml")
    gas_real_pilot  = ct.Solution("gri30.yaml")
    
    gas_real_jet.TP = temperature + 273.15, pressure * 1e5
    gas_real_jet.set_equivalence_ratio(eq_ratio_jet, "H2", "O2:1.0, N2:3.76")
    
    gas_real_pilot.TP = temperature + 273.15, pressure * 1e5
    gas_real_pilot.set_equivalence_ratio(eq_ratio_pilot, "H2", "O2:1.0, N2:3.76")
    
    mixture_density_jet = gas_real_jet.density_mass
    mass_flowrate_jet = jet_flowrate * mixture_density_jet  # kg/s
    
    mixture_density_pilot = gas_real_pilot.density_mass
    mass_flowrate_pilot = pilot_flowrate * mixture_density_pilot  # kg/s
    
    y_h2_jet   = gas_real_jet.Y[gas_real_jet.species_index("H2")]
    y_h2_pilot = gas_real_pilot.Y[gas_real_pilot.species_index("H2")]
    
    # Calculate the mass flow rate of H2 and air
    mass_flow_h2_jet  = mass_flowrate_jet * y_h2_jet
    mass_flow_air_jet = mass_flowrate_jet - mass_flow_h2_jet
    
    mass_flow_h2_pilot = mass_flowrate_pilot * y_h2_pilot
    mass_flow_air_pilot = mass_flowrate_pilot - mass_flow_h2_pilot
    
    # Calculate densities at normal conditions -> at 0°C and 1 atm
    gas_normal_air = ct.Solution("gri30.yaml")
    gas_normal_air.TPX = 273.15, ct.one_atm, "O2:0.21, N2:0.79"
    normal_density_air = gas_normal_air.density_mass
    
    gas_normal_h2 = ct.Solution("gri30.yaml")
    gas_normal_h2.TPX = 273.15, ct.one_atm, "H2:1.0"
    normal_density_h2 = gas_normal_h2.density_mass
    
    # Calculate normal volumetric flowrates
    vol_flow_normal_h2_jet   = mass_flow_h2_jet / normal_density_h2
    vol_flow_normal_h2_pilot = mass_flow_h2_pilot / normal_density_h2
    
    vol_flow_std_air_jet   = mass_flow_air_jet / normal_density_air
    vol_flow_std_air_pilot = mass_flow_air_pilot / normal_density_air

    
    normal_flowrates = {
            "H2_Jet"   : round(vol_flow_normal_h2_jet * 3600, 5),  # Convert to m^3/h
            "Air_Jet"  : round(vol_flow_std_air_jet   * 3600, 5),  # Convert to m^3/h
            "H2_Pilot" : round(vol_flow_normal_h2_pilot * 3600, 5),  # Convert to m^3/h
            "Air_Pilot": round(vol_flow_std_air_pilot   * 3600, 5),  # Convert to m^3/h
    }
    return normal_flowrates

class FlowCalculator(Widget):
    """A widget for calculating flow rates for Jet and Pilot."""
    
    CSS_PATH = "CSS_main.tcss"
    
    # --- Shared Reactive Variables ---
    temperature = reactive(20.00)  # Default Temp C
    pressure    = reactive(1.00)   # Default Pressure bar
    
    # --- Jet Reactive Variables ---
    jet_flow_speed    = reactive(100.00)
    jet_eq_ratio      = reactive(0.40)
    jet_dia           = reactive(2)
    jet_flow_rate_h2  = reactive(0.00)
    jet_flow_rate_air = reactive(0.00)
    
    # --- Pilot Reactive Variables ---
    pilot_flow_speed    = reactive(1)
    pilot_eq_ratio      = reactive(0.40)
    pilot_dia           = reactive(30)
    pilot_flow_rate_h2  = reactive(0.00)
    pilot_flow_rate_air = reactive(0.00)
    
    def __init__(self) -> None:
        super().__init__()
        self.manager = DeviceManager.get_instance()
        self.device_db = self.manager.device_db
        self.bundles = self.manager.bundles

        self.calculated_flowrates = {
                "H2_Jet"   : 0.0,
                "Air_Jet"  : 0.0,
                "H2_Pilot" : 0.0,
                "Air_Pilot": 0.0,
        }
    
    def compose(self):
        # Define widgets
        temperature_input = Input(placeholder="[°C]", id="temperature", value=str(self.temperature), type="number")
        pressure_input    = Input(placeholder="[bar]", id="pressure", value=str(self.pressure), type="number")
        jet_dia_input     = Input(placeholder="[mm]", id="jet_dia", value=f"{self.jet_dia}", type="text")
        pilot_dia_input   = Input(placeholder="[mm]", id="pilot_dia", value=f"{self.pilot_dia}", type="text")
        
        temperature_input.border_title  = "Temperature, degC"
        pressure_input.border_title     = "Pressure, bar"
        jet_dia_input.border_title      = "Jet diameter, mm"
        pilot_dia_input.border_title    = "Pilot diameter, mm"
        
        jet_flow_input      = Input(placeholder="[m/s]", id="jet_flow_speed", value=str(self.jet_flow_speed), type="number")
        jet_eq_ratio_input  = Input(placeholder="Eq Ratio", id="jet_eq_ratio", value=str(self.jet_eq_ratio), type="number")
        jet_h2_flowrate_label  = Label("0.0", id="jet_flowrate_label_h2")
        jet_air_flowrate_label = Label("0.0", id="jet_flowrate_label_air")
        
        jet_flow_input.border_title         = "Jet Vel. m/s "
        jet_eq_ratio_input.border_title     = "Jet Eq. Ratio"
        jet_h2_flowrate_label.border_title  = "Jet H2, m3n/h"
        jet_air_flowrate_label.border_title = "Jet Air, m3n/h"
        
        pilot_flow_input     = Input(placeholder="[m/s]", id="pilot_flow_speed", value=str(self.pilot_flow_speed), type="number")
        pilot_eq_ratio_input = Input(placeholder="Eq Ratio", id="pilot_eq_ratio", value=str(self.pilot_eq_ratio), type="number")
        pilot_h2_flowrate_label  = Label("0.0", id="pilot_flowrate_label_h2")
        pilot_air_flowrate_label = Label("0.0", id="pilot_flowrate_label_air")
        
        pilot_flow_input.border_title         = "Pilot Vel. m/s "
        pilot_eq_ratio_input.border_title     = "Pilot Eq. Ratio"
        pilot_h2_flowrate_label.border_title  = "Pilot H2, m3n/h"
        pilot_air_flowrate_label.border_title = "Pilot Air, m3n/h"
        
        calculate_button    = Button("Calculate", id="calculate_button", variant="primary")
        send_button         = Button("Send", id="send_2_mfc", variant="success")
        
        with Horizontal():
            # --- Shared Inputs (Top) ---
            with Vertical(id="fixed_inputs_container"):
                with Horizontal():
                    yield temperature_input
                    yield pressure_input
                
                with Horizontal():
                    yield jet_dia_input
                    yield pilot_dia_input
                
                with Horizontal():
                    yield calculate_button
                    yield send_button
            
            # --- Jet and Pilot Sections ---
            with Horizontal(id="main_horizontal_layout"):
                # --- Jet Section ---
                with Vertical(id="jet_container", classes="input-section"):
                    # yield Label("[b]Jet Calculation[/b]")
                    with Vertical():
                        with Vertical(id="jet_inputs"):
                            yield jet_flow_input
                            yield jet_eq_ratio_input
                        
                        with Vertical(id="jet_outputs"):
                            yield jet_h2_flowrate_label
                            yield jet_air_flowrate_label
                
                # --- Pilot Section ---
                with Vertical(id="pilot_container", classes="input-section"):
                    # yield Label("[b]Pilot Calculation[/b]")
                    with Vertical():
                        with Vertical(id="pilot_inputs"):
                            yield pilot_flow_input
                            yield pilot_eq_ratio_input
                        
                        with Vertical(id="pilot_outputs"):
                            yield pilot_h2_flowrate_label
                            yield pilot_air_flowrate_label
    
    def log_message(self, message: str) -> None:
        """Send log messages to the parent BronkhorstWidget"""
        # Find the parent BronkhorstWidget
        parent = self.app.query_one(BronkhorstWidget)
        parent.log_message(f"{message}")
    
    @on(Button.Pressed, "#calculate_button")
    def calculate_button(self)  -> None:
        """Calculate the flow rates for both Jet and Pilot."""
        try:
            # Get shared values
            temperature = float(self.query_one("#temperature", Input).value)
            pressure = float(self.query_one("#pressure", Input).value)
            
            # Get jet-specific values
            flow_speed_jet = float(self.query_one("#jet_flow_speed", Input).value)
            eq_ratio_jet   = float(self.query_one("#jet_eq_ratio", Input).value)
            diameter_jet   = float(self.query_one("#jet_dia", Input).value)  # Read dia
            
            # Get pilot-specific values
            flow_speed_pilot = float(self.query_one("#pilot_flow_speed", Input).value)
            eq_ratio_pilot   = float(self.query_one("#pilot_eq_ratio", Input).value)
            diameter_pilot   = float(self.query_one("#pilot_dia", Input).value)  # Read dia
            
            # Store shared values (might be redundant if watched)
            self.temperature = temperature
            self.pressure    = pressure
            
            # Calculate flow rates
            flow_rates = calculate_flow_rate(
                    temperature=temperature,
                    pressure=pressure,
                    flow_speed_jet=flow_speed_jet,
                    eq_ratio_jet=eq_ratio_jet,
                    diameter_jet=diameter_jet,
                    flow_speed_pilot=flow_speed_pilot,
                    eq_ratio_pilot=eq_ratio_pilot,
                    diameter_pilot=diameter_pilot,
            )
            
            # Store calculated flow rates
            self.calculated_flowrates["H2_Jet"]   = flow_rates["H2_Jet"]
            self.calculated_flowrates["Air_Jet"]  = flow_rates["Air_Jet"]
            self.calculated_flowrates["H2_Pilot"] = flow_rates["H2_Pilot"]
            self.calculated_flowrates["Air_Pilot"]= flow_rates["Air_Pilot"]
        
            
            # Update labels
            self.query_one("#jet_flowrate_label_h2", Label).update(
                    f"{flow_rates['H2_Jet']:.5f}"
            )
            self.query_one("#jet_flowrate_label_air", Label).update(
                    f"{flow_rates['Air_Jet']:.5f}"
            )
            
            self.query_one("#pilot_flowrate_label_h2", Label).update(
                    f"{flow_rates['H2_Pilot']:.5f}"
            )
            self.query_one("#pilot_flowrate_label_air", Label).update(
                    f"{flow_rates['Air_Pilot']:.5f}"
            )
            
            # Log the results
            self.log_message(
                    f"Calculated Jet  : H2={flow_rates['H2_Jet']:.5f} m3n/h, Air={flow_rates['Air_Jet']:.5f} m3n/h"
            )
            self.log_message(
                    f"Calculated Pilot: H2={flow_rates['H2_Pilot']:.5f} m3n/h, Air={flow_rates['Air_Pilot']:.5f} m3n/h"
            )
            
        except ValueError as e:
            self.notify(
                    f"Invalid input: {e}",
                    severity="error",
                    title="Calculation Error",
            )
        except Exception as e:
            self.notify(
                    f"Calculation error: {str(e)}",
                    severity="error",
                    title="Calculation Error",
            )
        
    def choose_mfc(self, bundle_name: str, target_flow_m3n_h: float) -> str | None:
        """
        Pick the most suitable MFC (by serial number) for the requested bundle.

        Parameters
        ----------
        bundle_name : str
            One of the names listed in the configuration's ``mfc_bundles``.
        target_flow_m3n_h : float
            Requested volumetric flow in m³ₙ/h (always normalized to this unit
            inside the YAML file).

        Returns
        -------
        str | None
            Serial number of the selected device or ``None`` when nothing
            matches the 10 %–100 % full-scale rule.
        """
        # ------------------------------------------------------------------
        # 1) gather candidates: devices whose bundle matches `bundle_name`
        # ------------------------------------------------------------------
        candidates: list[tuple[str, float]] = []  # (serial, full_scale)
        
        for serial, dev_cfg in self.device_db.items():
            # `dev_cfg` is a DeviceConfig data-class ➔ use attribute access
            if dev_cfg.bundle != bundle_name:
                continue
            
            full_scale = dev_cfg.m3n_h_capacity
            if full_scale is None:
                continue
            
            # 10 %-FS rule --------------------------------------------------
            if 0.1 * full_scale <= target_flow_m3n_h <= full_scale:
                candidates.append((serial, full_scale))
        
        # ------------------------------------------------------------------
        # 2) no candidate found
        # ------------------------------------------------------------------
        if not candidates:
            self.log_message(
                    f"No MFC in bundle '{bundle_name}' can supply "
                    f"{target_flow_m3n_h:.4f} m³ₙ/h (violates 10 %-rule or exceeds FS)."
            )
            return None
        
        # ------------------------------------------------------------------
        # 3) choose the device with the smallest full-scale that still works
        # ------------------------------------------------------------------
        best_serial, _ = min(candidates, key=lambda item: item[1])
        return best_serial
    
    @on(Button.Pressed, "#send_2_mfc")
    def send_to_mfcs(self) -> None:
        jet_h2_mfc    = self.choose_mfc("jet_h2", self.calculated_flowrates["H2_Jet"])
        jet_air_mfc   = self.choose_mfc("jet_air", self.calculated_flowrates["Air_Jet"])
        pilot_h2_mfc  = self.choose_mfc("pilot_h2", self.calculated_flowrates["H2_Pilot"])
        pilot_air_mfc = self.choose_mfc("pilot_air", self.calculated_flowrates["Air_Pilot"])
        
        self.log_message(f"  Jet H2 = {jet_h2_mfc},   Jet Air = {jet_air_mfc}")
        self.log_message(f"Pilot H2 = {pilot_h2_mfc}, Pilot Air = {pilot_air_mfc}")
        
        theme_background_color, color = self.app.background_colors
        
        mfc_modules = list(self.app.query(MFCModule))
        try:
            for module in mfc_modules:
                if hasattr(module, "mfc_serial"):
                    if module.mfc_serial == jet_h2_mfc:
                        input_field = module.query_one("#flow_input", Input)
                        input_field.value = f"{self.calculated_flowrates["H2_Jet"]:.5f}"
                        module.styles.background = "red 20%"
                        module.styles.opacity = "100%"
                        
                    elif module.mfc_serial == jet_air_mfc:
                        input_field = module.query_one("#flow_input", Input)
                        input_field.value = f"{self.calculated_flowrates["Air_Jet"]:.5f}"
                        module.styles.background = "blue 20%"
                        module.styles.opacity = "100%"
                        
                    elif module.mfc_serial == pilot_h2_mfc:
                        input_field = module.query_one("#flow_input", Input)
                        input_field.value = f"{self.calculated_flowrates["H2_Pilot"]:.5f}"
                        module.styles.background = "red 20%"
                        module.styles.opacity = "100%"
                        
                    elif module.mfc_serial == pilot_air_mfc:
                        input_field = module.query_one("#flow_input", Input)
                        input_field.value = f"{self.calculated_flowrates["Air_Pilot"]:.5f}"
                        module.styles.background = "blue 20%"
                        module.styles.opacity = "100%"
                        
                    else:
                        if module.mfc_serial in self.bundles["coflow"]:
                            module.styles.background = color
                            module.styles.opacity = "100%"
                        else:
                            module.styles.background = color
                            module.styles.opacity = "30%"
        except Exception as e:
            self.log_message(f"Error setting flow rates: {e}")
