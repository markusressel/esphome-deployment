import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ruamel.yaml.comments import TaggedScalar, CommentedMap

from esphome_deployment.deployment import (
    EspHomeDeploymentConfiguration,
    EspHomePackageReference,
    CompileInfo,
    CompileOptions,
    UploadInfo,
    UploadOptions,
)
from esphome_deployment.deployment.deployment_manager import (
    DeploymentManager,
    DeploymentDisabledException,
    FirmwareBinaryNotFound,
)
from esphome_deployment.util.semver import SemVerVersion
from .. import TestBase


def _make_deployment_config(file_path: Path, parsed_yaml: dict = None) -> EspHomeDeploymentConfiguration:
    if parsed_yaml is None:
        parsed_yaml = {"esphome": {"name": "test_device"}}
    return EspHomeDeploymentConfiguration(file_path=file_path, parsed_yaml_content=parsed_yaml)


def _make_manager(persistence=None):
    if persistence is None:
        persistence = MagicMock()
    return DeploymentManager(persistence=persistence, logger=None)


class DeploymentManagerTest(TestBase):

    # ------------------------------------------------------------------ #
    # find_esphome_configuration_files                                     #
    # ------------------------------------------------------------------ #

    def test_find_esphome_configuration_files_excludes_blacklisted(self):
        manager = _make_manager()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "device.yaml").touch()
            for blacklisted in DeploymentManager.BLACKLISTED_FILES:
                (tmp_path / blacklisted).touch()
            result = manager.find_esphome_configuration_files(tmp_path)
            names = [f.name for f in result]
            self.assertIn("device.yaml", names)
            for blacklisted in DeploymentManager.BLACKLISTED_FILES:
                self.assertNotIn(blacklisted, names)

    def test_find_esphome_configuration_files_excludes_underscore_prefixed(self):
        manager = _make_manager()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "_private.yaml").touch()
            (tmp_path / "public.yaml").touch()
            result = manager.find_esphome_configuration_files(tmp_path)
            names = [f.name for f in result]
            self.assertIn("public.yaml", names)
            self.assertNotIn("_private.yaml", names)

    def test_find_esphome_configuration_files_returns_case_insensitive_sorted(self):
        manager = _make_manager()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for name in ["Zebra.yaml", "apple.yaml", "Mango.yaml"]:
                (tmp_path / name).touch()
            result = manager.find_esphome_configuration_files(tmp_path)
            names = [f.name for f in result]
            self.assertEqual(names, sorted(names, key=str.casefold))

    # ------------------------------------------------------------------ #
    # filter_deployments                                                   #
    # ------------------------------------------------------------------ #

    def test_filter_deployments_raises_when_deploy_disabled(self):
        manager = _make_manager()
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.deploy = False
        config.filename = "disabled_device.yaml"
        with self.assertRaises(DeploymentDisabledException):
            manager.filter_deployments([config])

    def test_filter_deployments_passes_when_deploy_enabled(self):
        manager = _make_manager()
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.deploy = True
        result = manager.filter_deployments([config])
        self.assertEqual(result, [config])

    def test_filter_deployments_returns_empty_for_empty_input(self):
        manager = _make_manager()
        result = manager.filter_deployments([])
        self.assertEqual(result, [])

    # ------------------------------------------------------------------ #
    # compile_deployment_config_if_needed                                  #
    # ------------------------------------------------------------------ #

    def test_compile_skips_when_config_and_version_and_binary_unchanged(self):
        persistence = MagicMock()
        version = SemVerVersion("2025.12.0")
        stored = CompileInfo(config_hash="abc", esphome_version=version, binary_hash="def")
        persistence.load_compile_info.return_value = stored

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)

        with (
            patch.object(DeploymentManager, "_calculate_config_hash", return_value="abc"),
            patch.object(DeploymentManager, "_get_current_esphome_version", return_value=version),
            patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="def"),
            patch.object(manager, "compile_configuration") as mock_compile,
        ):
            manager.compile_deployment_config_if_needed(config, CompileOptions(), log_to_console=False)
            mock_compile.assert_not_called()

    def test_compile_runs_when_no_previous_compile_info(self):
        persistence = MagicMock()
        persistence.load_compile_info.return_value = None

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)

        with patch.object(manager, "compile_configuration") as mock_compile:
            manager.compile_deployment_config_if_needed(config, CompileOptions(), log_to_console=False)
            mock_compile.assert_called_once_with(config, False)

    def test_compile_runs_when_config_hash_changed(self):
        persistence = MagicMock()
        version = SemVerVersion("2025.12.0")
        stored = CompileInfo(config_hash="old_hash", esphome_version=version, binary_hash="bin_hash")
        persistence.load_compile_info.return_value = stored

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)

        with (
            patch.object(DeploymentManager, "_calculate_config_hash", return_value="new_hash"),
            patch.object(DeploymentManager, "_get_current_esphome_version", return_value=version),
            patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="bin_hash"),
            patch.object(manager, "compile_configuration") as mock_compile,
        ):
            manager.compile_deployment_config_if_needed(config, CompileOptions(), log_to_console=False)
            mock_compile.assert_called_once()

    def test_compile_raises_on_downgrade_when_not_allowed(self):
        persistence = MagicMock()
        stored_version = SemVerVersion("2025.12.0")
        current_version = SemVerVersion("2025.11.0")
        stored = CompileInfo(config_hash="abc", esphome_version=stored_version, binary_hash="def")
        persistence.load_compile_info.return_value = stored

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)

        with (
            patch.object(DeploymentManager, "_calculate_config_hash", return_value="abc"),
            patch.object(DeploymentManager, "_get_current_esphome_version", return_value=current_version),
            patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="def"),
        ):
            with self.assertRaises(AssertionError):
                manager.compile_deployment_config_if_needed(
                    config, CompileOptions(allow_downgrade=False), log_to_console=False
                )

    def test_compile_allows_downgrade_when_flag_set(self):
        persistence = MagicMock()
        stored_version = SemVerVersion("2025.12.0")
        current_version = SemVerVersion("2025.11.0")
        stored = CompileInfo(config_hash="abc", esphome_version=stored_version, binary_hash="def")
        persistence.load_compile_info.return_value = stored

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)

        with (
            patch.object(DeploymentManager, "_calculate_config_hash", return_value="abc"),
            patch.object(DeploymentManager, "_get_current_esphome_version", return_value=current_version),
            patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="def"),
            patch.object(manager, "compile_configuration") as mock_compile,
        ):
            manager.compile_deployment_config_if_needed(
                config, CompileOptions(allow_downgrade=True), log_to_console=False
            )
            mock_compile.assert_called_once()

    # ------------------------------------------------------------------ #
    # upload_deployment_config_if_needed                                   #
    # ------------------------------------------------------------------ #

    def test_upload_raises_when_binary_not_found(self):
        manager = _make_manager()
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.binary_file_path = MagicMock()
        config.binary_file_path.exists.return_value = False

        with self.assertRaises(FirmwareBinaryNotFound):
            manager.upload_deployment_config_if_needed(config, log_to_console=False)

    def test_upload_skips_when_binary_hash_unchanged(self):
        persistence = MagicMock()
        compile_info = CompileInfo(config_hash="c", esphome_version=SemVerVersion("2025.12.0"), binary_hash="bin123")
        upload_info = UploadInfo(binary_hash="bin123", timestamp=MagicMock())
        persistence.load_compile_info.return_value = compile_info
        persistence.load_upload_info.return_value = upload_info

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.binary_file_path = MagicMock()
        config.binary_file_path.exists.return_value = True

        with (
            patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="bin123"),
            patch.object(manager, "upload_configuration") as mock_upload,
        ):
            manager.upload_deployment_config_if_needed(
                config, log_to_console=False, upload_options=UploadOptions(force=False)
            )
            mock_upload.assert_not_called()

    def test_upload_forces_when_flag_set(self):
        persistence = MagicMock()
        compile_info = CompileInfo(config_hash="c", esphome_version=SemVerVersion("2025.12.0"), binary_hash="bin123")
        upload_info = UploadInfo(binary_hash="bin123", timestamp=MagicMock())
        persistence.load_compile_info.return_value = compile_info
        persistence.load_upload_info.return_value = upload_info

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.binary_file_path = MagicMock()
        config.binary_file_path.exists.return_value = True

        with (
            patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="bin123"),
            patch.object(manager, "upload_configuration") as mock_upload,
        ):
            manager.upload_deployment_config_if_needed(
                config, log_to_console=False, upload_options=UploadOptions(force=True)
            )
            mock_upload.assert_called_once()

    def test_upload_runs_when_no_previous_upload_info(self):
        persistence = MagicMock()
        persistence.load_compile_info.return_value = None
        persistence.load_upload_info.return_value = None

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.binary_file_path = MagicMock()
        config.binary_file_path.exists.return_value = True

        with patch.object(manager, "upload_configuration") as mock_upload:
            manager.upload_deployment_config_if_needed(config, log_to_console=False)
            mock_upload.assert_called_once()

    def test_upload_raises_on_binary_mismatch_when_not_ignored(self):
        persistence = MagicMock()
        compile_info = CompileInfo(config_hash="c", esphome_version=SemVerVersion("2025.12.0"), binary_hash="expected_bin")
        upload_info = UploadInfo(binary_hash="old_bin", timestamp=MagicMock())
        persistence.load_compile_info.return_value = compile_info
        persistence.load_upload_info.return_value = upload_info

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.binary_file_path = MagicMock()
        config.binary_file_path.exists.return_value = True

        with patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="different_bin"):
            with self.assertRaises(AssertionError):
                manager.upload_deployment_config_if_needed(
                    config, log_to_console=False,
                    upload_options=UploadOptions(ignore_compiled_binary_mismatch=False)
                )

    def test_upload_proceeds_on_binary_mismatch_when_ignored(self):
        persistence = MagicMock()
        compile_info = CompileInfo(config_hash="c", esphome_version=SemVerVersion("2025.12.0"), binary_hash="expected_bin")
        upload_info = UploadInfo(binary_hash="old_bin", timestamp=MagicMock())
        persistence.load_compile_info.return_value = compile_info
        persistence.load_upload_info.return_value = upload_info

        manager = _make_manager(persistence)
        config = MagicMock(spec=EspHomeDeploymentConfiguration)
        config.binary_file_path = MagicMock()
        config.binary_file_path.exists.return_value = True

        with (
            patch.object(DeploymentManager, "_calculate_firmware_binary_hash", return_value="different_bin"),
            patch.object(manager, "upload_configuration") as mock_upload,
        ):
            manager.upload_deployment_config_if_needed(
                config, log_to_console=False,
                upload_options=UploadOptions(ignore_compiled_binary_mismatch=True)
            )
            mock_upload.assert_called_once()


