import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, cast

from rich.console import Console
from rich.progress import TaskID

from esphome_deployment.deployment import CompileOptions, UploadOptions
from esphome_deployment.deployment.deployment_manager import DeploymentManager, UploadFailedException, CompileFailedException, DeploymentDisabledException
from esphome_deployment.persistence import DeploymentPersistence
from esphome_deployment.ui.parallel_progress import ParallelProgress, WorkerResults, WorkerResultCustom


class DeploymentCoordinator:
    """
    Used to coordinate the deployment of multiple configurations in parallel.
    """
    LOGGER = logging.getLogger(__name__)

    def __init__(self, console: Console, persistence: DeploymentPersistence):
        self._console = console
        self._persistence = persistence

    def _run_in_parallel(
        self,
        names: List[str],
        worker_fn,
        path: Path,
        *args,
        max_workers: int = 4,
        **kwargs
    ):
        """
        Runs the given worker_fn (callable accepting (name, path, *args, **kwargs)) in a thread pool
        and displays a parallel progress spinner per deployment using ParallelProgress.

        Note: Also does this if there is only one name, to ensure consistent output and progress display.
        """
        with ParallelProgress(console=self._console) as progress:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(names))) as executor:
                future_to_name = {}
                for name in names:
                    raw_task_id = progress.add_task(name)
                    task_id = cast(TaskID, raw_task_id)
                    future = executor.submit(self._wrapped_worker, progress, task_id, worker_fn, name, path, *args, **kwargs)
                    future_to_name[future] = name

                # IMPORTANT: Do not call future.result() in a loop that blocks
                # the whole method if you want to see updates.
                # Rich's Live display runs in its own background thread,
                # but we need to ensure we don't exit the 'with' block prematurely.

                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        # This will now only block until THE NEXT future is done,
                        # allowing the progress bars for others to continue spinning.
                        future.result()
                    except Exception as e:
                        self.LOGGER.error(f"Deployment for '{name}' failed: {e}")

    def _wrapped_worker(self, progress: ParallelProgress, task_id: TaskID, worker_fn, name: str, path: Path, *args, **kwargs):
        # create a manager per thread
        logger_adapter = logging.LoggerAdapter(self.LOGGER, {"device": name})
        deployment_manager = DeploymentManager(persistence=self._persistence, logger=logger_adapter)
        try:
            progress.set_running(task_id)
            worker_fn(deployment_manager, name, path, *args, **kwargs)
            progress.mark_done(task_id, result=WorkerResults.SUCCESS)
        except Exception as ex:
            if isinstance(ex, UploadFailedException):
                worker_result = WorkerResultCustom(state="Upload Failed", is_success=False)
            elif isinstance(ex, CompileFailedException):
                worker_result = WorkerResultCustom(state="Compile Failed", is_success=False)
            elif isinstance(ex, DeploymentDisabledException):
                worker_result = WorkerResults.Disabled
            else:
                worker_result = WorkerResults.FAILURE
            progress.mark_done(task_id, result=worker_result)
            raise

    def clean(
        self,
        name: str | List[str],
        path: Path
    ):
        """
        Cleans the deployment for a specific configuration
        :param name: the name of the deployment (filename without extension)
        :param path: the path where the configuration file is located
        """
        if isinstance(name, str):
            name = [name]

        # TODO: also utilize DeploymentCoordinator

        for single_name in name:
            deployment_manager = DeploymentManager(persistence=self._persistence, logger=self.LOGGER)
            deployment_manager.clean(name=single_name, path=path)

    def compile(
        self,
        name: str | List[str],
        path: Path,
        compile_options: CompileOptions = CompileOptions()
    ):
        """
        Compiles a specific configuration
        :param name: the name of the deployment (filename without extension)
        :param path: the path where the configuration file is located
        :param compile_options: options for compilation
        """
        if isinstance(name, str):
            name = [name]

        def _worker(manager: DeploymentManager, single_name: str, path: Path, compile_options: CompileOptions):
            manager.compile(
                name=single_name,
                path=path,
                compile_options=compile_options
            )

        self._run_in_parallel(name, _worker, path, compile_options)

    def upload(
        self,
        name: str | List[str],
        path: Path,
        upload_options: UploadOptions = UploadOptions()
    ):
        """
        Uploads a specific configuration
        :param name: the name of the deployment (filename without extension)
        :param path: the path where the configuration file is located
        :param upload_options: options for upload
        """
        if isinstance(name, str):
            name = [name]

        def _worker(manager: DeploymentManager, single_name: str, path: Path, upload_options: UploadOptions):
            manager.upload(
                name=single_name,
                path=path,
                upload_options=upload_options
            )

        self._run_in_parallel(name, _worker, path, upload_options)

    def deploy(
        self,
        name: str | List[str],
        path: Path,
        compile_options: CompileOptions = CompileOptions(),
        upload_options: UploadOptions = UploadOptions()
    ):
        """
        Deploys a specific configuration
        :param name: the name of the deployment (filename without extension)
        :param path: the path where the configuration file is located
        :param compile_options: options for compilation
        :param upload_options: options for upload
        """
        if isinstance(name, str):
            name = [name]

        def _worker(manager: DeploymentManager, single_name: str, path: Path, compile_options: CompileOptions, upload_options: UploadOptions):
            manager.deploy(
                name=single_name,
                path=path,
                compile_options=compile_options,
                upload_options=upload_options
            )

        self._run_in_parallel(name, _worker, path, compile_options, upload_options)
