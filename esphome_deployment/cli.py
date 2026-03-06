import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional, List

import click
from container_app_conf.formatter.toml import TomlFormatter
from rich.console import Console
from rich.theme import Theme

from esphome_deployment.config import AppConfig
from esphome_deployment.deployment import EspHomeDeploymentConfiguration
from esphome_deployment.deployment.deployment_coordinator import DeploymentCoordinator, CompileOptions, UploadOptions
from esphome_deployment.deployment.deployment_manager import DeploymentManager
from esphome_deployment.log_stuff import ProgressAwareLoggingHandler
from esphome_deployment.persistence import DeploymentPersistence
from esphome_deployment.util import load_yaml_file

parent_dir = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", ".."))
sys.path.append(parent_dir)

# TODO the log level from the config is not applied to all logger instances
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


def signal_handler(signal=None, frame=None):
    LOGGER.info("Exiting...")
    os._exit(0)


PARAM_DEPLOYMENT_NAME = "name"
PARAM_TAG = "tag"
PARAM_DOWNGRADE_NAME = "allow_downgrade"
PARAM_FORCE = "force"
PARAM_IGNORE_COMPILED_BINARY_MISMATCH = "ignore_compiled_binary_mismatch"

CMD_OPTION_NAMES = {
    PARAM_DEPLOYMENT_NAME: ["-n", "--name"],
    PARAM_TAG: ["-t", "--tag"],
    PARAM_DOWNGRADE_NAME: ["--allow-downgrade"],
    PARAM_FORCE: ["--force"],
    PARAM_IGNORE_COMPILED_BINARY_MISMATCH: ["--ignore-compiled-binary-mismatch"],
}

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
def cli():
    pass


def get_option_names(parameter: str) -> list:
    """
    Returns a list of all valid console parameter names for a given parameter
    :param parameter: the parameter to check
    :return: a list of all valid names to use this parameter
    """
    return CMD_OPTION_NAMES[parameter]


def _base_setup() -> Console:
    signal.signal(signal.SIGINT, signal_handler)

    config = AppConfig()

    log_level_str = str(config.LOG_LEVEL.value).strip().upper()
    log_level = getattr(logging, log_level_str, config.LOG_LEVEL.default)

    custom_theme = Theme({
        "logging.level.debug": "dim",
        "logging.level.info": "white",
    })
    console = Console(theme=custom_theme)

    rich_handler = ProgressAwareLoggingHandler(console=console)

    root_logger = logging.getLogger()
    root_logger.handlers = []  # remove all handlers from root logger
    root_logger.addHandler(rich_handler)
    root_logger.setLevel(log_level)

    LOGGER = logging.getLogger("esphome-deployment")
    LOGGER.setLevel(log_level)

    LOGGER.info("=== esphome-deployment ===")
    return console


@cli.command(name="compile")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str, multiple=True,
              help='The name of the deployment to compile (filename without extension)')
@click.option(*get_option_names(PARAM_TAG), required=False, default=None, type=str, multiple=True,
              help='The tag of the deployment(s) to compile')
@click.option(*get_option_names(PARAM_DOWNGRADE_NAME), is_flag=True, default=False,
              help='Allow downgrading ESPHome version when compiling')
def c_compile(
    name: Optional[str | list[str]],
    tag: Optional[str | list[str]],
    allow_downgrade: bool,
):
    """
    Compile the given deployment(s)
    """
    names = _detect_device_configuration_names(name, tag)

    console = _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence, console=console)

    compile_options = CompileOptions(allow_downgrade=allow_downgrade)

    deployment_coordinator.compile(name=names, path=path, compile_options=compile_options)


@cli.command(name="upload")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str, multiple=True,
              help='The name of the deployment to upload (filename without extension)')
@click.option(*get_option_names(PARAM_TAG), required=False, default=None, type=str, multiple=True,
              help='The tag of the deployment(s) to upload')
@click.option(*get_option_names(PARAM_IGNORE_COMPILED_BINARY_MISMATCH), is_flag=True, default=False,
              help='Ignore compiled binary mismatch when uploading')
@click.option(*get_option_names(PARAM_FORCE), is_flag=True, default=False,
              help='Force upload even if the binary matches the last uploaded one')
def c_upload(
    name: Optional[str | list[str]],
    tag: Optional[str | list[str]],
    ignore_compiled_binary_mismatch: bool = False,
    force: bool = False,
):
    """
    Upload the given deployment(s)
    """
    names = _detect_device_configuration_names(name, tag)

    console = _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence, console=console)

    upload_options = UploadOptions(
        force=force,
        ignore_compiled_binary_mismatch=ignore_compiled_binary_mismatch,
    )

    deployment_coordinator.upload(name=names, path=path, upload_options=upload_options)


