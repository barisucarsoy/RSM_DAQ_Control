import time

from textual import on
from textual.widget import Widget
from textual.app import ComposeResult
from textual.widgets import Switch, Input, Button, Static, Log, Label
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive

from ui.custom_progress_bar import ProgressBar as CustomProgressBar

from device_managers.device_manager_bronkhorst import DeviceManager
from device_database.database_bronkhorst import device_db

"""
Textual TUI widget for Bronkhorst flow meter control and monitoring.
"""


class MFCModule(Widget):
    DEFAULT_CSS = """
    
    MFCModule {
    layout: horizontal;
    height: 5;
    align: center top;
    
    }
    .mfc-container {
        border: solid $accent round;
        height: 5;
        width: auto;
        margin: 0;
        border-title-align: left;
    }
    
    .mfc_arm_switch {
        margin: 0;
        height: auto;
        width: auto;
        background: #96304a;
    }
    
    .progress_label_container {
        margin: 0;
        height: auto;
        width: 15;
        align: left middle;
        }
    
    .progress_labels {
        margin: 0;
        height: auto;
        min-width: 5;
        align: left middle;
    }
    
    #progress_bars {
        margin: 0;
        align: left middle;
    }
    
    .mfc_progress_bar {
        margin: 0;
        align: right middle;
        }
        
    .mfc_input {
        margin: 0;
        height: 3;
        width: 20;
        background: darkslategrey;
    }
    
    .mfc_button {
        margin: 0;
    }
    
    .disabled-input {
        opacity: 0.7;
    }
    
    .disabled-button {
        opacity: 0.7;
    }
    
    .switch_armed{
        background: #4a9630;
    }
    
    .temperature_label {
        margin: 0;
        height: 3;
        width: 10;
        border: solid red round;
        align: left middle;
    }
    
    .flow_label {
        margin: 0;
        height: 3;
        width: 15;
        border: solid lightblue round;
        align: left middle;
    }
    
    .progress_label {
        margin: 0;
    }
    
    #wink_button {
        margin-left: 1;
        margin-right: 1;
        height: 3;
        width: 3;   
    }
        """

    # Reactive properties to track state
    armed               = reactive(False)
    set_percentage      = reactive(0.00)
    current_percentage  = reactive(0.00)
    current_valve       = reactive(0.00)
    temperature         = reactive(0.00)
    flowrate            = reactive(0.00)


    def __init__(self, mfc_serial: str) -> None:
        super().__init__()
        self.manager = DeviceManager.get_instance()

        self.mfc_serial = mfc_serial  # Serial number of the MFC
        self.mfc_data = device_db[mfc_serial]  # Get MFC data from the database according to serial number
        self.mfc_tag = self.mfc_data.tag  # Tag of the MFC
        self.mfc_fluid = self.mfc_data.target_fluid  # Target fluid of the MFC
        self.mfc_unit = self.mfc_data.target_unit  # Unit of the MFC
        self.mfc_capacity = self.mfc_data.target_capacity  # Max capacity of the MFC

    def log_message(self, message: str) -> None:
        """Send log messages to the parent BronkhorstWidget"""
        # Find the parent BronkhorstWidget
        parent = self.app.query_one(BronkhorstWidget)
        parent.log_message(f"[{self.mfc_serial}] {message}")

    def compose(self) -> ComposeResult:
        container = Container(classes="mfc-container")
        container.border_title = self.mfc_serial + " - " + self.mfc_tag + " - " + self.mfc_fluid

        flow_label = Label("NaN", id="flow_label", classes="flow_label")
        flow_label.border_title = self.mfc_unit

        temp_label = Label("NaN", id="temperature_label", classes="temperature_label")
        temp_label.border_title = "degC"

        with container:
            with Horizontal():
                # Arming Switch
                yield Switch(value=False, id="mfc_arm_switch", tooltip="Arm MFC", classes="mfc_arm_switch")

                with Vertical(classes="progress_label_container"):
                    yield Static("User Setpoint :", classes="progress_labels")
                    yield Static("Measured Flow :", classes="progress_labels")
                    yield Static("Valve Position:", classes="progress_labels")


                # Progress bars for set and actual opening percentage
                with Vertical(classes="progress_bars"):
                    yield CustomProgressBar(total=100.00, show_eta=False, id="set_percent_bar",
                                            classes="mfc_progress_bar")

                    yield CustomProgressBar(total=100.00, show_eta=False, id="real_percent_bar",
                                            classes="mfc_progress_bar")

                    yield CustomProgressBar(total=100.00, show_eta=False, id="valve_percent_bar",
                                            classes="mfc_progress_bar")

                yield flow_label
                yield temp_label

                # Input field for setting MFC opening percentage
                yield Input(placeholder="Flow m3n/h", id="flow_input", tooltip="Set MFC flow rate",
                            classes="mfc_input disabled-input", type="number", validate_on=["submitted"])

                # Send button
                yield Button("Send", id="send_button", tooltip="Send MFC opening percentage", variant="success",
                             classes="mfc_button disabled-button")

                # Wink wink
                yield Button("Blink", id="wink_button", tooltip="Wink", variant="primary", classes="wink_button")

    def on_mount(self) -> None:
        """Initialize widget state when mounted"""
        # Set progress bars to initial values
        self.query_one("#set_percent_bar", CustomProgressBar).progress = float(self.set_percentage)
        self.query_one("#real_percent_bar", CustomProgressBar).progress = self.current_percentage
        self.query_one("#valve_percent_bar", CustomProgressBar).progress = self.current_valve

        self.log_message(
            "Pulled from database:" + " Max Capacity: " + str(self.mfc_data.target_capacity) + " " + self.mfc_unit)

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



    @on(Input.Changed, "#flow_input")
    def validate_input(self, event: Input.Changed) -> None:
        """Validate and update percentage input"""
        try:
            value = float(event.value)
            if value < 0 or value > self.mfc_capacity:
                self.log_message(f"Invalid value: {value}. Must be between 0 and {self.mfc_capacity}.")
                event.input.value = ""

            percentage = value / self.mfc_capacity * 100.00
            # Update the set percentage bar to reflect input value
            self.set_percentage = str(percentage)
            self.query_one("#set_percent_bar", CustomProgressBar).progress = float(self.set_percentage)

        except ValueError:
            # If not a valid number, reset to 0
            event.input.value = ""

    @on(Button.Pressed, "#send_button")
    def send_flowrate(self) -> None:
        """Send the percentage to the device"""
        if not self.armed:
            self.notify("MFC is not armed.", severity="warning")
            return

        try:
            # Get the percentage from the input field
            input_field = self.query_one("#flow_input", Input)

            flowrate = float(input_field.value)

            self.manager.write_setpoint_manual(self.mfc_serial, flowrate)

        except Exception as e:
            self.log_message(f"Error sending flow rate: {e}")

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
                self.query_one("#real_percent_bar", CustomProgressBar).progress = self.current_percentage
                self.query_one("#valve_percent_bar", CustomProgressBar).progress = self.current_valve
                self.query_one("#temperature_label", Label).update(self.temperature)
                self.query_one("#flow_label", Label).update(self.flowrate)

        except Exception as e:
            if self.manager.is_connected:
                self.log_message(f"Error updating display: {e}")


