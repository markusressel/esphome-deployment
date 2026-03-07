from __future__ import annotations

import threading
from abc import ABC
from typing import Dict, Optional

from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TaskID

from esphome_deployment.ui.dynamic_bar_column import DynamicBarColumn
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
    Disabled = WorkerResultCustom(state="Disabled", is_success=False)


class ParallelProgress:
    """
    Simple helper to display per-deployment progress in parallel using rich.

    API:
      - add_task(name) -> task_id
      - mark_done(task_id, success=True)
      - context manager support (with ParallelProgress() as p: ...)

    This class uses an indeterminate spinner for each task since esphome's subprocesses do their own output.
    """

    def __init__(self, console: Console):
        self.console = console
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.fields[name]}", justify="left"),
            TextColumn("[{task.fields[state_color]}]{task.fields[state]}[/]", justify="right"),
            DynamicBarColumn(
                bar_width=None,
            ),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )
        self._task_map: Dict[TaskID, TaskID] = {}
        self._lock = threading.Lock()
        self._live: Optional[Live] = None

    def __enter__(self):
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
                total=None,  # Indeterminate spinner, so total is None
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

    def _update_status(
        self,
        task_id: TaskID,
        state: str = None,
        color: str = None,
        bar_completed_style: str = None,
        bar_finished_style: str = None,
        progress: Optional[float] = None,
        total: Optional[float] = None,
        description: str = None,
        visible: bool = True
    ):
        """
        :param task_id: the id of the task to update (as returned by add_task)
        :param state: arbitrary text to display as the current state of this task
        :param color: the color to use for the state text (e.g. "green", "red", "yellow", "cyan", etc.)
        :param progress: 0 - 100
        """
        self._progress.update(
            task_id=TaskID(task_id),
            state=state,
            description=description,
            state_color=color,
            bar_completed_style=bar_completed_style,
            bar_finished_style=bar_finished_style,
            completed=progress,
            total=total,
            visible=visible,
        )

    def mark_done(self, task_id: TaskID, result: WorkerResult = WorkerResults.SUCCESS):
        with self._lock:
            state = result.__str__()
            total = 100
            if result.is_success():
                color = "green"
                completed = 100
            elif result is WorkerResults.Disabled:
                color = "grey37"  # Specific hex or rich color for 'Disabled'
                completed = 100  # Fill it 100% to show a solid grey bar for disabled tasks
            else:
                # FAILURE case
                color = "red"
                completed = 100  # Fill it 100% so we see a SOLID red bar

            self._update_status(
                task_id=task_id,
                state=state,
                color=color,
                bar_completed_style=color,
                bar_finished_style=color,
                total=total,
                progress=completed,
            )
            self._progress.stop_task(TaskID(task_id))

    def stop(self):
        if self._live:
            self._live.stop()
            self._live = None
