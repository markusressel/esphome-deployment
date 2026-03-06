from rich.logging import RichHandler


class ProgressAwareLoggingHandler(RichHandler):
    """
    A logging handler that uses a specific Rich Console
    to ensure logs don't break the Live progress display.
    """

    def __init__(self, console, *args, **kwargs):
        super().__init__(console=console, *args, **kwargs)
