from ui.main_app import RSM_DAQ_Toolbox
from device_managers.device_manager_bronkhorst import DeviceManager


if __name__ == "__main__":

    device_manager = DeviceManager.get_instance()
    app = RSM_DAQ_Toolbox()
    app.run()
    print("App closed")

    try:
        device_manager.abort_all()
        print("All devices aborted")
        device_manager.stop()
        print("Device manager stopped")

    except Exception as e:
        print(f"Error stopping device manager: {e}")
