import yaml
from typing import Dict, List, Any
from dataclasses import dataclass
import os
import numpy as np
from rich.console import Console
from rich.table import Table
import plotly.graph_objects as go


@dataclass
class ConfigurationInfo:
    owner: str
    name: str
    description: str
    date: str

@dataclass
class ConnectionConfig:
    port: str
    baudrate: int

@dataclass
class SetupConfig:
    fuels: List[str]
    oxidizers: List[str]
    inert_gases: List[str]
    misc: List[str]

@dataclass
class DeviceConfig:
    serial: str
    bundle: str
    user_fluid: str
    factory_fluid: str
    conv_poly: List[float]
    calib_poly: List[float]
    factory_unit: str
    factory_capacity: float
    m3n_h_capacity: float
    last_calibration: str

@dataclass
class MFCBundles:
    bundles: dict[Any, List[str]]

@dataclass
class BronkhorstConfig:
    configuration_info: ConfigurationInfo
    connection: ConnectionConfig
    setup: SetupConfig
    mfc_bundles: MFCBundles
    devices: Dict[str, DeviceConfig]


def load_config(config_path: str = "config_mfc.yaml") -> BronkhorstConfig:
    """Load and validate the Bronkhorst configuration from a YAML file."""
    console = Console()

    # Automatically resolve path relative to the config_loader module
    if not os.path.isabs(config_path):
        # Get directory where this config_loader module is located
        module_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(module_dir, config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, 'r') as file:
        config_data = yaml.safe_load(file)

    # Load configuration info
    config_info = ConfigurationInfo(
            owner=config_data['configuration_info']['owner'],
            name=config_data['configuration_info']['name'],
            description=config_data['configuration_info']['description'],
            date=config_data['configuration_info']['date']
    )

    # Load connection config
    conn_config = ConnectionConfig(
            port=config_data['connection']['port'],
            baudrate=config_data['connection']['baudrate']
    )

    # Load setup config
    setup_config = SetupConfig(
            fuels=config_data['setup']['fuel'],
            oxidizers=config_data['setup']['oxidizer'],
            inert_gases=config_data['setup']['inert_gases'],
            misc=config_data['setup']['misc']
    )

    # Combine all valid fluids from setup
    valid_fluids = setup_config.fuels + setup_config.oxidizers + setup_config.inert_gases + setup_config.misc

    # Convert MFC bundle list to a dictionary where bundle names are keys and values are empty lists
    # This will be populated with device serials later
    mfc_bundles_dict = {bundle_name: [] for bundle_name in config_data['mfc_bundles']}
    mfc_bundles = MFCBundles(bundles=mfc_bundles_dict)

    # Validate and load device configs
    devices = {}
    for serial, device_data in config_data['devices'].items():
        # Validate user fluid against setup
        user_fluid = device_data['user_fluid']
        if user_fluid not in valid_fluids:
            console.print(f"[yellow]Warning:[/yellow] Device {serial} uses fluid '{user_fluid}' not defined in setup")

        # Create the device config
        devices[serial] = DeviceConfig(
                serial=device_data['serial'],
                bundle=device_data['bundle'],
                user_fluid=device_data['user_fluid'],
                factory_fluid=device_data['factory_fluid'],
                conv_poly=device_data['conv_poly'],
                calib_poly=device_data['calib_poly'],
                factory_unit=device_data['factory_unit'],
                factory_capacity=device_data['factory_capacity'],
                m3n_h_capacity=device_data['m3n_h_capacity'],
                last_calibration=device_data['last_calibration']
        )

        # Assign device to the appropriate bundle based on tag
        device_tag = device_data['bundle']
        for bundle_name in mfc_bundles_dict:
            if bundle_name in device_tag:
                mfc_bundles_dict[bundle_name].append(serial)
                break

    return BronkhorstConfig(
            configuration_info=config_info,
            connection=conn_config,
            setup=setup_config,
            mfc_bundles=mfc_bundles,
            devices=devices
    )

