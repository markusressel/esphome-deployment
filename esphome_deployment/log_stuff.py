import logging

from rich.logging import RichHandler

from esphome_deployment.ui.util import get_device_color


class ProgressAwareLoggingHandler(RichHandler):
    """
    A logging handler that uses a specific Rich Console
    to ensure logs don't break the Live progress display.
    """

    # A simple list of vibrant colors supported by Rich
    COLORS = ["cyan", "magenta", "green", "yellow", "blue", "bright_red", "orange3"]

    def __init__(self, console, *args, **kwargs):
        super().__init__(console=console, markup=True, rich_tracebacks=True, *args, **kwargs)
        self.setFormatter(logging.Formatter(fmt="%(device_styled)s %(message)s", datefmt="[%X]"))

    def emit(self, record):
        if not hasattr(record, "device"):
            # Default style for non-device logs
            record.device_styled = "[bold white]system              [/]"
        else:
            color = get_device_color(record.device)
            # Pad the name to 20 characters for perfect vertical alignment
            padded_name = f"{record.device:<20}"
            record.device_styled = f"[bold {color}]{padded_name}[/]"

        super().emit(record)
