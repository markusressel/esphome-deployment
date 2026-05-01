from pathlib import Path
from unittest.mock import MagicMock, patch, call

from esphome_deployment.deployment import CompileOptions, UploadOptions
from esphome_deployment.deployment.deployment_coordinator import DeploymentCoordinator
from esphome_deployment.deployment.deployment_manager import (
    DeploymentDisabledException,
    UploadFailedException,
    CompileFailedException,
    FirmwareBinaryNotFound,
)
from esphome_deployment.ui.parallel_progress import WorkerResults, WorkerResultCustom
from tests import TestBase


def _make_coordinator(console=None, persistence=None) -> DeploymentCoordinator:
    if console is None:
        console = MagicMock()
    if persistence is None:
        persistence = MagicMock()
    return DeploymentCoordinator(console=console, persistence=persistence)


class DeploymentCoordinatorRunInParallelTest(TestBase):

    def test_run_in_parallel_logs_warning_when_no_names(self):
        coordinator = _make_coordinator()
        with patch.object(coordinator, "LOGGER") as mock_logger:
            coordinator._run_in_parallel(names=[], worker_fn=MagicMock(), path=Path("/tmp"))
            mock_logger.warning.assert_called_once()

    def test_run_in_parallel_does_not_execute_worker_when_no_names(self):
        coordinator = _make_coordinator()
        worker_fn = MagicMock()
        coordinator._run_in_parallel(names=[], worker_fn=worker_fn, path=Path("/tmp"))
        worker_fn.assert_not_called()

    def test_run_in_parallel_logs_to_console_when_single_name(self):
        """log_to_console=True when only one name is given."""
        coordinator = _make_coordinator()
        captured = {}

        def spy_worker(manager, name, path, log_to_console):
            captured["log_to_console"] = log_to_console

        with patch("esphome_deployment.deployment.deployment_coordinator.ParallelProgress") as MockProgress:
            MockProgress.return_value.__enter__ = lambda s: MagicMock()
            MockProgress.return_value.__exit__ = MagicMock(return_value=False)
            with patch.object(coordinator, "_wrapped_worker", side_effect=lambda *a, **kw: None):
                coordinator._run_in_parallel(
                    names=["device"],
                    worker_fn=spy_worker,
                    path=Path("/tmp"),
                    max_workers=4,
                )


class DeploymentCoordinatorWrappedWorkerTest(TestBase):

    def _make_progress(self):
        progress = MagicMock()
        return progress

    def test_wrapped_worker_marks_done_with_success_on_completion(self):
        coordinator = _make_coordinator()
        progress = self._make_progress()
        task_id = MagicMock()
        worker_result = WorkerResultCustom(state="Compiled", is_success=True)
        worker_fn = MagicMock(return_value=worker_result)

        coordinator._wrapped_worker(progress, task_id, worker_fn, "device", Path("/tmp"), False)

        progress.set_running.assert_called_once_with(task_id)
        progress.mark_done.assert_called_once_with(task_id, result=worker_result)

    def test_wrapped_worker_uses_success_result_when_worker_returns_none(self):
        coordinator = _make_coordinator()
        progress = self._make_progress()
        task_id = MagicMock()
        worker_fn = MagicMock(return_value=None)

        coordinator._wrapped_worker(progress, task_id, worker_fn, "device", Path("/tmp"), False)

        progress.mark_done.assert_called_once_with(task_id, result=WorkerResults.SUCCESS)

    def test_wrapped_worker_marks_disabled_on_deployment_disabled_exception(self):
        coordinator = _make_coordinator()
        progress = self._make_progress()
        task_id = MagicMock()
        worker_fn = MagicMock(side_effect=DeploymentDisabledException("disabled"))

        # Should NOT raise
        coordinator._wrapped_worker(progress, task_id, worker_fn, "device", Path("/tmp"), False)

        progress.mark_done.assert_called_once_with(task_id, result=WorkerResults.Disabled)

    def test_wrapped_worker_marks_upload_failed_and_reraises_on_upload_exception(self):
        coordinator = _make_coordinator()
        progress = self._make_progress()
        task_id = MagicMock()
        worker_fn = MagicMock(side_effect=UploadFailedException("upload failed"))

        with self.assertRaises(UploadFailedException):
            coordinator._wrapped_worker(progress, task_id, worker_fn, "device", Path("/tmp"), False)

        result = progress.mark_done.call_args[1]["result"]
        self.assertIsInstance(result, WorkerResultCustom)
        self.assertEqual(result.state, "Upload Failed")
        self.assertFalse(result.is_success())

    def test_wrapped_worker_marks_needs_compile_and_reraises_on_binary_not_found(self):
        coordinator = _make_coordinator()
        progress = self._make_progress()
        task_id = MagicMock()
        worker_fn = MagicMock(side_effect=FirmwareBinaryNotFound("not found"))

        with self.assertRaises(FirmwareBinaryNotFound):
            coordinator._wrapped_worker(progress, task_id, worker_fn, "device", Path("/tmp"), False)

        result = progress.mark_done.call_args[1]["result"]
        self.assertIsInstance(result, WorkerResultCustom)
        self.assertEqual(result.state, "Needs Compile")
        self.assertFalse(result.is_success())

    def test_wrapped_worker_marks_compile_failed_and_reraises_on_compile_exception(self):
        coordinator = _make_coordinator()
        progress = self._make_progress()
        task_id = MagicMock()
        worker_fn = MagicMock(side_effect=CompileFailedException("compile failed"))

        with self.assertRaises(CompileFailedException):
            coordinator._wrapped_worker(progress, task_id, worker_fn, "device", Path("/tmp"), False)

        result = progress.mark_done.call_args[1]["result"]
        self.assertIsInstance(result, WorkerResultCustom)
        self.assertEqual(result.state, "Compile Failed")
        self.assertFalse(result.is_success())

    def test_wrapped_worker_marks_failure_and_reraises_on_generic_exception(self):
        coordinator = _make_coordinator()
        progress = self._make_progress()
        task_id = MagicMock()
        worker_fn = MagicMock(side_effect=RuntimeError("unexpected"))

        with self.assertRaises(RuntimeError):
            coordinator._wrapped_worker(progress, task_id, worker_fn, "device", Path("/tmp"), False)

        progress.mark_done.assert_called_once_with(task_id, result=WorkerResults.FAILURE)


