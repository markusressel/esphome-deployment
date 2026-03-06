import logging
from datetime import datetime

from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text

from esphome_deployment.ui.util import get_device_color


class ProgressAwareLoggingHandler(RichHandler):
    """
    A logging handler that uses a specific Rich Console
    to ensure logs don't break the Live progress display.
    """

    # A simple list of vibrant colors supported by Rich
    COLORS = ["cyan", "magenta", "green", "yellow", "blue", "bright_red", "orange3"]

    def __init__(self, console: Console, *args, **kwargs):
        def format_time_ms(dt: datetime) -> Text:
            # Format to H:M:S.mmm
            time_str = dt.strftime("%H:%M:%S.%f")[:-3]
            return Text(f"[{time_str}]")

        super().__init__(
            console=console,
            markup=True,
            rich_tracebacks=True,
            show_time=True,
            log_time_format=format_time_ms,
            omit_repeated_times=False,
            *args,
            **kwargs
        )
        # set explicitly to None so the format_time_ms function is used for time formatting instead
        self.setFormatter(logging.Formatter(fmt="%(device_styled)s %(message)s"))

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
