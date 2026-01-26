import logging
import re

from container_app_conf import ConfigBase
from container_app_conf.entry.string import StringConfigEntry
from container_app_conf.source.env_source import EnvSource
from container_app_conf.source.toml_source import TomlSource
from container_app_conf.source.yaml_source import YamlSource

from esphome_deployment.const import CONFIG_NODE_ROOT


class AppConfig(ConfigBase):

    def __new__(cls, *args, **kwargs):
        yaml_source = YamlSource(file_name=CONFIG_NODE_ROOT)
        toml_source = TomlSource(file_name=CONFIG_NODE_ROOT)
        data_sources = [
            EnvSource(),
            yaml_source,
            toml_source,
        ]
        return super(AppConfig, cls).__new__(cls, data_sources=data_sources)

    LOG_LEVEL = StringConfigEntry(
        description="Log level",
        key_path=[
            CONFIG_NODE_ROOT,
            "log_level"
        ],
        regex=re.compile(f" {'|'.join(logging._nameToLevel.keys())}", flags=re.IGNORECASE),
        default="INFO",
    )
