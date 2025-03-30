from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Placeholder, TabbedContent, TabPane, Log, Button
from textual import on

from ui.bronkhorst_widget import BronkhorstWidget
from ui.flow_calculator import FlowCalculator


class RSM_DAQ_Toolbox(App):
    CSS = """

    Screen {
        layout: grid;
        grid-size: 16 9;
    }

    #title {
        row-span: 1;
        column-span: 16;
        border: solid $accent round;
        margin: 0;
    }

    #tabbed_content {
        row-span: 9;
        column-span: 6;
        border: solid $accent round;
        margin: 0;
        height: 100%;
    }

    .log {
    text-wrap: wrap;
    }

    #sensor {
        margin: 0;
    }
    
    #calculator {
        margin: 0;
    }

    """

    BINDINGS = [
            ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:

        logs = Log(id="connection_logs", highlight=True, classes="log", auto_scroll=True)
        logs.styles.text_wrap = "wrap"

        yield Header(icon="Menu", show_clock=True)
        yield Footer(show_command_palette=True)

        yield BronkhorstWidget()

        with TabbedContent(id="tabbed_content"):
            with TabPane("Logs"):
                yield Button("Clear", id="clear_logs", variant="primary")
                yield logs
            with TabPane("Sensors"):
                yield Placeholder("Placeholder for sensors")
            with TabPane("Calculator", id="calculator"):
                yield FlowCalculator()

    def on_mount(self) -> None:
        self.title = "RSM Data Acquisition Toolbox"
        self.query_one("#connection_logs", Log).write_line(f"Press Connect to start")

    @on(Button.Pressed, "#clear_logs")
    def clear_logs(self) -> None:
        self.query_one("#connection_logs", Log).clear()
