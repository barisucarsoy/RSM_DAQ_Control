from textual.widget import Widget
from textual.widgets import Input, Button, Label, Rule, Select
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual import on
from textual.reactive import reactive

import cantera as ct

from device_database.database_bronkhorst import device_db


def calculate_flow_rate(flow_speed:     float,
                        eq_ratio:       float,
                        diameter:       float,
                        temperature:    float,
                        pressure:       float):

    """Calculate the flow rate based on the given parameters."""
    area = (3.14159 * (diameter / 1000) ** 2) / 4  # Convert diameter from mm to m
    total_flowrate = flow_speed * area  # m^3/s

    gas_real = ct.Solution('gri30.yaml')
    gas_real.TP = temperature + 273.15, pressure * 1e5
    gas_real.set_equivalence_ratio(eq_ratio, 'H2', 'O2:1.0, N2:3.76')
    mixture_density = gas_real.density_mass
    mass_flowrate = total_flowrate * mixture_density  # kg/s

    Y_h2 = gas_real.Y[gas_real.species_index('H2')]
    Y_o2 = gas_real.Y[gas_real.species_index('O2')]
    Y_n2 = gas_real.Y[gas_real.species_index('N2')]

    # Calculate the mass flow rate of H2 and air
    mass_flow_h2 = mass_flowrate * Y_h2
    mass_flow_air = mass_flowrate * (Y_o2 + Y_n2)

    # Calculate Standard volumetric flows at 0°C and 1 atm
    gas_std_air = ct.Solution('gri30.yaml')
    gas_std_air.TPX = 273.15, ct.one_atm, 'O2:0.21, N2:0.79'
    std_density_air = gas_std_air.density_mass

    gas_std_h2 = ct.Solution('gri30.yaml')
    gas_std_h2.TPX = 273.15, ct.one_atm, 'H2:1.0'
    std_density_h2 = gas_std_h2.density_mass

    vol_flow_std_h2 = mass_flow_h2 / std_density_h2
    vol_flow_std_air = mass_flow_air / std_density_air

    std_flowrates = {
            'H2' : round(vol_flow_std_h2 * 3600, 5),  # Convert to m^3/h
            'Air': round(vol_flow_std_air * 3600, 5),  # Convert to m^3/h
            'mass_flow_rate': round(mass_flowrate * 1000, 5),  # g/s
    }
    return std_flowrates


