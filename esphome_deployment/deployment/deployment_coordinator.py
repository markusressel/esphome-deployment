import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, cast

from rich.progress import TaskID

from esphome_deployment.deployment import CompileOptions, UploadOptions
from esphome_deployment.deployment.deployment_manager import DeploymentManager
from esphome_deployment.ui.progress import ParallelProgress


class DeploymentCoordinator:
    """
    Used to coordinate the deployment of multiple configurations in parallel.
    """
    LOGGER = logging.getLogger(__name__)

    def __init__(self, persistence=None):
        self._persistence = persistence

    def _run_in_parallel(
        self,
        names: List[str],
        worker_fn,
        path: Path,
        *args,
        max_workers: int = 4, **kwargs
    ):
        """
        Runs the given worker_fn (callable accepting (name, path, *args, **kwargs)) in a thread pool
        and displays a parallel progress spinner per deployment using ParallelProgress.
        """
        # If only one job, run synchronously to preserve existing behavior/logging
        if len(names) <= 1:
            for single_name in names:
                deployment_manager = DeploymentManager(persistence=self._persistence)
                worker_fn(deployment_manager, single_name, path, *args, **kwargs)
            return

        tasks = {}
        with ParallelProgress() as progress:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(names))) as executor:
                future_to_name = {}
                for name in names:
                    # register a task in the progress UI
                    raw_task_id = progress.add_task(name)
                    task_id = cast(TaskID, raw_task_id)
                    # submit job
                    future = executor.submit(self._wrapped_worker, progress, task_id, worker_fn, name, path, *args, **kwargs)
                    future_to_name[future] = name

                # wait for all to finish and propagate exceptions after marking status
                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        future.result()
                    except Exception as e:
                        self.LOGGER.error(f"Deployment for '{name}' failed: {e}")

    def _wrapped_worker(self, progress: ParallelProgress, task_id: TaskID, worker_fn, name: str, path: Path, *args, **kwargs):
        # create a manager per thread
        deployment_manager = DeploymentManager(persistence=self._persistence)
        try:
            progress.set_running(task_id)
            worker_fn(deployment_manager, name, path, *args, **kwargs)
            progress.mark_done(task_id, success=True)
        except Exception:
            progress.mark_done(task_id, success=False)
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

        for single_name in name:
            deployment_manager = DeploymentManager(persistence=self._persistence)
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