@cli.command(name="deploy")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str, multiple=True,
              help='The name of the deployment to run (filename without extension)')
@click.option(*get_option_names(PARAM_TAG), required=False, default=None, type=str, multiple=True,
              help='The tag of the deployment(s) to run')
@click.option(*get_option_names(PARAM_DOWNGRADE_NAME), is_flag=True, default=False,
              help='Allow downgrading ESPHome version when compiling')
@click.option(*get_option_names(PARAM_IGNORE_COMPILED_BINARY_MISMATCH), is_flag=True, default=False,
              help='Ignore compiled binary mismatch when uploading')
@click.option(*get_option_names(PARAM_FORCE), is_flag=True, default=False,
              help='Force upload even if the binary matches the last uploaded one')
def c_deploy(
    name: Optional[str | list[str]],
    tag: Optional[str | list[str]],
    allow_downgrade: bool,
    ignore_compiled_binary_mismatch: bool = False,
    force: bool = False,
):
    """
    Deploy (compile + upload) the given deployment(s)

    :param name: The name(s) of the deployment(s) to deploy
    :param tag: The tag(s) of the deployment(s) to deploy
    :param allow_downgrade: Whether downgrading ESPHome version is allowed
    :param ignore_compiled_binary_mismatch: Whether to ignore compiled binary mismatch when uploading
    :param force: Whether to force upload even if the binary matches the last uploaded one
    """
    names = _detect_device_configuration_names(name, tag)

    console = _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence, console=console)

    compile_options = CompileOptions(allow_downgrade=allow_downgrade)
    upload_options = UploadOptions(
        force=force,
        ignore_compiled_binary_mismatch=ignore_compiled_binary_mismatch,
    )

    deployment_coordinator.deploy(name=names, path=path, compile_options=compile_options, upload_options=upload_options)


@cli.command(name="clean")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str,
              help='The name of the deployment to clean (filename without extension)')
@click.option(*get_option_names(PARAM_TAG), required=False, default=None, type=str, multiple=True,
              help='The tag of the deployment(s) to clean')
def c_clean(
    name: Optional[str],
    tag: Optional[str | list[str]],
):
    """
    Clean
    """
    names = _detect_device_configuration_names(name, tag)

    console = _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence, console=console)

    deployment_coordinator.clean(name=names, path=path)


@cli.command(name="config")
def c_config():
    """
    Print the current configuration
    """
    from esphome_deployment.config import AppConfig

    config = AppConfig()
    click.echo(config.print(TomlFormatter()))


def _detect_device_configuration_names(
    name: Optional[str | list[str]],
    tag: Optional[str | list[str]],
) -> List[str]:
    """
    Detect all device configurations in the current working directory that match the given arguments.

    :param name: Optional name(s) to filter the configurations by
    :param tag: Optional tag(s) to filter the configurations by

    :return: A list of device configuration names (filenames without extension)
    """
    path = Path(os.getcwd())
    config_names = []
    for file in path.glob("*.yaml"):
        config_names.append(file.stem)
    for file in path.glob("*.yml"):
        config_names.append(file.stem)

    config_names = sorted(list(set(config_names)), key=lambda s: s.casefold())
    for n in DeploymentManager.BLACKLISTED_FILES:
        n = n.removesuffix('.yaml').removesuffix('.yml')
        if n in config_names:
            config_names.remove(n)

    if not name and not tag:
        return config_names

    named_config_names = []
    if name:
        if isinstance(name, str):
            name = [name]
        # remove .yaml and .yml suffixes
        name = [n.removesuffix('.yaml').removesuffix('.yml') for n in name]
        for config_name in config_names:
            if config_name in name:
                named_config_names.append(config_name)

    tagged_config_names = []
    if tag:
        if isinstance(tag, str):
            tag = [tag]
        # we need to load the YAML files to check the tags
        for config_name in config_names:
            file_path = path / f"{config_name}.yaml"
            content = load_yaml_file(file_path)
            deployment_config = EspHomeDeploymentConfiguration(
                file_path=file_path,
                parsed_yaml_content=content
            )
            config_tags = deployment_config.esphome_deployment_options.tags
            if any(t in config_tags for t in tag):
                tagged_config_names.append(config_name)

    return named_config_names + tagged_config_names


if __name__ == '__main__':
    cli()
