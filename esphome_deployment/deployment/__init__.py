import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from ruamel.yaml.comments import TaggedScalar, CommentedMap

from esphome_deployment.util import load_json_file, load_yaml_file
from esphome_deployment.util.semver import SemVerVersion


@dataclass
class CompileOptions:
    # whether to allow downgrading ESPHome version when compiling
    allow_downgrade: bool = False


@dataclass
class UploadOptions:
    # whether to force the upload even if the state tells us that we have already uploaded this firmware binary
    force: bool = False

    # whether to ignore mismatches between the locally present compiled binary and the last known compiled one
    ignore_compiled_binary_mismatch: bool = False


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
    tags: List[str] = field(default_factory=list)


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
    def _esphome_base_path(self) -> Path:
        return self.path / ".esphome"

    @property
    def build_path(self) -> Path:
        build_path = self._esphome_base_path
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
    def esphom_storage_data(self) -> Dict[str, Any]:
        data_file_path = self._esphome_base_path / "storage" / f"{self.filename}.json"
        try:
            return load_json_file(data_file_path)
        except Exception as ex:
            return {}

    @property
    def deploy(self) -> bool:
        return self.esphome_deployment_options.deploy

    @property
    def tags(self) -> List[str]:
        return self.esphome_deployment_options.tags

    @property
    def ip_address(self) -> Optional[str]:
        return self.esphom_storage_data.get("address", None)

    @property
    def esphome_deployment_options(self) -> EspHomeDeploymentOptions:
        visited_files: Set[Path] = set()
        package_options = self._collect_package_deployment_options(visited_files=visited_files)

        top_level_options = self._parse_deployment_options(self.parsed_yaml_content)

        # Top-level options override package-derived defaults when explicitly set.
        return self._merge_deployment_options(package_options, top_level_options)

    @staticmethod
    def _parse_deployment_options(parsed_yaml: Dict[str, Any]) -> Tuple[Optional[bool], List[str]]:
        raw_options = parsed_yaml.get(".esphome_deployment", {})
        deploy: Optional[bool] = None
        if "deploy" in raw_options:
            deploy = bool(raw_options.get("deploy"))

        raw_tags = raw_options.get("tags", [])
        if not isinstance(raw_tags, list):
            raw_tags = [raw_tags]
        tags = [str(tag) for tag in raw_tags]

        return deploy, tags

    @staticmethod
    def _merge_deployment_options(
        base: Tuple[Optional[bool], List[str]],
        override: Tuple[Optional[bool], List[str]],
    ) -> EspHomeDeploymentOptions:
        deploy, merged_tags = EspHomeDeploymentConfiguration._merge_deployment_option_values(base, override)
        return EspHomeDeploymentOptions(
            deploy=deploy,
            tags=merged_tags,
        )

    @staticmethod
    def _merge_deployment_option_values(
        base: Tuple[Optional[bool], List[str]],
        override: Tuple[Optional[bool], List[str]],
    ) -> Tuple[bool, List[str]]:
        base_deploy, base_tags = base
        override_deploy, override_tags = override

        deploy = base_deploy if override_deploy is None else override_deploy
        if deploy is None:
            deploy = True

        # Keep tag order stable while preventing duplicates.
        merged_tags = list(dict.fromkeys([*base_tags, *override_tags]))
        return deploy, merged_tags

    def _collect_package_deployment_options(
        self,
        visited_files: Set[Path],
    ) -> Tuple[Optional[bool], List[str]]:
        resolved_path = self.file_path.resolve()
        if resolved_path in visited_files:
            return None, []
        visited_files.add(resolved_path)

        merged: Tuple[Optional[bool], List[str]] = (None, [])
        for package in self.packages:
            if not package.file:
                continue

            package_yaml = load_yaml_file(package.file)
            if not isinstance(package_yaml, dict):
                continue

            package_config = EspHomeDeploymentConfiguration(
                file_path=package.file,
                parsed_yaml_content=package_yaml,
            )

            nested_options = package_config._collect_package_deployment_options(
                visited_files=visited_files,
            )

            merged = self._merge_deployment_option_values(merged, nested_options)
            package_options = package_config._parse_deployment_options(package_yaml)
            merged = self._merge_deployment_option_values(merged, package_options)

        return merged


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
        if not isinstance(raw_packages, dict):
            return []

        result = []
        for package_name, package_value in raw_packages.items():
            if isinstance(package_value, TaggedScalar):
                if package_value.value is None:
                    continue
                result.append(
                    EspHomePackageReference(
                        name=package_name,
                        file=self.path / package_value.value,
                        vars={}
                    )
                )
            elif isinstance(package_value, CommentedMap):
                package_file = package_value.get("file")
                if package_file is None:
                    continue

                package_vars = package_value.get("vars", {})
                if not isinstance(package_vars, dict):
                    package_vars = {}

                result.append(
                    EspHomePackageReference(
                        name=package_name,
                        file=self.path / package_file,
                        vars=package_vars
                    )
                )
        return result