class FlowCalculator(Widget):
    """A widget for calculating flow rates."""
    DEFAULT_CSS = """
    FlowCalculator {
        border: solid lightblue round;
        margin: 0;
        align: center top;
        height: auto;
    }

    #flow_speed, #eq_ratio, #diameter, #temperature, #pressure {
        width: 25;
        height: 3;
        border: solid $accent round;
        border-title-align: left;
        margin: 0;
        background: $background;
    }

    #flowrate_label_h2, #flowrate_label_air, #mass_flowrate_label{
        width: 20;
        height: 3;
        border: solid lightblue round;
        border-title-align: left;
    }

    .error_message {
        color: red;
        height: 1;
    }

    #send_container {
        height: auto;
        margin: 1;
    }

    #send_button {
        width: 15;
    }

    .calculate_button {
        margin: 0;
    }
    
    #rule {
        align: center top;   
    }

    """

    jet_flow_speed      = reactive(0.00)
    jet_eq_ratio        = reactive(0.40)
    jet_diameter        = reactive(0.00)
    jet_temperature     = reactive(0.00)
    jet_pressure        = reactive(1.00)  # Default to 1 bar
    jet_flow_rate_h2    = reactive(0.00)
    jet_flow_rate_air   = reactive(0.00)

    def __init__(self) -> None:
        super().__init__()
        self.device_db = device_db
        self.jet_mfcs = {'air': [], 'h2': []}
        self.pilot_mfcs = {'air': [], 'h2': []}

        for device in self.device_db.values():
            if device.tag == "jet":
                if device.target_fluid == "h2":
                    self.jet_mfcs['h2'].append(device.serial)
                elif device.target_fluid == "air":
                    self.jet_mfcs['air'].append(device.serial)
            elif device.tag == "pilot":
                if device.target_fluid == "h2":
                    self.pilot_mfcs['h2'].append(device.serial)
                elif device.target_fluid == "air":
                    self.pilot_mfcs['air'].append(device.serial)

        # Get all jet air MFC serials
        self.jet_air_devices = self.jet_mfcs['air']  # returns list of serials
        self.jet_h2_devices = self.jet_mfcs['h2']  # returns list of serials

        # Get all pilot air MFC serials
        self.pilot_air_devices = self.pilot_mfcs['air']  # returns list of serials
        self.pilot_h2_devices = self.pilot_mfcs['h2']  # returns list of serials

    def compose(self):
        flow_input = Input(placeholder='[m/s]', id='flow_speed', value="100.0", type="number")
        flow_input.border_title = "Jet Speed m/s "

        eq_ratio_input = Input(placeholder='Eq Ratio', id='eq_ratio', value="0.40", type="number")
        eq_ratio_input.border_title = "Jet Eq Ratio"

        diameter_input = Input(placeholder='[mm]', id='diameter', value="2.0", type="number")
        diameter_input.border_title = "Jet Diameter mm"

        temperature_input = Input(placeholder='[°C]', id='temperature', value="25.0", type="number")
        temperature_input.border_title = "Jet Temperature °C"

        pressure_input = Input(placeholder='[bar]', id='pressure', value="1", type="number")
        pressure_input.border_title = "Jet Pressure bar"

        h2_flowrate_label = Label('0.0', id="flowrate_label_h2")
        h2_flowrate_label.border_title = "jet H2 m3n/h"

        air_flowrate_label = Label('0.0', id="flowrate_label_air")
        air_flowrate_label.border_title = "jet air m3n/h"

        mass_flowrate_label = Label('0.0', id="mass_flowrate_label")
        mass_flowrate_label.border_title = "mass flow g/s"

        with Vertical():

            with Horizontal():
                # Input fields for parameters
                with Vertical():
                    yield flow_input
                    yield eq_ratio_input
                    yield diameter_input
                    yield temperature_input
                    yield pressure_input

                with Vertical():
                    # Display calculated flow rates
                    yield h2_flowrate_label
                    yield air_flowrate_label
                    yield mass_flowrate_label
                    yield Button("Calculate", id="calculate_flowrate", variant="primary", classes="calculate_button")
                    yield Button("Send to MFCs", id="send_button", variant="success")

            yield Rule(id="rule", line_style="dashed")

            with Horizontal():
                with Vertical():
                    yield Label("x")
                    yield Label("x")
                    yield Label("x")
                    yield Label("x")


    @on(Button.Pressed, "#calculate_flowrate")
    def calculate(self) -> None:
        """Calculate the flow rate based on the input parameters."""
        try:
            # Get input values and convert to float
            flow_speed = float(self.query_one("#flow_speed", Input).value)
            eq_ratio = float(self.query_one("#eq_ratio", Input).value)
            diameter = float(self.query_one("#diameter", Input).value)
            temperature = float(self.query_one("#temperature", Input).value)
            pressure = float(self.query_one("#pressure", Input).value)

            # Calculate flow rates
            flow_rates = calculate_flow_rate(
                flow_speed=flow_speed,
                eq_ratio=eq_ratio,
                diameter=diameter,
                temperature=temperature,
                pressure=pressure
            )

            # Update labels with calculated values
            self.query_one("#flowrate_label_h2", Label).update(f"{flow_rates['H2']:.5f}")
            self.query_one("#flowrate_label_air", Label).update(f"{flow_rates['Air']:.5f}")
            self.query_one("#mass_flowrate_label", Label).update(f"{flow_rates['mass_flow_rate']:.5f}")

            # Store values in reactive variables
            self.jet_flow_speed = flow_speed
            self.jet_eq_ratio = eq_ratio
            self.jet_diameter = diameter
            self.jet_temperature = temperature
            self.jet_pressure = pressure
            self.jet_flow_rate_h2 = flow_rates['H2']
            self.jet_flow_rate_air = flow_rates['Air']

        except ValueError as e:
            self.notify("Invalid input values", severity="error")
        except Exception as e:
            self.notify(f"Calculation error: {str(e)}", severity="error")

    @on(Button.Pressed, "#send_button")
    def send_flowrates(self):
        try:
            if self.jet_flow_rate_h2 <= 0 or self.jet_flow_rate_air <= 0:
                self.notify("Please calculate valid flow rates first", severity="error")
                return

            # Find all MFC modules in the application
            from widgets.bronkhorst_widget import MFCModule
            mfc_modules = list(self.app.query(MFCModule))

            # Keep track of how many values we've set
            updates_applied = 0
            low_flowrates = []

            # Process H2 MFCs
            for h2_serial in self.jet_mfcs['h2']:
                # Find the matching MFC module
                for module in mfc_modules:
                    if module.mfc_serial == h2_serial:
                        # Check if capacity is sufficient (but don't block based on arming)
                        if self.jet_flow_rate_h2 < self.device_db[h2_serial].target_capacity * 0.1:
                            low_flowrates.append(f"H2 ({h2_serial})")

                        # Set the flow value in the input field regardless of armed state
                        input_field = module.query_one("#flow_input", Input)
                        input_field.value = str(self.jet_flow_rate_h2)
                        updates_applied += 1
                        break

            # Process Air MFCs
            for air_serial in self.jet_mfcs['air']:
                # Find the matching MFC module
                for module in mfc_modules:
                    if module.mfc_serial == air_serial:
                        # Check if capacity is sufficient (but don't block based on arming)
                        if self.jet_flow_rate_air < self.device_db[air_serial].target_capacity * 0.1:
                            low_flowrates.append(f"Air ({air_serial})")

                        # Set the flow value in the input field regardless of armed state
                        input_field = module.query_one("#flow_input", Input)
                        input_field.value = str(self.jet_flow_rate_air)
                        updates_applied += 1
                        break

            # Report results
            if updates_applied > 0:
                self.notify(f"Applied flow rates to {updates_applied} MFCs", severity="information")

                # Warn about low flowrates if any were detected
                if low_flowrates:
                    low_flowrate_msg = ", ".join(low_flowrates)
                    self.notify(f"Warning: Low flowrates (<10% capacity) for: {low_flowrate_msg}", severity="warning")
            else:
                self.notify("No MFCs were found matching jet tag", severity="warning")

        except Exception as e:
            self.notify(f"Error sending flow rates: {str(e)}", severity="error")
