from textual.app import App, ComposeResult
from textual import on
from textual.widgets import (
	Footer,
	Header,
	Placeholder,
	TabbedContent,
	TabPane,
	Button,
	RichLog,
)
from textual.containers import Horizontal, Vertical
from ui.bronkhorst_widget import BronkhorstWidget, MFCModule
from ui.flow_calculator import FlowCalculator
from device_managers.device_manager_bronkhorst import DeviceManager

class RSM_DAQ_Toolbox(App):
	CSS_PATH = "CSS_main.tcss"
	
	BINDINGS = [
			("ctrl+q", "quit", "Quit"),
	]
	
	def __init__(self) -> None:
		super().__init__()
		self.manager = DeviceManager.get_instance()
		self.BronkhorstWidget = BronkhorstWidget
	
	def compose(self) -> ComposeResult:
		
		logs = RichLog(
				id="connection_logs",
				highlight=True,
				classes="log",
				auto_scroll=True,
				markup=True,
				wrap=True,
		)
		
		yield Header(icon="Menu", show_clock=True)
		yield Footer(show_command_palette=True)
		
		with Vertical():
			
			with TabbedContent(id="tabbed_content"):
				
				with TabPane(title="MFC Dashboard", id="manual_control_tab"):
					with Horizontal():
						yield BronkhorstWidget()
				
				with TabPane("Sensors", id="sensor_tab"):
					yield Placeholder("Placeholder for sensors")
				
				with TabPane("Database", id="database_tab"):
					yield Placeholder("Placeholder for database")
			
			with Horizontal(id="bottom_container"):
				
				with Horizontal(id="bottom_menu"):
					with Vertical(id="bottom_menu_buttons"):
						yield Button("Connect", id="connect_button", variant="primary")
						yield Button("Abort", id="abort_button", variant="error")
						yield Button("Reset", id="reset_button", variant="default")
						# yield Button("Reload Config",   id="reload_config_button",  variant="default")
					
					# with Vertical(id="bottom_menu_select"):
					#     yield Select(prompt="Port", id="port_select", options=options)
				
				yield FlowCalculator()
				
				yield logs  # connection logs
	
	def on_mount(self) -> None:
		self.title = "RSM MFC Control Toolbox"
		self.query_one("#connection_logs", RichLog).write(
				"Welcome to the RSM MFC Control Toolbox!"
		)
		self.query_one("#connection_logs", RichLog).write(
				"Logs will be displayed here.\n"
		)
	
	@on(Button.Pressed,"#connect_button")
	def connect(self) -> None:
		
		try:
			# Call init_sequence and let exceptions propagate
			self.manager.init_sequence()
			self.query_one("#connection_logs", RichLog).write( f"Connected to {len(self.manager.connected_devices)} device(s)")
			self.query_one("#connection_logs", RichLog).write( "Connected devices: " + str(self.manager.connected_devices))
			
			bronkhorst_widget_instance = self.query_one(BronkhorstWidget)
			
			bronkhorst_widget_instance.measurement_package_updates()
			
			if self.manager.disconnected_devices is not None:
				self.query_one("#connection_logs", RichLog).write("Unable to connect to: " + str(self.manager.disconnected_devices))
		
		except ConnectionError as e:
			# Handle the specific error with the original message
			self.query_one("#connection_logs", RichLog).write(f"{e}")
		except Exception as e:
			# Handle any other unexpected exceptions
			self.query_one("#connection_logs", RichLog).write(f"Connection error wid: {e}")
			
	@on(Button.Pressed,"#reset_button")
	def reset_colors(self) -> None:
		mfc_modules = list(self.app.query(MFCModule))
		theme_background_color, color = self.app.background_colors
		
		for mfc_module in mfc_modules:
			mfc_module.styles.background = color
			mfc_module.styles.opacity = "100%"

# TODO: add com port select, add abort
# TODO; add color coding for bundles, and sort by bundle
