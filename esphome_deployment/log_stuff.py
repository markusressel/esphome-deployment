import logging

from rich.logging import RichHandler


class ProgressAwareLoggingHandler(RichHandler):
    """
    A logging handler that uses a specific Rich Console
    to ensure logs don't break the Live progress display.
    """

    def __init__(self, console, *args, **kwargs):
        super().__init__(
            console=console,
            markup=True,
            rich_tracebacks=True,
            *args, **kwargs
        )
        # Custom format string: pulls 'device' from the LogRecord
        # The -20 ensures the device names align in a nice column
        self.setFormatter(logging.Formatter(
            fmt="[bold cyan]%(device)-20s[/] %(message)s",
            datefmt="[%X]"
        ))

    def emit(self, record):
        # Fallback if a log is fired outside of a worker (no 'device' extra)
        if not hasattr(record, "device"):
            record.device = "system"
        super().emit(record)
