from pygments import highlight
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Placeholder, TabbedContent, TabPane, Log, Button, RichLog
from textual.containers import Horizontal
import ui



class RSM_DAQ_Toolbox(App):
    CSS = """

    Screen {
        layout: grid;
    }

    #tabbed_content {
        border: solid $accent round;
        margin: 0;
        height: 100%;
    }
    
    #logs_tab {
        margin: 0;
    }
    
    #calculator_tab {
        margin: 0;
    }
    
    #sensor_tab {
        margin: 0;
    }
    
    #database_tab {
        margin: 0;
    }

    """

    BINDINGS = [
            ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:

        logs = RichLog(id="connection_logs", highlight=True, classes="log", auto_scroll=True, markup=True, wrap=True)

        yield Header(icon="Menu", show_clock=True)
        yield Footer(show_command_palette=True)

        with Horizontal():

            with TabbedContent(id="tabbed_content"):

                with TabPane(title="Manual Control", id="manual_control_tab"):
                    yield Placeholder("Placeholder for manual control")

                with TabPane(title="Logs", id="logs_tab"):
                    yield logs

                with TabPane("Calculator", id="calculator_tab"):
                    yield Placeholder("Placeholder for calculator")

                with TabPane("Sensors", id="sensor_tab"):
                    yield Placeholder("Placeholder for sensors")

                with TabPane("Database", id="database_tab"):
                    yield Placeholder("Placeholder for database")

    def on_mount(self) -> None:
        self.title = "RSM Data Acquisition Toolbox"
        self.query_one("#connection_logs", RichLog).write("Welcome to the RSM Data Acquisition Toolbox!\n")
        self.query_one("#connection_logs", RichLog).write("Logs will be displayed here.\n")
