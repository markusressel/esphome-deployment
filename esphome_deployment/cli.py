import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional, List

import click
from container_app_conf.formatter.toml import TomlFormatter

from esphome_deployment.config import AppConfig
from esphome_deployment.deployment.deployment_coordinator import DeploymentCoordinator
from esphome_deployment.persistence import DeploymentPersistence

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
PARAM_DOWNGRADE_NAME = "allow_downgrade"

CMD_OPTION_NAMES = {
    PARAM_DEPLOYMENT_NAME: ["-n", "--name"],
    PARAM_DOWNGRADE_NAME: ["--allow-downgrade"],
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


def _base_setup():
    signal.signal(signal.SIGINT, signal_handler)

    config = AppConfig()

    log_level = logging._nameToLevel.get(
        str(config.LOG_LEVEL.value).upper(),
        config.LOG_LEVEL.default
    )
    LOGGER = logging.getLogger("esphome-deployment")
    LOGGER.setLevel(log_level)

    LOGGER.info("=== esphome-deployment ===")


@cli.command(name="compile")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str, multiple=True,
              help='The name of the deployment to compile (filename without extension)')
@click.option(*get_option_names(PARAM_DOWNGRADE_NAME), is_flag=True, default=False,
              help='Allow downgrading ESPHome version when compiling')
def c_compile(
    name: Optional[str | list[str]],
    allow_downgrade: bool,
):
    """
    Compile the given deployment(s)
    """
    names = name
    if isinstance(names, str):
        names = [names]

    if not names:
        names = _detect_device_configuration_names()

    _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence)

    for name in names:
        if name:
            name = name.removesuffix('.yaml').removesuffix('.yml')
            deployment_coordinator.compile(name=name, path=path, allow_downgrade=allow_downgrade)
        else:
            deployment_coordinator.compile_all(path=path, allow_downgrade=allow_downgrade)


@cli.command(name="upload")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str, multiple=True,
              help='The name of the deployment to upload (filename without extension)')
def c_upload(
    name: Optional[str | list[str]],
    ignore_compile_version_mismatch: bool = False,
    force: bool = False,
):
    """
    Upload the given deployment(s)
    """
    names = name
    if isinstance(names, str):
        names = [names]

    if not names:
        names = _detect_device_configuration_names()

    _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence)
    for name in names:
        if name:
            name = name.removesuffix('.yaml').removesuffix('.yml')
            deployment_coordinator.upload(name, path)
        else:
            deployment_coordinator.upload_all(path)


@cli.command(name="deploy")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str, multiple=True,
              help='The name of the deployment to run (filename without extension)')
@click.option(*get_option_names(PARAM_DOWNGRADE_NAME), is_flag=True, default=False,
              help='Allow downgrading ESPHome version when compiling')
def c_deploy(
    name: Optional[str | list[str]],
    allow_downgrade: bool,
):
    """
    Deploy (compile + upload) the given deployment(s)

    :param name: The name(s) of the deployment(s) to deploy
    :param allow_downgrade: Whether downgrading ESPHome version is allowed
    """
    names = name
    if isinstance(names, str):
        names = [names]

    if not names:
        names = _detect_device_configuration_names()

    _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence)
    for name in names:
        if name:
            name = name.removesuffix('.yaml').removesuffix('.yml')
            deployment_coordinator.deploy(name, path, allow_downgrade=allow_downgrade)
        else:
            deployment_coordinator.deploy_all(path, allow_downgrade=allow_downgrade)


@cli.command(name="clean")
@click.option(*get_option_names(PARAM_DEPLOYMENT_NAME), required=False, default=None, type=str,
              help='The name of the deployment to clean (filename without extension)')
def c_clean(name: Optional[str]):
    """
    Clean
    """
    _base_setup()
    path = Path(os.getcwd())

    persistence = DeploymentPersistence(base_path=path)
    deployment_coordinator = DeploymentCoordinator(persistence=persistence)
    if name:
        name = name.removesuffix('.yaml').removesuffix('.yml')
        deployment_coordinator.clean(name, path)
    else:
        deployment_coordinator.clean_all(path)


@cli.command(name="config")
def c_config():
    """
    Print the current configuration
    """
    from esphome_deployment.config import AppConfig

    config = AppConfig()
    click.echo(config.print(TomlFormatter()))


def _detect_device_configuration_names() -> List[str]:
    """
    Detect all device configuration names in the current working directory
    :return: A list of device configuration names (filenames without extension)
    """
    path = Path(os.getcwd())
    config_names = []
    for file in path.glob("*.yaml"):
        config_names.append(file.stem)

    config_names = sorted(list(set(config_names)), key=lambda s: s.casefold())
    config_names.remove('esphome_deployment')
    config_names.remove('secrets')

    return config_names


if __name__ == '__main__':
    cli()