class EspHomeDeploymentConfigurationPackagesTest(TestBase):

    def _make_tagged_scalar(self, value: str) -> TaggedScalar:
        return TaggedScalar(value=value, tag="!include")

    def test_packages_returns_empty_when_no_packages_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = _make_deployment_config(Path(tmp) / "device.yaml")
            self.assertEqual(config.packages, [])

    def test_packages_returns_empty_for_non_dict_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = _make_deployment_config(Path(tmp) / "device.yaml", parsed_yaml={"packages": "not_a_dict"})
            self.assertEqual(config.packages, [])

    def test_packages_parses_tagged_scalar(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ts = self._make_tagged_scalar("packages/base.yaml")
            parsed = {"esphome": {"name": "d"}, "packages": {"base": ts}}
            config = _make_deployment_config(tmp_path / "device.yaml", parsed_yaml=parsed)
            packages = config.packages
            self.assertEqual(len(packages), 1)
            self.assertIsInstance(packages[0], EspHomePackageReference)
            self.assertEqual(packages[0].name, "base")
            self.assertEqual(packages[0].file, tmp_path / "packages/base.yaml")
            self.assertEqual(packages[0].vars, {})

    def test_packages_skips_tagged_scalar_with_none_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            ts = TaggedScalar(value=None, tag="!include")
            parsed = {"esphome": {"name": "d"}, "packages": {"base": ts}}
            config = _make_deployment_config(Path(tmp) / "device.yaml", parsed_yaml=parsed)
            self.assertEqual(config.packages, [])

    def test_packages_parses_commented_map_with_file_and_vars(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cm = CommentedMap()
            cm["file"] = "packages/common.yaml"
            cm["vars"] = {"board": "esp32", "freq": 240}
            parsed = {"esphome": {"name": "d"}, "packages": {"common": cm}}
            config = _make_deployment_config(tmp_path / "device.yaml", parsed_yaml=parsed)
            packages = config.packages
            self.assertEqual(len(packages), 1)
            pkg = packages[0]
            self.assertIsInstance(pkg, EspHomePackageReference)
            self.assertEqual(pkg.name, "common")
            self.assertEqual(pkg.file, tmp_path / "packages/common.yaml")
            self.assertEqual(pkg.vars, {"board": "esp32", "freq": 240})

    def test_packages_skips_commented_map_without_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cm = CommentedMap()
            cm["vars"] = {"key": "value"}
            parsed = {"esphome": {"name": "d"}, "packages": {"broken": cm}}
            config = _make_deployment_config(Path(tmp) / "device.yaml", parsed_yaml=parsed)
            self.assertEqual(config.packages, [])

    def test_packages_defaults_vars_to_empty_dict_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cm = CommentedMap()
            cm["file"] = "packages/minimal.yaml"
            parsed = {"esphome": {"name": "d"}, "packages": {"minimal": cm}}
            config = _make_deployment_config(tmp_path / "device.yaml", parsed_yaml=parsed)
            packages = config.packages
            self.assertEqual(len(packages), 1)
            self.assertEqual(packages[0].vars, {})

    def test_packages_multiple_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ts = self._make_tagged_scalar("packages/a.yaml")
            cm = CommentedMap()
            cm["file"] = "packages/b.yaml"
            parsed = {"esphome": {"name": "d"}, "packages": {"a": ts, "b": cm}}
            config = _make_deployment_config(tmp_path / "device.yaml", parsed_yaml=parsed)
            packages = config.packages
            self.assertEqual(len(packages), 2)
            names = [p.name for p in packages]
            self.assertIn("a", names)
            self.assertIn("b", names)

