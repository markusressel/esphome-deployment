from rich.progress import BarColumn


class DynamicBarColumn(BarColumn):
    """A BarColumn that changes color based on task fields."""

    def render(self, task):
        # Get the color from fields, default to 'bar.complete' if not set
        bar_complete_style = task.fields.get("bar_complete_style", "bar.complete")
        self.complete_style = bar_complete_style
        bar_finished_style = task.fields.get("bar_finished_style", "bar.finished")
        self.finished_style = bar_finished_style

        return super().render(task)
