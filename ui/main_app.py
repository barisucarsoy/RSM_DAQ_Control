from textual.app import App, ComposeResult
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
from ui.bronkhorst_widget import BronkhorstWidget
from ui.flow_calculator import FlowCalculator



class RSM_DAQ_Toolbox(App):
	CSS_PATH = "CSS_main.tcss"
	
	BINDINGS = [
			("ctrl+q", "quit", "Quit"),
			
	]
	
	
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
						# yield Button("Reload Config",   id="reload_config_button",  variant="default")
					
					# with Vertical(id="bottom_menu_select"):
					#     yield Select(prompt="Port", id="port_select", options=options)
				
				yield FlowCalculator()
				
				yield logs  # connection logs
	
	def on_mount(self) -> None:
		self.title = "RSM MFC Control Toolbox"
		self.query_one("#connection_logs", RichLog).write(
				"Welcome to the RSM MFC Control Toolbox!\n"
		)
		self.query_one("#connection_logs", RichLog).write(
				"Logs will be displayed here.\n"
		)
	
	# def on_button_pressed(self, event: Button.Pressed) -> None:
	#     if event.button.id == "connect_button":
	#         self.query_one("#connection_logs", RichLog).styles.background = "blue"
	#     elif event.button.id == "abort_button":
	#         self.query_one("#connection_logs", RichLog).styles.background = "red"


# TODO: change color of active modules
# TODO: add a button to connect to the mfc, add com port select, add abort
# TODO: add color changes for calculated mfcs and when the flow rate is reached
# TODO; add color coding for bundles, and sort by bundle
# TODO: implement the backend for the percentage input
# TODO: fix flow calculator
# TODO: fix connect
