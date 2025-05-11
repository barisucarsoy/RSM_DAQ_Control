from device_managers.device_manager_bronkhorst import DeviceManager
from ui.main_app import RSM_DAQ_Toolbox

if __name__ == "__main__":

    # Initialize the device manager
    device_manager = DeviceManager.get_instance()
    app = RSM_DAQ_Toolbox()
    app.run()

    try:
        device_manager.abort_all()
        print("All devices aborted")

        device_manager.stop()
        print("Device manager stopped")

    except Exception as e:
        print(f"Error stopping device manager: {e}")
