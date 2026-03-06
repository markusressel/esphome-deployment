from __future__ import annotations

import threading
from typing import Dict, Optional

from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, TaskID


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

    def __enter__(self):
        # start live rendering
        self._live = Live(self._progress, console=self.console, refresh_per_second=10)
        self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        # stop live rendering
        if self._live:
            self._live.__exit__(exc_type, exc, tb)
            self._live = None

    def add_task(self, name: str) -> TaskID:
        with self._lock:
            raw_id = self._progress.add_task("", name=name, state="queued", state_color="yellow", total=None)
            task_id = TaskID(raw_id)  # ensure type for static checker
            self._task_map[task_id] = task_id
            return task_id

    def set_running(self, task_id: TaskID):
        with self._lock:
            self._progress.update(TaskID(task_id), state="running", state_color="cyan")

    def mark_done(self, task_id: TaskID, success: bool = True):
        with self._lock:
            state = "done" if success else "failed"
            color = "green" if success else "red"
            self._progress.update(TaskID(task_id), state=state, state_color=color, completed=0)
            try:
                self._progress.stop_task(TaskID(task_id))
            except Exception:
                pass

    def write(self, *args, **kwargs):
        # convenience passthrough
        self.console.print(*args, **kwargs)

    def stop(self):
        if self._live:
            self._live.stop()
            self._live = None
