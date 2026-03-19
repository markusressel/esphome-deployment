import logging
import re

from container_app_conf import ConfigBase
from container_app_conf.entry.int import IntConfigEntry
from container_app_conf.entry.string import StringConfigEntry
from container_app_conf.source.env_source import EnvSource
from container_app_conf.source.toml_source import TomlSource
from container_app_conf.source.yaml_source import YamlSource
from py_range_parse import parse_range

from esphome_deployment.const import *


class AppConfig(ConfigBase):

    def __new__(cls, *args, **kwargs):
        yaml_source = YamlSource(file_name=[CONFIG_NODE_ROOT, f".{CONFIG_NODE_ROOT}"])
        toml_source = TomlSource(file_name=[CONFIG_NODE_ROOT, f".{CONFIG_NODE_ROOT}"])
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

    MAX_WORKERS = IntConfigEntry(
        description="Max workers for parallel execution",
        key_path=[
            CONFIG_NODE_ROOT,
            CONFIG_NODE_DEPLOYMENT_COORDINATOR,
            "max_workers"
        ],
        range=parse_range("[1..100]"),
        default=4,
    )

    LOG_FILES_TO_KEEP = IntConfigEntry(
        description="Number of log files to keep for each deployment",
        key_path=[
            CONFIG_NODE_ROOT,
            CONFIG_NODE_DEPLOYMENT_COORDINATOR,
            "log_files_to_keep"
        ],
        default=3,
    )
