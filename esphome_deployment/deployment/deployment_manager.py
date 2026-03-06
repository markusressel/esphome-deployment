import datetime
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from esphome_deployment.deployment import EspHomeDeploymentConfiguration, CompileInfo, UploadInfo, CompileOptions, UploadOptions
from esphome_deployment.util import calculate_md5_file, calculate_md5_yaml_recursive, load_yaml_file
from esphome_deployment.util.semver import SemVerVersion


class UploadFailedException(Exception):
    pass

class DeploymentManager:
    LOGGER = logging.getLogger(__name__)

    BLACKLISTED_FILES = {
        "esphome_deployment.yaml",
        "secrets.yaml",
    }

    def __init__(self, persistence=None):
        self._persistence = persistence

    def clean(self, name: str, path: Path):
        """
        Cleans the deployment for a specific configuration
        :param name: the name of the deployment (filename without extension)
        :param path: the path where the configuration file is located
        """
        file_path = path / f"{name}.yaml"
        self.LOGGER.info(f"Cleaning deployment for configuration: {file_path}")
        file_paths = [file_path]
        deployment_configuration = self.load_deployment_configurations(file_paths)
        filtered_deployments = self.filter_deployments(deployment_configuration)
        for deployment_config in filtered_deployments:
            self.run_esphome(deployment_config, 'clean', str(file_path))

    def compile(
        self,
        name: str,
        path: Path,
        compile_options: CompileOptions = CompileOptions()
    ):
        """
        Compiles a specific configuration
        :param name: the name of the deployment (filename without extension)
        :param path: the path where the configuration file is located
        :param compile_options: options for compilation
        """
        file_path = path / f"{name}.yaml"
        file_paths = [file_path]
        deployment_configuration = self.load_deployment_configurations(file_paths)
        filtered_deployments = self.filter_deployments(deployment_configuration)
        self.compile_deployment_configs_if_needed(
            deployment_configs=filtered_deployments,
            compile_options=compile_options
        )

    def upload(self, name: str, path: Path, upload_options: UploadOptions = UploadOptions()):
        """
        Uploads a specific configuration
        :param name: the name of the deployment (filename without extension)
        :param path: the path where the configuration file is located
        :param upload_options: options for upload
        """
        file_path = path / f"{name}.yaml"
        file_paths = [file_path]
        deployment_configuration = self.load_deployment_configurations(file_paths)
        filtered_deployments = self.filter_deployments(deployment_configuration)
        for filtered_deployment in filtered_deployments:
            self.upload_deployment_config_if_needed(
                deployment_config=filtered_deployment,
                upload_options=upload_options
            )

    def deploy(
        self,
        name: str,
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
        file_path = path / f"{name}.yaml"
        file_paths = [file_path]
        deployment_configuration = self.load_deployment_configurations(file_paths)
        filtered_deployments = self.filter_deployments(deployment_configuration)
        self.deploy_deployment_configs_if_needed(
            deployment_configs=filtered_deployments,
            compile_options=compile_options,
            upload_options=upload_options
        )

    def find_esphome_configuration_files(self, directory: Path) -> List[Path]:
        """
        Finds all esphome configuration files in the given directory
        :param directory: the directory to search
        :return: a case-insensitive sorted list of paths to the found configuration files
        """
        toplevel_files = list(directory.glob('*.yaml'))
        filtered = [
            f for f in toplevel_files
            if not f.name.startswith('_') and f.name not in self.BLACKLISTED_FILES
        ]
        return list(sorted(filtered, key=lambda s: s.name.casefold()))

    def load_deployment_configurations(self, config_files: List[Path]) -> List[EspHomeDeploymentConfiguration]:
        """
        Loads deployment configurations from the given list of configuration files
        :param config_files: the list of configuration file paths
        :return: a list of EspHomeDeploymentConfiguration instances
        """
        deployment_configurations = []
        for config_file in config_files:
            deployment_config = self.load_deployment_configuration(config_file)
            deployment_configurations.append(deployment_config)
        return deployment_configurations

    @staticmethod
    def load_deployment_configuration(config_file: Path) -> EspHomeDeploymentConfiguration:
        """
        Loads a deployment configuration from the given configuration file
        :param config_file: the path to the configuration file
        :return: an EspHomeDeploymentConfiguration instance
        """
        loaded_config = load_yaml_file(config_file)

        deployment_config = EspHomeDeploymentConfiguration(
            file_path=config_file,
            parsed_yaml_content=loaded_config
        )
        return deployment_config

    def filter_deployments(
        self,
        deployment_configurations: List[EspHomeDeploymentConfiguration]
    ) -> List[EspHomeDeploymentConfiguration]:
        """
        Filters deployment configurations based on their deploy flag
        :param deployment_configurations: the list of deployment configurations to filter
        :return: a list of deployment configurations that should be deployed
        """
        self.LOGGER.debug(f"Filtering deployment configurations...")

        result = []
        for config in deployment_configurations:
            if not config.deploy:
                self.LOGGER.warning(f"Skipping deployment for '{config.filename}' as per 'deploy' flag.")
                continue

            result.append(config)

        return result

    def deploy_deployment_configs_if_needed(
        self,
        deployment_configs: List[EspHomeDeploymentConfiguration],
        compile_options: CompileOptions = CompileOptions(),
        upload_options: UploadOptions = UploadOptions(),
    ):
        """
        Processes the given list of deployment configurations
        :param deployment_configs:  the list of deployment configurations to process
        :param compile_options: options for compilation
        :param upload_options: options for upload
        """
        for config in deployment_configs:
            self.deploy_deployment_config_if_needed(config, compile_options=compile_options, upload_options=upload_options)

    def deploy_deployment_config_if_needed(
        self,
        deployment_config: EspHomeDeploymentConfiguration,
        compile_options: CompileOptions = CompileOptions(),
        upload_options: UploadOptions = UploadOptions(),
    ):
        """
        Deploys the given deployment configuration
        :param deployment_config: the deployment configuration to deploy
        :param compile_options: options for compilation
        :param upload_options: options for upload
        """
        self.LOGGER.info(f"Deploying configuration for: {deployment_config.name}")

        self.compile_deployment_config_if_needed(deployment_config=deployment_config, compile_options=compile_options)
        self.upload_deployment_config_if_needed(deployment_config=deployment_config, upload_options=upload_options)

    def compile_configuration(self, deployment_config: EspHomeDeploymentConfiguration):
        """
        Compiles the given deployment configuration
        :param deployment_config: the deployment configuration to compile
        """
        try:
            self.LOGGER.debug(f"Compiling configuration: {deployment_config.name}")
            self.run_esphome(deployment_config, 'compile', str(deployment_config.file_path))

            self.LOGGER.info(f"Successfully compiled configuration for '{deployment_config.name}'")
            self._remember_successful_compile(deployment_config)
        except Exception as e:
            self.LOGGER.error(f"Failed to compile configuration for '{deployment_config.name}': {e}")
            raise

    def upload_configuration(self, deployment_config: EspHomeDeploymentConfiguration):
        """
        Uploads the given deployment configuration to the target device
        :param deployment_config: the deployment configuration to upload
        """
        try:
            self.LOGGER.debug(f"Uploading configuration: {deployment_config.name}")

            ip_address = deployment_config.ip_address
            if ip_address:
                self.LOGGER.debug(f"Using custom IP address for upload: {ip_address}")
                self.run_esphome(deployment_config, 'upload', '--device', ip_address, str(deployment_config.file_path))
            else:
                self.run_esphome(deployment_config, 'upload', str(deployment_config.file_path))

            self.LOGGER.info(f"Successfully uploaded configuration for '{deployment_config.name}'")
            self._remember_successful_upload(deployment_config)
        except Exception as e:
            self.LOGGER.error(f"Failed to upload configuration for '{deployment_config.name}': {e}")
            raise UploadFailedException(f"Failed to upload configuration for '{deployment_config.name}': {e}") from e

    def _remember_successful_compile(self, deployment_config: EspHomeDeploymentConfiguration) -> CompileInfo:
        """
        Remembers that the given deployment configuration was successfully compiled.
        This can be used to avoid redeploying unchanged configurations in the future.

        :param deployment_config: the deployment configuration that was successfully compiled
        :return: a RememberedCompileInfo instance representing the remembered compile info
        """
        self.LOGGER.debug(f"Remembering successful compile for configuration: {deployment_config.name}")
        config_hash = self._calculate_config_hash(deployment_config)
        if config_hash is None:
            raise ValueError("Config hash cannot be None")
        esphome_version = self._get_current_esphome_version()
        binary_hash = self._calculate_firmware_binary_hash(deployment_config)
        if binary_hash is None:
            raise ValueError("Binary hash cannot be None")

        remembered_compile_info = CompileInfo(
            config_hash=config_hash,
            esphome_version=esphome_version,
            binary_hash=binary_hash,
        )
        self._persistence.save_compile_info(remembered_compile_info, deployment_config)

        return remembered_compile_info

    def _get_remembered_compile_info(self, deployment_config) -> Optional[CompileInfo]:
        return self._persistence.load_compile_info(deployment_config)

    def _remember_successful_upload(self, deployment_config: EspHomeDeploymentConfiguration):
        """
        Remembers that the given deployment configuration was successfully uploaded.
        This can be used to avoid redeploying unchanged configurations in the future.

        :param deployment_config: the deployment configuration that was successfully uploaded
        """
        self.LOGGER.debug(f"Remembering successful upload for configuration: {deployment_config.name}")

        binary_hash = self._calculate_firmware_binary_hash(deployment_config)
        if binary_hash is None:
            raise ValueError("Binary hash cannot be None")

        upload_info = UploadInfo(
            binary_hash=binary_hash,
            timestamp=datetime.datetime.now(),
        )
        self._persistence.save_upload_info(upload_info, deployment_config)

    def _get_remembered_upload_info(self, deployment_config: EspHomeDeploymentConfiguration) -> Optional[UploadInfo]:
        return self._persistence.load_upload_info(deployment_config)

    @staticmethod
    def _calculate_config_hash(deployment_config: EspHomeDeploymentConfiguration) -> str:
        """
        Calculates a hash for the given deployment configuration
        :param deployment_config: the deployment configuration to hash
        :return: a string representing the hash of the configuration
        """
        result = calculate_md5_yaml_recursive(
            root_path=deployment_config.file_path.parent,
            file_path=deployment_config.file_path,
        )
        return result

    @staticmethod
    def _calculate_firmware_binary_hash(deployment_config: EspHomeDeploymentConfiguration) -> Optional[str]:
        """
        Calculates a hash for the compiled firmware binary of the given deployment configuration
        :param deployment_config: the deployment configuration to hash
        :return: a string representing the hash of the compiled firmware binary
        """
        if not deployment_config.binary_file_path.exists():
            return None
        return calculate_md5_file(deployment_config.binary_file_path)

    def run_esphome(self, deployment_config: EspHomeDeploymentConfiguration, *args):
        """
        Runs the esphome command with the given arguments
        :param args: the arguments to pass to esphome
        """
        self.LOGGER.info(f"Executing esphome with arguments: {args}")

        # Create the logs directory if it doesn't exist
        log_dir = deployment_config.file_path.parent / ".deployment-logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create a unique filename: e.g., livingroom_compile_20231027_123005.log
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        command_name = args[0] if args else "unknown"
        log_file = log_dir / f"{deployment_config.name}_{command_name}_{timestamp}.log"

        self.LOGGER.info(f"Executing esphome {args} -> Logging to {log_file}")

        self._run_esphome_subprocess(log_file, *args)
        # self._run_esphome_module(*args)

    def _run_esphome_subprocess(self, log_file: Path, *args):
        with open(log_file, "w", encoding="utf-8") as f:
            # We use stdout=f and stderr=subprocess.STDOUT to merge both
            # streams into the same log file.
            subprocess.run(
                ['esphome', *args],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=True,
                text=True
            )

    def _run_esphome_module(self, *args):
        """
        TODO: Fails with strange errors, probably due to global state in esphome that is not properly reset between runs.
         Needs investigation.

        :param args:
        :return:
        """
        try:
            from esphome.__main__ import run_esphome as esphome_run_internal
            argv = ["esphome", *args]
            # This bypasses the zero-argument main() and goes to the logic
            exit_code = esphome_run_internal(argv)

            if exit_code != 0:
                raise RuntimeError(f"ESPHome exited with code {exit_code}")

        except Exception as e:
            self.LOGGER.error(f"ESPHome execution failed: {e}")
            raise

    @staticmethod
    def _get_current_esphome_version() -> SemVerVersion:
        """
        Gets the current version of esphome
        :return: a string representing the esphome version, e.g., "2025.12.2"
        """
        esphome_version = subprocess.check_output(['esphome', '--version']).decode().strip()
        esphome_version = esphome_version.replace("Version:", "").strip()
        return SemVerVersion(esphome_version)

    def compile_deployment_configs_if_needed(
        self,
        deployment_configs: List[EspHomeDeploymentConfiguration],
        compile_options: CompileOptions,
    ):
        """
        Compiles the given list of deployment configurations

        :param deployment_configs:  the list of deployment configurations to compile
        :param compile_options: options for compilation
        """
        for config in deployment_configs:
            self.compile_deployment_config_if_needed(
                deployment_config=config,
                compile_options=compile_options
            )

    def compile_deployment_config_if_needed(
        self,
        deployment_config: EspHomeDeploymentConfiguration,
        compile_options: CompileOptions,
    ):
        """
        Compiles a single deployment configuration
        :param deployment_config: the deployment configuration to compile
        :param compile_options: options for compilation
        """

        compile_info: CompileInfo = self._get_remembered_compile_info(deployment_config)

        if compile_info is not None:
            current_config_hash = self._calculate_config_hash(deployment_config)
            current_esphome_version = self._get_current_esphome_version()
            current_firmware_binary_hash = self._calculate_firmware_binary_hash(deployment_config)

            if current_esphome_version < compile_info.esphome_version:
                self.LOGGER.warning(
                    f"Detected downgrade of esphome version for '{deployment_config.name}': {current_esphome_version} < {compile_info.esphome_version}.")
                if not compile_options.allow_downgrade:
                    raise AssertionError("Downgrade not allowed. Use the '--allow-downgrade' flag to enable downgrading.")
                self.LOGGER.info(f"Allowing downgrade for '{deployment_config.name}' as per '--allow-downgrade' flag, proceeding with compile.")
                self.compile_configuration(deployment_config)
                return

            if (compile_info.config_hash == current_config_hash and
                compile_info.esphome_version == current_esphome_version and
                compile_info.binary_hash == current_firmware_binary_hash):
                self.LOGGER.warning(
                    f"Skipping compile for '{deployment_config.name}': configuration unchanged and already compiled with esphome version {current_esphome_version}.")
                return

        self.compile_configuration(deployment_config)

    def upload_deployment_config_if_needed(
        self,
        deployment_config: EspHomeDeploymentConfiguration,
        upload_options: UploadOptions = UploadOptions(),
    ):
        """
        Uploads a single deployment configuration, if needed.

        :param deployment_config: the deployment configuration to upload
        :param upload_options: options for upload
        """
        if not deployment_config.binary_file_path.exists():
            raise FileNotFoundError(f"Firmware binary not found for '{deployment_config.name}': {deployment_config.binary_file_path}, please compile first.")
        compile_info: Optional[CompileInfo] = self._get_remembered_compile_info(deployment_config)
        upload_info: Optional[UploadInfo] = self._get_remembered_upload_info(deployment_config)
        if upload_info is not None:
            current_binary_hash = self._calculate_firmware_binary_hash(deployment_config)

            if compile_info.binary_hash != current_binary_hash:
                self.LOGGER.warning(
                    f"Local firmware binary doesn't match last compiled firmware (expected: {compile_info.binary_hash}, actual: {current_binary_hash}). A recompile is recommended. If you still want to upload, use the '--ignore-compiled-binary-mismatch' flag.")
                if not upload_options.ignore_compiled_binary_mismatch:
                    raise AssertionError("Compiled binary mismatch. Use the '--ignore-compiled-binary-mismatch' flag to ignore this check.")

            if upload_info.binary_hash == current_binary_hash:
                self.LOGGER.warning(
                    f"Local firmware binary already uploaded for '{deployment_config.name}'.")
                if not upload_options.force:
                    self.LOGGER.info(f"Skipping upload for '{deployment_config.name}'.")
                    return
                else:
                    self.LOGGER.info(f"Forcing upload for '{deployment_config.name}' as per '--force' flag.")

        self.upload_configuration(deployment_config)
