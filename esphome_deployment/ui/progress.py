from __future__ import annotations

import logging
import threading
from abc import ABC
from typing import Dict, Optional

from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, TaskID

from esphome_deployment.log_stuff import ProgressAwareLoggingHandler
from esphome_deployment.ui.util import get_device_color


class WorkerResult(ABC):

    def is_success(self) -> bool:
        return False


class WorkerSucceeded(WorkerResult):

    def is_success(self) -> bool:
        return True

    def __str__(self):
        return "Success"


class WorkerFailed(WorkerResult):

    def __str__(self):
        return "Failed"


class WorkerResultCustom(WorkerResult):

    def __init__(self, state: str, is_success: bool):
        self.state = state
        self._is_success = is_success

    def is_success(self) -> bool:
        return self._is_success

    def __str__(self):
        return self.state


class WorkerResults:
    SUCCESS = WorkerSucceeded()
    FAILURE = WorkerFailed()


class ParallelProgress:
    """
    Simple helper to display per-deployment progress in parallel using rich.

    API:
      - add_task(name) -> task_id
      - mark_done(task_id, success=True)
      - context manager support (with ParallelProgress() as p: ...)

    This class uses an indeterminate spinner for each task since esphome's subprocesses do their own output.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.fields[name]}", justify="left"),
            TextColumn("[{task.fields[state_color]}]{task.fields[state]}[/]", justify="right"),
            BarColumn(bar_width=None),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=False,
        )
        self._task_map: Dict[TaskID, TaskID] = {}
        self._lock = threading.Lock()
        self._live: Optional[Live] = None

        self._handler = ProgressAwareLoggingHandler(console=self.console)

    def __enter__(self):
        # 1. Capture original handlers and replace with our Rich handler
        root_logger = logging.getLogger()
        self._original_handlers = root_logger.handlers[:]
        for h in self._original_handlers:
            root_logger.removeHandler(h)
        root_logger.addHandler(self._handler)

        # 2. start live rendering
        self._live = Live(
            self._progress,
            console=self.console,
            refresh_per_second=10,
            auto_refresh=True,
        )
        self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        # stop live rendering
        if self._live:
            self._live.__exit__(exc_type, exc, tb)
            self._live = None

        # Restore original logging handlers
        root_logger = logging.getLogger()
        root_logger.removeHandler(self._handler)
        for h in self._original_handlers:
            root_logger.addHandler(h)

    def add_task(self, name: str) -> TaskID:
        with self._lock:
            # Get the unique color for this specific device
            device_color = get_device_color(name)

            # We wrap the name in the color tag inside the 'name' field
            styled_name = f"[bold {device_color}]{name}[/]"

            raw_id = self._progress.add_task(
                "",
                name=styled_name,  # The name itself is now colored
                state="queued",
                state_color="dark-gray",  # State (queued/running) can stay neutral
                total=None
            )
            return TaskID(raw_id)

    def set_running(self, task_id: TaskID):
        with self._lock:
            self._progress.update(TaskID(task_id), state="running", state_color="cyan")

    def update_status(self, task_id: TaskID, state: str, color: str, progress: Optional[float] = None):
        """
        :param task_id: the id of the task to update (as returned by add_task)
        :param state: arbitrary text to display as the current state of this task
        :param color: the color to use for the state text (e.g. "green", "red", "yellow", "cyan", etc.)
        :param progress: 0 - 100
        """
        with self._lock:
            self._progress.update(TaskID(task_id), state=state, state_color=color, completed=progress)

    def _update_status(self, task_id: TaskID, state: str, color: str, progress: Optional[float] = None):
        """
        :param task_id: the id of the task to update (as returned by add_task)
        :param state: arbitrary text to display as the current state of this task
        :param color: the color to use for the state text (e.g. "green", "red", "yellow", "cyan", etc.)
        :param progress: 0 - 100
        """
        self._progress.update(TaskID(task_id), state=state, state_color=color, completed=progress, total=100)

    def mark_done(self, task_id: TaskID, result: WorkerResult = WorkerResults.SUCCESS):
        with self._lock:
            state = result.__str__()
            completed = 100 if result.is_success() else 0
            color = "green" if result.is_success() else "red"
            self._update_status(
                task_id=task_id,
                state=state,
                color=color,
                progress=completed
            )
            try:
                self._progress.stop_task(TaskID(task_id))
            except Exception:
                pass

    def stop(self):
        if self._live:
            self._live.stop()
            self._live = None
