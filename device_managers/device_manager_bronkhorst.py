import logging

import propar
import sys
import time
import device_database.config_loader_bronkhorst
import numpy as np
import warnings

class DeviceManager:
    """
    Manager class for the Bronkhorst devices. Only one instance of this class should be created.
    This class is a singleton and should be accessed via the get_instance() method in "main.py" file.
    """

    _instance = None

    def __init__(self):
        self.config_loader      = device_database.config_loader_bronkhorst.load_config()  # Load the config data
        self.device_db          = self.config_loader.devices        # Pull device data from database_bronkhorst file
        self.connection_config  = self.config_loader.connection     # Pull connection config from database_bronkhorst file
        self.bundles            = self.config_loader.mfc_bundles.bundles    # Pull bundle data from database_bronkhorst file
        self.setup              = self.config_loader.setup          # Pull setup data from database_bronkhorst file
        self.config_info        = self.config_loader.configuration_info # Pull config info from database_bronkhorst file

        self.is_connected       = False  # Connection status of the device

        self.active_port        = None   # Active communication port, fetched from the config data.

        self.propar_device      = None   # Propar instrument object for the active port
        self.connected_devices  = {}     # List of connected devices through RS232 on the active port
        self.matched_devices    = {}     # Dict of matching devices serial to node address
        self.missing_devices    = {}     # Dict of missing devices serial to node address
        self.new_devices        = {}     # Dict of new devices serial to node address

        self.data_package       = {}     # Reading data package from the device
        self.read_parameters    =  [{'proc_nr': 1,    'parm_nr': 0, 'parm_type': propar.PP_TYPE_INT16},  # Measure
                                    {'proc_nr': 1,    'parm_nr': 1, 'parm_type': propar.PP_TYPE_INT16},  # Setpoint
                                    {'proc_nr': 33,   'parm_nr': 7, 'parm_type': propar.PP_TYPE_FLOAT},  # Temperature
                                    {'proc_nr': 114,  'parm_nr': 1, 'parm_type': propar.PP_TYPE_INT32}]  # Valve output

    @classmethod
    def get_instance(cls):
        """
        Singleton pattern to get the instance of DeviceManager.
        Used to ensure only one instance of DeviceManager is created.
        """
        if cls._instance is None:
            cls._instance = DeviceManager()
        return cls._instance

    def set_active_port(self):
        """This method takes the connection port from config file and checks the operating system."""

        self.active_port = self.connection_config.port

        # Check if the active port is valid and exists
        if sys.platform.startswith('win'):
            if not self.active_port.startswith("COM"):
                raise ValueError("Invalid port name, expected format: COMx")
        elif sys.platform.startswith('darwin'):
            if not self.active_port.startswith("/dev/cu."):
                raise ValueError("Invalid port name, expected format: /dev/cu.")
        return True

    def connect_RS232(self):
        """Connect to the device via RS232 using the active port."""

        # Fetch the active port and check if it is valid
        self.set_active_port()

        try:
            # Create an instrument object for the active port
            self.propar_device = propar.instrument(self.active_port)
            self.is_connected  = True
            return True
        except Exception as e:
            self.is_connected  = False
            self.propar_device = None
            raise ConnectionError(f"RS232 Connection Error: {e}")

    def get_connected_devices(self):
        """Get the data of the connected devices"""

        try:
            """
            .get_nodes() returns a list of dictionaries with the following keys
            - address   : The node address of the device
            - type      : The type of the device
            - serial    : The serial number of the device (eg. M23208425A)
            - id        : The id of the device
            - channel   : The channel of the device
            """

            # Get the connected device dictionary
            self.connected_devices = self.propar_device.master.get_nodes()

            # Check if the connected devices list is empty
            if len(self.connected_devices) == 0:
                raise ConnectionError("No devices found. Check connections and try again.")
            return True

        except Exception as e:
            raise ConnectionError(f"Error getting device data: {e}")

    def compare_devices(self):
        """Compares the connected devices with the device database

        Creates two dictionaries:
        - matched_devices: Maps device serials to their node addresses for devices in the database
        - missing_devices: Contains devices found but not in the database

        Returns:
            bool: True if comparison completed successfully, False otherwise
        """
        try:
            # Reset dictionaries to ensure clean state
            self.matched_devices = {}
            self.missing_devices = {}
            self.new_devices = {}

            if not self.connected_devices:
                return False

            # Iterate through connected devices
            for connected_device in self.connected_devices:
                device_serial = connected_device.get('serial')
                if not device_serial:
                    continue

                # Check if the device serial is in the database
                if device_serial in self.device_db:
                    # Device found in database - add to matched devices
                    self.matched_devices[device_serial] = connected_device['address']
                else:
                    # Device not in database - add to new devices
                    self.new_devices[device_serial] = connected_device['address']

            # Check for missing devices
            for device_serial in self.device_db:
                if device_serial not in self.matched_devices:
                    # Device not found in connected devices - add to missing devices
                    self.missing_devices[device_serial] = None
            return True

        except Exception as e:
            print(f"Error comparing devices: {e}")
            return False

    def init_sequence(self):
        """Initialize the device connection sequence"""
        try:
            # Connect and perform initialization steps
            self.connect_RS232()
            self.get_connected_devices()

            if not self.compare_devices():
                raise ConnectionError("Failed to match devices with database")
            return True

        except Exception as e:
            # Ensure cleanup on failure
            if self.propar_device is not None:
                self.stop()
            error_message = f"Initialization sequence failed: {e}"
            raise ConnectionError(error_message) from e

    def write_setpoint_manual(self, device_serial: str, input_setpoint: float,
                              is_percentage: bool = False, bypass: bool = False):

        """
        Handles the setpoint writing to the device. It takes the input setpoint and converts it to a percentage if needed.
        It also handles the bypass flag and checks if the setpoint is within the range of 0-100%.
        """

        # Check if the input setpoint is a percentage or a flow rate
        if not is_percentage:
            # Convert the flow rate setpoint to percentage
            max_capacity     = self.device_db[device_serial].m3n_h_capacity     # Get the maximum capacity of the device
            input_percentage = (input_setpoint / max_capacity) * 100            # Convert the setpoint to percentage
        else:
            # Use the input percentage directly
            input_percentage = input_setpoint

        # Check if the bypass flag is set, if not, set the calibration
        if not bypass:
            calibrated_percentage = self.set_calibration(device_serial = device_serial, raw_percentage = input_percentage)
        else:
            # If bypass is set, use the input percentage directly
            calibrated_percentage = input_percentage

        # Check if the percentage is within the range
        if calibrated_percentage < 0 or calibrated_percentage > 100:
            print(f"Setpoint percentage out of range: {calibrated_percentage}")
            return False

        # Convert the percentage to the setpoint value, 0-100% = 0-32000.
        # Any difference in percentage less than 0.003125% will not change the setpoint
        setpoint_value = int((calibrated_percentage/100) * 32000)

        try:
            self.propar_device.address = self.matched_devices[device_serial]  # Get the node address of the device
            self.propar_device.writeParameter(9, setpoint_value)              # Set the setpoint of the device
            return True

        except Exception as e:
            print(f"Error writing setpoint: {e}")
            return False

    def set_calibration(self, device_serial: str, raw_percentage: float):
        """Converts the input percentage to calibrated value according to configuration polynomial coefficients
        Then converts the calibrated value to converted value according to configuration polynomial coefficients"""

        calibration_coef = np.array(self.device_db[device_serial].calib_poly)[::-1] # Calibration polynomial coeffs from database
        convertion_coef  = np.array(self.device_db[device_serial].conv_poly)[::-1]  # Conversion polynomial coeffs from database

        raw_input_calibrated = np.polyval(calibration_coef, raw_percentage)      # Convert the input percentage to calibrated value
        raw_input_converted = np.polyval(convertion_coef, raw_input_calibrated)  # Convert the calibrated value to converted value

        # Check if the input percentage is 0 or 100, and set the converted value accordingly
        if raw_percentage == 0:
            converted_value = 0
        elif raw_percentage == 100:
            converted_value = 100
        else:
            converted_value = raw_input_converted

        return converted_value

    def read_multiple_parameters(self):
        """Read multiple parameters at the same time from the device"""

        params = self.read_parameters

        try:
            # Create a new dictionary for atomic update
            new_data_package = {}

            for matched_device in self.matched_devices:
                self.propar_device.address = self.matched_devices[matched_device]
                max_cap = self.device_db[matched_device].m3n_h_capacity  # Get the maximum capacity of the device

                # Start the timer
                start_time = time.time()

                # Read the parameters
                package = self.propar_device.read_parameters(params)

                # Calculate response time in milliseconds
                response_time = round((time.time() - start_time) * 1000, 1)

                # Store values directly in the new dictionary
                new_data_package[matched_device] = {
                        "measure"     : (package[0]["data"]/32000) * max_cap,    # Convert to flow rate m3n/h
                        "setpoint"    :  package[1]["data"]/32000,               # Convert to fraction
                        "temperature" :  round(package[2]["data"], 2),           # Round to 2 decimal places
                        "valve_output":  package[3]["data"]/16777215,            # Convert to fraction
                        "ping"        :  response_time,                          # Response time
                }

            # Atomically replace the entire dictionary (thread-safe for reads)
            self.data_package = new_data_package
            return True

        except Exception as e:
            print(f"Error reading parameters: {e}")
            return False

    def blink(self, device_serial: str):

        """Blinks device according to the device serial number for physical location tracing"""

        # Get the node address of the device from the matched devices dict
        node = self.matched_devices[device_serial]

        # Assign the node address to the propar device
        self.propar_device.address = node

        # Blink the device, default duration 9 seconds
        self.propar_device.wink()

    def stop(self):
        """Stop the device"""
        try:
            if hasattr(self.propar_device, 'master'):
                self.propar_device.master.stop()
            self.is_connected = False
        except Exception as e:
            print(f"Error stopping device: {e}")

    def abort_all(self):
        """Set all devices to 0 and stop the device"""
        try:
            for aborted_device in self.matched_devices:
                self.propar_device.address = self.matched_devices[aborted_device]
                self.propar_device.writeParameter(9, 0)
        except Exception as e:
            print(f"Error aborting device: {e}")

    def soft_abort(self):
        """Set all fuel mfc to 0 and purge with n2"""

        self.purge()

        for fuel in self.setup.fuels:
            for device_serial, device_config in self.device_db.items():
                if device_config.user_fluid == fuel:
                    if device_serial in self.matched_devices:
                        self.propar_device.address = self.matched_devices[device_serial]
                        self.propar_device.writeParameter(9, 0)

    def purge(self):
        """Purge the device with N2"""

        # TODO: Connect tinkerforge relay to purge the device with N2
        warnings.warn("Purge function is not implemented yet. Connect tinkerforge relay to purge the device with N2")

    def write_setpoint_bundle(self, bundle: str, input_setpoint: float, cutoff_percent: float = 10, bypass: bool = False):
        """ Write setpoint to the bundle of devices. Logic is similar to write_setpoint_manual.
            Input setpoint is checked against the bundle max capacities and sent to the appropriate device.
            Input must be flow rate in m3n/h.
        """

        selected_device = None

        # Check if the bundle is valid
        if bundle not in self.bundles:
            raise ValueError(f"Invalid bundle: {bundle}")

        # Get the devices in the bundle
        devices = self.bundles[bundle]

        # Check which mfc to choose for the given flow rate
        for device_serial in devices:
            max_capacity = self.device_db[device_serial].m3n_h_capacity
            lower_cutoff = cutoff_percent * max_capacity

            if lower_cutoff <= input_setpoint <= max_capacity:
                # If the input setpoint is within the range of the device, set the setpoint
                selected_device = device_serial

        if selected_device is not None:
            self.write_setpoint_manual(selected_device, input_setpoint, is_percentage=False, bypass=bypass)
        else:
            return False