def display_config_summary(config: BronkhorstConfig):
    """Display a summary of the configuration using Rich tables with enhanced formatting."""
    console = Console()

    # Configuration info table
    console.print(f"\n[bold blue]Configuration:[/bold blue] {config.configuration_info.name}")
    console.print(f"[dim]{config.configuration_info.description}[/dim]")
    console.print(f"Owner: {config.configuration_info.owner}, Last updated: {config.configuration_info.date}")

    # Connection info
    console.print(
        f"\n[bold blue]Connection:[/bold blue] {config.connection.port} @ {config.connection.baudrate} baud")

    # Setup info
    setup_table = Table(show_header=False, title="Setup Configuration", border_style="blue")
    setup_table.add_column("Category", style="cyan")
    setup_table.add_column("Values", style="white")
    setup_table.add_row("Fuels", ", ".join([f"[red]{fuel}[/red]" for fuel in config.setup.fuels]))
    setup_table.add_row("Oxidizers", ", ".join([f"[blue]{ox}[/blue]" for ox in config.setup.oxidizers]))
    setup_table.add_row("Inert gases", ", ".join([f"[green]{gas}[/green]" for gas in config.setup.inert_gases]))
    console.print(setup_table)

    # Color mapping for fluids
    fluid_colors = {
            "air": "blue",
            "h2" : "red",
            "ch4": "yellow",
            "n2" : "green",
            "o2" : "purple"
    }

    # Bundle groups - show tables for all bundles
    console.print("\n[bold blue]MFC Bundles:[/bold blue]")
    for bundle_name, serials in config.mfc_bundles.bundles.items():
        # Create a table for all bundles
        table = Table(title=f"{bundle_name} Bundle", border_style="cyan")
        table.add_column("Serial", style="cyan")
        table.add_column("Bundle", style="blue")
        table.add_column("Fluid", style="white")
        table.add_column("Capacity", style="white")
        table.add_column("10% Flow", style="green")
        table.add_column("50% Flow", style="yellow")
        table.add_column("100% Flow", style="red")

        # Add devices to the table
        if serials:
            for serial in serials:
                device = config.devices[serial]
                fluid_color = fluid_colors.get(device.user_fluid, "white")

                # Calculate flow rates at different percentages using calibration polynomial
                calib_coeff = device.calib_poly[::-1]
                flow_10 = np.polyval(calib_coeff, 10) * device.m3n_h_capacity / 100
                flow_50 = np.polyval(calib_coeff, 50) * device.m3n_h_capacity / 100
                flow_100 = np.polyval(calib_coeff, 100) * device.m3n_h_capacity / 100

                # Highlight the last 4 characters of serial number in bright magenta
                serial_display = f"{serial[:-4]}[bright_magenta]{serial[-4:]}[/bright_magenta]"

                table.add_row(
                        serial_display,
                        device.bundle,
                        f"[{fluid_color}]{device.user_fluid}[/{fluid_color}]",
                        f"{device.m3n_h_capacity:.3f} m³n/h",
                        f"{flow_10:.5f} m³n/h",
                        f"{flow_50:.5f} m³n/h",
                        f"{flow_100:.5f} m³n/h"
                )
        else:
            # Show empty table with a message if no devices for this bundle
            table.add_row("[italic]No devices[/italic]", "", "", "", "", "", "")

        console.print(table)

    # Devices summary table with calibration details
    console.print("\n[bold blue]Device Summary with Flow Calculations:[/bold blue]")
    devices_table = Table(title="All Devices", border_style="blue")
    devices_table.add_column("Serial", style="cyan")
    devices_table.add_column("Tag", style="blue")
    devices_table.add_column("Fluid", style="white")
    devices_table.add_column("Max Capacity", style="white")
    devices_table.add_column("Input 50%", style="yellow")
    devices_table.add_column("Calibrated 50%", style="green")
    devices_table.add_column("Converted 50%", style="red")
    devices_table.add_column("Last Cal.", style="magenta")

    # Calculate 50% values for each device
    for serial, device in config.devices.items():
        # Get device fluid color
        fluid_color = fluid_colors.get(device.user_fluid, "white")

        # Calculate calibrated value (using poly directly)
        calib_coeff = device.calib_poly[::-1]  # Reverse for numpy polyval
        input_50 = 50.0
        calibrated_val = np.polyval(calib_coeff, input_50)
        calibrated_flow = (calibrated_val / 100) * device.m3n_h_capacity

        # Calculate converted value (apply conversion poly on top of calibrated)
        conv_coeff = device.conv_poly[::-1]  # Reverse for numpy polyval
        converted_val = np.polyval(conv_coeff, calibrated_val)
        converted_flow = (converted_val / 100) * device.m3n_h_capacity

        # Highlight the last 4 characters of serial number in bright magenta
        serial_display = f"{serial[:-4]}[bright_magenta]{serial[-4:]}[/bright_magenta]"

        # Calculate raw flow at 50% input (before calibration)
        raw_flow_50 = (50.0 / 100) * device.m3n_h_capacity

        # Add row to table with calculated values
        devices_table.add_row(
                serial_display,
                device.bundle,
                f"[{fluid_color}]{device.user_fluid}[/{fluid_color}]",
                f"{device.m3n_h_capacity:.3f} m³n/h",
                f"50.00% ({raw_flow_50:.5f} m³n/h)",
                f"{calibrated_val:.2f}% ({calibrated_flow:.5f} m³n/h)",
                f"{converted_val:.2f}% ({converted_flow:.5f} m³n/h)",
                device.last_calibration
        )

    console.print(devices_table)

    # Flow calculation visualization
    console.print("\n[bold blue]Flow Calculation Path:[/bold blue]")
    flow_table = Table(show_header=False, border_style="green")
    flow_table.add_column("Step", style="cyan")
    flow_table.add_column("Description", style="white")
    flow_table.add_row(
            "[bold]1. Input Signal[/bold]",
            "The raw input setpoint (e.g., 50% of full scale)"
    )
    flow_table.add_row(
            "[bold]2. Calibration[/bold]",
            "Apply calibration polynomial to input → Calibrated value"
    )
    flow_table.add_row(
            "[bold]3. Conversion[/bold]",
            "Apply conversion polynomial to calibrated value → Converted value"
    )
    flow_table.add_row(
            "[bold]4. Flow Rate[/bold]",
            "Flow rate = (Converted value / 100) × Max capacity"
    )
    console.print(flow_table)

    # Visual representation of polynomial application
    console.print("\n[bold blue]Polynomial Application:[/bold blue]")
    console.print("[dim]For a value x, the polynomial a + b·x + c·x² + d·x³ is applied[/dim]")

    # Display example calculation for one device
    if config.devices:
        example_device = next(iter(config.devices.values()))
        console.print(f"\n[bold]Example for device {example_device.serial}:[/bold]")
        calib_poly = example_device.calib_poly
        conv_poly = example_device.conv_poly

        console.print(
                f"[yellow]Calibration polynomial:[/yellow] {calib_poly[0]:.4f} + {calib_poly[1]:.4f}·x + {calib_poly[2]:.4f}·x² + {calib_poly[3]:.4f}·x³")
        console.print(
                f"[yellow]Conversion polynomial:[/yellow] {conv_poly[0]:.4f} + {conv_poly[1]:.4f}·x + {conv_poly[2]:.4f}·x² + {conv_poly[3]:.4f}·x³")

        # Calculate values for the example
        input_val = 50.0
        calibrated = np.polyval(calib_poly[::-1], input_val)
        converted = np.polyval(conv_poly[::-1], calibrated)

        console.print(
                f"\n[green]Input 50%[/green] → [yellow]Calibration[/yellow] → [green]{calibrated:.4f}%[/green] → [yellow]Conversion[/yellow] → [green]{converted:.4f}%[/green]")