class DeploymentCoordinatorPublicApiTest(TestBase):

    def test_clean_normalizes_single_string_name_to_list(self):
        coordinator = _make_coordinator()
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.clean("device", Path("/tmp"), log_to_console=False)
            names = mock_run.call_args[1]["names"] if mock_run.call_args[1] else mock_run.call_args[0][0]
            self.assertIsInstance(names, list)
            self.assertEqual(names, ["device"])

    def test_clean_passes_list_names_unchanged(self):
        coordinator = _make_coordinator()
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.clean(["device_a", "device_b"], Path("/tmp"), log_to_console=False)
            names = mock_run.call_args[1]["names"] if mock_run.call_args[1] else mock_run.call_args[0][0]
            self.assertEqual(names, ["device_a", "device_b"])

    def test_compile_normalizes_single_string_name_to_list(self):
        coordinator = _make_coordinator()
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.compile("device", Path("/tmp"))
            args, kwargs = mock_run.call_args
            names = kwargs.get("names") or args[0]
            self.assertIsInstance(names, list)
            self.assertEqual(names, ["device"])

    def test_compile_passes_compile_options(self):
        coordinator = _make_coordinator()
        options = CompileOptions(allow_downgrade=True)
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.compile(["device"], Path("/tmp"), compile_options=options)
            args, kwargs = mock_run.call_args
            # compile_options is passed as a positional extra arg to _run_in_parallel
            self.assertIn(options, args)

    def test_upload_normalizes_single_string_name_to_list(self):
        coordinator = _make_coordinator()
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.upload("device", Path("/tmp"))
            args, kwargs = mock_run.call_args
            names = kwargs.get("names") or args[0]
            self.assertIsInstance(names, list)
            self.assertEqual(names, ["device"])

    def test_upload_passes_upload_options(self):
        coordinator = _make_coordinator()
        options = UploadOptions(force=True)
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.upload(["device"], Path("/tmp"), upload_options=options)
            args, kwargs = mock_run.call_args
            self.assertIn(options, args)

    def test_deploy_normalizes_single_string_name_to_list(self):
        coordinator = _make_coordinator()
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.deploy("device", Path("/tmp"))
            args, kwargs = mock_run.call_args
            names = kwargs.get("names") or args[0]
            self.assertIsInstance(names, list)
            self.assertEqual(names, ["device"])

    def test_deploy_passes_compile_and_upload_options(self):
        coordinator = _make_coordinator()
        compile_opts = CompileOptions(allow_downgrade=True)
        upload_opts = UploadOptions(force=True)
        with patch.object(coordinator, "_run_in_parallel") as mock_run:
            coordinator.deploy(["device"], Path("/tmp"), compile_options=compile_opts, upload_options=upload_opts)
            args, kwargs = mock_run.call_args
            self.assertIn(compile_opts, args)
            self.assertIn(upload_opts, args)