if __name__ == "__main__":

    # Example usage of the DeviceManager class

    # Create an instance of the DeviceManager
    dm = DeviceManager.get_instance()

    calibrated = dm.set_calibration('M23208425A', 0.5)
    print(dm.device_db['M23208425A'].calib_poly)
    print(dm.device_db['M23208425A'].conv_poly)
    print(f"Calibrated value: {calibrated}")

    bundles = dm.bundles

    for bundle in bundles:
        print(f"Bundle: {bundle}")
        for device in bundles[bundle]:
            print(f"Device: {device}")

    # # Connect to the device
    # dm.init_sequence()
    #
    # # Blink the devices on the matched devices
    # for device in dm.matched_devices:
    #     dm.blink(device)
    #     print(f"Blinking device {device} at node {dm.matched_devices[device]}")
    #
    #
    #
    # dm.stop()  # Stop the device


# def calibration_conversion(self, device_serial: str, set_input: float, direction='to_device'):
#     """
#     Converts values between device calibration and target calibration
#
#     Args:
#         device_serial: Device serial number
#         set_input: Value to convert (percentage or flow rate)
#         direction: 'to_device' or 'from_device'
#
#     Returns:
#         Converted value
#     """
#     calibration = self.device_db[device_serial].calib_poly
#     conversion = self.device_db[device_serial].conv_poly
#
#     if direction == 'to_device':
#         # Convert from target gas to device calibration (for setpoints)
#         # Use current approach with polynomial roots
#         calibration_poly = Poly([calibration[0] - set_input, calibration[1], calibration[2], calibration[3]])
#         calibration_root = calibration_poly.roots()[0]
#
#         conversion_poly = Poly([conversion[0] - calibration_root, conversion[1], conversion[2], conversion[3]])
#         conversion_root = conversion_poly.roots()[0]
#
#         return conversion_root
#
#     else:  # from_device
#         # Convert from device calibration to target gas (for measurements)
#         # Use pre-computed inverse polynomials or generate them
#
#         # Option 1: Generate inverse polynomials on-the-fly
#         inverse_conversion = create_inverse_polynomial(conversion)
#         inverse_calibration = create_inverse_polynomial(calibration)
#
#         # Apply inverse conversion first, then inverse calibration
#         inv_conv_poly = Poly(inverse_conversion)
#         intermediate_value = inv_conv_poly(set_input)
#
#         inv_calib_poly = Poly(inverse_calibration)
#         result = inv_calib_poly(intermediate_value)
#
#         return result
#
#
# def create_inverse_polynomial(coefficients, degree=3, num_points=100, x_range=(0, 1)):
#     """
#     Create an inverse polynomial where x and y axes are flipped
#
#     Args:
#         coefficients: Polynomial coefficients [a0, a1, a2, ...]
#         degree: Degree of inverse polynomial
#         num_points: Number of points for fitting
#         x_range: Range of x values to sample
#
#     Returns:
#         Coefficients of inverse polynomial
#     """
#     from numpy.polynomial import Polynomial as Poly
#     import numpy as np
#
#     # Create original polynomial
#     poly = Poly(coefficients)
#
#     # Generate points
#     x_points = np.linspace(x_range[0], x_range[1], num_points)
#     y_points = poly(x_points)
#
#     # Swap x and y
#     x_inverse = y_points
#     y_inverse = x_points
#
#     # Fit inverse polynomial
#     inverse_poly = Poly.fit(x_inverse, y_inverse, degree)
#
#     return inverse_poly.coef
