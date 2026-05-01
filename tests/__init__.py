from unittest import IsolatedAsyncioTestCase


class TestBase(IsolatedAsyncioTestCase):
    from esphome_deployment.config import AppConfig
    from container_app_conf.source.yaml_source import YamlSource

    # load config from test folder
    config = AppConfig(
        singleton=True,
        data_sources=[
            YamlSource(".esphome_deployment", "./tests/")
        ]
    )