def plot_calibration_curves(config: BronkhorstConfig, show_plot=True, save_path=None):
    """
    Plot calibration polynomials for all devices using plotly.

    Args:
        config: The Bronkhorst configuration object
        show_plot: Whether to show the plot in browser (default: False)
        save_path: Path to save the plot as HTML file (default: None)

    Returns:
        The plotly figure object
    """
    console = Console()

    # Create the figure
    fig = go.Figure()

    # Generate x values from 0 to 100%
    x = np.linspace(0, 100, 1000)

    # Color mapping for different gas types with better contrast
    color_map = {
        "air": "#1f77b4",  # blue
        "h2": "#d62728",   # red
        "n2": "#2ca02c",   # green
        "ch4": "#ff7f0e",  # orange
        "o2": "#9467bd"    # purple
    }

    # Group devices by tag type for better organization
    tag_groups = {}
    for serial, device in config.devices.items():
        tag_base = device.bundle.split('_')[0] if '_' in device.bundle else device.bundle
        if tag_base not in tag_groups:
            tag_groups[tag_base] = []
        tag_groups[tag_base].append((serial, device))

    # Define dash patterns for different tag types
    dash_patterns = {
        "jet": "solid",
        "pilot": "dot",
        "coflow": "dash",
        "methane": "dashdot"
    }

    # Plot each device's calibration polynomial
    for tag_type, devices in tag_groups.items():
        for serial, device in devices:
            # Evaluate the calibration polynomial
            poly_coefficients = device.calib_poly
            y = np.polyval(poly_coefficients[::-1], x)  # Reverse coefficients for numpy polyval

            # Determine color based on gas type
            fluid_color = color_map.get(device.user_fluid, "gray")

            # Determine line style based on tag
            dash_type = "solid"
            for tag_base, pattern in dash_patterns.items():
                if tag_base in device.bundle:
                    dash_type = pattern
                    break

            # Add the trace for this device
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode='lines',
                    name=f"{device.bundle} ({device.serial})",
                    hovertemplate=(
                        f"Device: {device.serial}<br>"
                        f"Bundle: {device.bundle}<br>"
                        f"Input: %{{x:.2f}}%<br>"  # Note the double braces
                        f"Output: %{{y:.5f}}<br>"  # Note the double braces
                        f"Fluid: {device.user_fluid}<br>"
                        f"Capacity: {device.m3n_h_capacity} m³n/h"
                    ),
                    line=dict(
                        width=2,
                        color=fluid_color,
                        dash=dash_type
                    ),
                )
            )

    # Add a line at y=x for reference
    fig.add_trace(
        go.Scatter(
            x=x,
            y=x,
            mode='lines',
            name='Linear (y=x)',
            line=dict(color='gray', width=1, dash='dash'),
            opacity=0.5
        )
    )

    # Update layout for full screen and better readability
    fig.update_layout(
        title={
            'text': "Calibration Polynomials for All Devices",
            'y': 0.98,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        xaxis_title="Input (%)",
        yaxis_title="Output (%)",
        legend_title="Device",
        autosize=True,  # Use autosize instead of fixed dimensions
        hovermode="closest",
        template="plotly_white",
        margin=dict(l=80, r=80, t=100, b=80),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="lightgray",
            borderwidth=1
        ),
        font=dict(
            family="Arial, sans-serif",
            size=14
        ),
        plot_bgcolor='rgba(240, 240, 240, 0.8)'
    )

    # Add annotations for clearer context
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.01, y=0.01,
        text=f"Configuration: {config.configuration_info.name}<br>Date: {config.configuration_info.date}",
        showarrow=False,
        font=dict(size=12)
    )

    # Add grid lines for better readability
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray',
        zeroline=True,
        zerolinewidth=2,
        zerolinecolor='gray'
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray',
        zeroline=True,
        zerolinewidth=2,
        zerolinecolor='gray'
    )

    # Save the figure if a path is provided
    if save_path:
        try:
            # Create a custom HTML with more screen space
            with open(save_path, 'w') as f:
                plot_html = fig.to_html(
                    full_html=True,
                    include_plotlyjs='cdn',
                    config={
                        'displayModeBar': True,
                        'responsive': True,
                        'scrollZoom': True
                    }
                )
                # Insert a style tag to ensure the plot fills the entire viewport
                plot_html = plot_html.replace(
                    '</head>',
                    '<style>body {margin: 0; padding: 0; overflow: hidden;} '
                    '.plotly-graph-div {width: 100vw; height: 100vh;}</style></head>'
                )
                f.write(plot_html)
            console.print(f"[green]Plot saved to:[/green] {save_path}")
        except Exception as e:
            console.print(f"[red]Failed to save plot:[/red] {str(e)}")

    # Show the plot if requested (won't automatically launch browser otherwise)
    if show_plot:
        fig.show()

    return fig