class BronkhorstWidget(Widget):
    DEFAULT_CSS = """
    BronkhorstWidget {
        border: solid $accent round;
        margin: 0;
        column-span: 10;
        row-span: 9;
    }

    #MFC_BOX {
        border: solid $accent blank;
        margin: 0;
        layout: vertical;
        scrollbar-size: 1 1;
        height: auto;
        border-title-align: left;
    }

    #title {
        height: auto;
        margin: 0;
        border: solid $accent round;
        align: center middle;
    }

    #dash_container {
        layout: horizontal;
        align: left middle;
        height: 3;
        margin: 1;
    }

    .comm_button {
        align: left middle;
        margin-left: 1;
        margin-right: 1;
    }

    #connection_logs {
        height: 4;
        width: 75;
        margin: 0;
    }
    
    #connection_status {
        height: 3;
        width: 25;
        margin: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.manager = DeviceManager.get_instance()

    def compose(self) -> ComposeResult:
        # Dashboard controls container
        with Horizontal(id="dash_container"):
            yield Button("Connect", id="connect_button", variant="success", classes="comm_button")
            yield Button("Abort", id="abort_button", variant="error", classes="comm_button")
            yield Label("Polling status: NaN", id="connection_status", classes="polling_status")

        # MFC modules container
        mfc_box = ScrollableContainer(id="MFC_BOX")
        mfc_box.border_title = ""

        with mfc_box:
            for devices in device_db:
                device_serial = device_db[devices].serial
                yield MFCModule(mfc_serial=device_serial)

    def on_mount(self) -> None:
        """Initialize widget state when mounted"""
        # TODO: Implement connection monitoring
        # TODO: Implement polling indicator
        # TODO: Implement connection status for individual devices
        # TODO: Add disconnection handling
        # TODO: Add abort button functionality

    @on(Button.Pressed, "#connect_button")
    def connect(self) -> None:
        self.log_message("Attempting to connect...")

        try:
            # Call init_sequence and let exceptions propagate
            self.manager.init_sequence()
            self.log_message(f"Connected to {len(self.manager.connected_devices)} device(s)")
            self.log_message("Connected devices: " + str(self.manager.connected_devices))
            self.measurement_package_updates()

            if self.manager.disconnected_devices is not None:
                self.log_message("Unable to connect to: " + str(self.manager.disconnected_devices))

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
                self.manager.write_setpoint_manual(aborted_device.get('serial'), 0)
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
        log = self.app.query_one("#connection_logs", Log)
        log.write_line(f"{time.strftime('%H:%M:%S')} {message}")

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

    def update_all_mfc_measurements(self) -> None:
        """Update all MFC modules with the latest measurement data"""
        # First read all parameters from all devices in one batch
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
