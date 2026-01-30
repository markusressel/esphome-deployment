import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

from ruamel.yaml.comments import TaggedScalar, CommentedMap

from esphome_deployment.util.semver import SemVerVersion


@dataclass
class CompileInfo:
    config_hash: str
    esphome_version: SemVerVersion
    binary_hash: str


@dataclass
class UploadInfo:
    binary_hash: str
    timestamp: datetime.datetime


@dataclass
class EspHomePackageReference:
    name: str
    file: Path
    vars: Dict[str, Any]


@dataclass
class EspHomeDeploymentOptions:
    # Whether to deploy this configuration (includes both build and upload)
    # Can be used to ignore certain configurations during batch deployments
    deploy: bool = True


@dataclass
class EspHomeDeploymentConfiguration:
    file_path: Path
    parsed_yaml_content: Dict

    @property
    def name(self) -> str:
        return self.file_path.stem

    @property
    def filename(self) -> str:
        return self.file_path.name

    @property
    def path(self) -> Path:
        return self.file_path.parent

    @property
    def esphome(self) -> Dict[str, Any]:
        return self.parsed_yaml_content.get("esphome", {})

    @property
    def build_path(self) -> Path:
        build_path = self.path / ".esphome"
        esphome_name = self.esphome.get("name", None)

        build_path_config: Optional[str] = self.parsed_yaml_content.get("esphome", {}).get("build_path", None)
        if build_path_config:
            build_path = build_path / build_path_config
        else:
            build_path = build_path / f"build/{esphome_name}"

        return build_path

    @property
    def binary_file_path(self) -> Path:
        # the path for the compiler can be different from the yaml configuration file name.
        # f.ex. the yaml configuration file "quinled-dig2go-pc-monitor-left.yaml" can have a compile path of
        # ".esphome/build/quinled_dig2go_bedroom_ceiling/.pioenvs/quinled_dig2go_bedroom_ceiling/firmware.bin"

        esphome_name = self.parsed_yaml_content["esphome"]["name"]
        binary_file_path = self.build_path / f".pioenvs/{esphome_name}/firmware.bin"
        return binary_file_path

    @property
    def deploy(self) -> bool:
        return self.esphome_deployment_options.deploy

    @property
    def esphome_deployment_options(self) -> EspHomeDeploymentOptions:
        options: Dict[str, Any] = self.parsed_yaml_content.get(".esphome_deployment", {})
        return EspHomeDeploymentOptions(
            deploy=options.get("deploy", True)
        )

    @property
    def packages(self) -> List[EspHomePackageReference]:
        # can be either a TaggedScalar or a CommentedMap
        #
        # TaggedScaler Example:
        # packages:
        #   my_package: !include packages/my_package.yaml
        #
        # CommentedMap Example:
        # packages:
        #   my_package:
        #     file: packages/my_package.yaml
        #     vars:
        #       var1: value1

        raw_packages = self.parsed_yaml_content.get("packages", {})
        result = []
        for package_name, package_value in raw_packages.items():
            if isinstance(package_value, TaggedScalar):
                result.append(
                    EspHomePackageReference(
                        name=package_name,
                        file=self.path / package_value.value,
                        vars={}
                    )
                )
            elif isinstance(package_value, CommentedMap):
                result.append(
                    EspHomePackageReference(
                        name=package_name,
                        file=self.path / package_value.get("file"),
                        vars=package_value.get("vars", {})
                    )
                )
        return result