def prompt_to_open_browser(file_path):
    """Prompt the user to open the HTML file in a browser. Only 'y' is accepted as confirmation."""
    import webbrowser
    import os
    from rich.console import Console

    console = Console()

    # Get the absolute path to the file
    abs_path = os.path.abspath(file_path)

    # Convert to a file URL
    file_url = f"file://{abs_path}"

    # Ask user if they want to open the file (custom implementation)
    console.print("[yellow]Open calibration curves in browser? (y/N)[/yellow]", end=" ")
    user_input = input().strip().lower()

    if user_input == "y":
        # Open in the default browser
        webbrowser.open(file_url, new=2)  # new=2 opens in a new tab if possible
        console.print(f"[green]Opened in browser:[/green] {file_url}")
    else:
        console.print(f"[blue]HTML file saved at:[/blue] {abs_path}")

    return file_url


# Example usage
if __name__ == "__main__":
    try:
        console = Console()
        config_path = "config_mfc.yaml"
        console.print(f"[bold]Loading configuration from[/bold] {config_path}")

        config = load_config(config_path)
        # for device in config.devices:
        #     console.print(device)
        #     console.print(config.devices[device].user_fluid)

        # Display configuration summary using Rich
        display_config_summary(config)

        # Plot calibration curves without showing browser
        console.print("\n[bold blue]Generating calibration curves...[/bold blue]")
        html_output_path = "calibration_curves.html"
        fig = plot_calibration_curves(
                config,
                show_plot=False,  # Don't automatically open browser
                save_path=html_output_path  # Save to file instead
        )

        # Prompt the user to open the HTML file
        file_url = prompt_to_open_browser(html_output_path)

        console.print("\n[green]Calibration analysis complete![/green]")

    except Exception as e:
        console = Console()
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback

        console.print(traceback.format_exc())
