import logging
from pathlib import Path
from typing import List

from esphome_deployment.deployment import CompileOptions, UploadOptions
from esphome_deployment.deployment.deployment_manager import DeploymentManager


class DeploymentCoordinator:
    """
    Used to coordinate the deployment of multiple configurations in parallel.
    """
    LOGGER = logging.getLogger(__name__)

    def __init__(self, persistence=None):
        self._persistence = persistence

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

        for single_name in name:
            deployment_manager = DeploymentManager(persistence=self._persistence)
            deployment_manager.compile(
                name=single_name,
                path=path,
                compile_options=compile_options
            )

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

        for single_name in name:
            deployment_manager = DeploymentManager(persistence=self._persistence)
            deployment_manager.upload(
                name=single_name,
                path=path,
                upload_options=upload_options
            )

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

        for single_name in name:
            deployment_manager = DeploymentManager(persistence=self._persistence)
            deployment_manager.deploy(
                name=single_name,
                path=path,
                compile_options=compile_options,
                upload_options=upload_options
            )
