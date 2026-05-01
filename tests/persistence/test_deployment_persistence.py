import datetime
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from esphome_deployment.deployment import CompileInfo, UploadInfo
from esphome_deployment.persistence import DeploymentPersistence
from esphome_deployment.util.semver import SemVerVersion
from tests import TestBase


def _make_persistence(tmp_path: Path) -> DeploymentPersistence:
    return DeploymentPersistence(base_path=tmp_path)


def _make_deployment_config(name: str = "test_device") -> MagicMock:
    config = MagicMock()
    config.name = name
    return config


def _make_compile_info(
    config_hash: str = "abc123",
    version: str = "2025.12.0",
    binary_hash: str = "def456",
) -> CompileInfo:
    return CompileInfo(
        config_hash=config_hash,
        esphome_version=SemVerVersion(version),
        binary_hash=binary_hash,
    )


def _make_upload_info(
    binary_hash: str = "def456",
    timestamp: datetime.datetime = None,
) -> UploadInfo:
    if timestamp is None:
        timestamp = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    return UploadInfo(binary_hash=binary_hash, timestamp=timestamp)


class DeploymentPersistenceInitTest(TestBase):

    def test_persistence_dir_created_on_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            persistence = _make_persistence(tmp_path)
            self.assertTrue(persistence.persistence_dir.exists())
            self.assertTrue(persistence.persistence_dir.is_dir())

    def test_persistence_dir_name_is_deployment_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            self.assertEqual(persistence.persistence_dir.name, ".deployment-state")

    def test_get_file_for_deployment_returns_correct_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("my_device")
            result = persistence._get_file_for_deployment(config)
            self.assertEqual(result, persistence.persistence_dir / "my_device.json")


class DeploymentPersistenceCompileInfoTest(TestBase):

    def test_save_and_load_compile_info_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_a")
            info = _make_compile_info(config_hash="hash1", version="2025.12.1", binary_hash="binhash1")

            persistence.save_compile_info(info, config)
            loaded = persistence.load_compile_info(config)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.config_hash, "hash1")
            self.assertEqual(loaded.esphome_version, SemVerVersion("2025.12.1"))
            self.assertEqual(loaded.binary_hash, "binhash1")

    def test_load_compile_info_returns_none_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("nonexistent")
            result = persistence.load_compile_info(config)
            self.assertIsNone(result)

    def test_load_compile_info_returns_none_when_last_compile_key_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_b")
            target = persistence._get_file_for_deployment(config)
            target.write_text(json.dumps({"some_other_key": {}}), encoding="utf-8")

            result = persistence.load_compile_info(config)
            self.assertIsNone(result)

    def test_load_compile_info_returns_none_when_config_hash_wrong_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_c")
            target = persistence._get_file_for_deployment(config)
            target.write_text(json.dumps({
                "last_successful_compile": {
                    "config_hash": 12345,  # int instead of str
                    "esphome_version": "2025.12.0",
                    "binary_hash": "binhash",
                }
            }), encoding="utf-8")

            result = persistence.load_compile_info(config)
            self.assertIsNone(result)

    def test_load_compile_info_returns_none_when_binary_hash_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_d")
            target = persistence._get_file_for_deployment(config)
            target.write_text(json.dumps({
                "last_successful_compile": {
                    "config_hash": "abc",
                    "esphome_version": "2025.12.0",
                    # binary_hash intentionally missing
                }
            }), encoding="utf-8")

            result = persistence.load_compile_info(config)
            self.assertIsNone(result)

    def test_load_compile_info_returns_none_when_file_is_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_e")
            target = persistence._get_file_for_deployment(config)
            target.write_text("not valid json {{{", encoding="utf-8")

            result = persistence.load_compile_info(config)
            self.assertIsNone(result)

    def test_save_compile_info_preserves_existing_upload_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_f")

            persistence.save_upload_info(_make_upload_info(), config)
            persistence.save_compile_info(_make_compile_info(), config)

            target = persistence._get_file_for_deployment(config)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("last_successful_compile", data)
            self.assertIn("last_successful_upload", data)

    def test_save_compile_info_overwrites_previous_compile_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_g")

            persistence.save_compile_info(_make_compile_info(config_hash="old"), config)
            persistence.save_compile_info(_make_compile_info(config_hash="new"), config)

            loaded = persistence.load_compile_info(config)
            self.assertEqual(loaded.config_hash, "new")


class DeploymentPersistenceUploadInfoTest(TestBase):

    def test_save_and_load_upload_info_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_a")
            ts = datetime.datetime(2026, 3, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)
            info = _make_upload_info(binary_hash="uploadhash", timestamp=ts)

            persistence.save_upload_info(info, config)
            loaded = persistence.load_upload_info(config)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.binary_hash, "uploadhash")
            self.assertEqual(loaded.timestamp, ts)

    def test_load_upload_info_returns_none_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("nonexistent")
            result = persistence.load_upload_info(config)
            self.assertIsNone(result)

    def test_load_upload_info_returns_none_when_key_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_b")
            target = persistence._get_file_for_deployment(config)
            target.write_text(json.dumps({"other_key": {}}), encoding="utf-8")

            result = persistence.load_upload_info(config)
            self.assertIsNone(result)

    def test_load_upload_info_returns_none_when_binary_hash_wrong_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_c")
            target = persistence._get_file_for_deployment(config)
            target.write_text(json.dumps({
                "last_successful_upload": {
                    "binary_hash": 99999,  # int instead of str
                    "timestamp": "2026-01-01T12:00:00+00:00",
                }
            }), encoding="utf-8")

            result = persistence.load_upload_info(config)
            self.assertIsNone(result)

    def test_load_upload_info_returns_none_when_timestamp_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_d")
            target = persistence._get_file_for_deployment(config)
            target.write_text(json.dumps({
                "last_successful_upload": {
                    "binary_hash": "binhash",
                    # timestamp intentionally missing
                }
            }), encoding="utf-8")

            result = persistence.load_upload_info(config)
            self.assertIsNone(result)

    def test_load_upload_info_returns_none_when_file_is_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_e")
            target = persistence._get_file_for_deployment(config)
            target.write_text("}}not json{{", encoding="utf-8")

            result = persistence.load_upload_info(config)
            self.assertIsNone(result)

    def test_save_upload_info_preserves_existing_compile_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_f")

            persistence.save_compile_info(_make_compile_info(), config)
            persistence.save_upload_info(_make_upload_info(), config)

            target = persistence._get_file_for_deployment(config)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("last_successful_compile", data)
            self.assertIn("last_successful_upload", data)

    def test_save_upload_info_overwrites_previous_upload_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            config = _make_deployment_config("device_g")

            persistence.save_upload_info(_make_upload_info(binary_hash="old_hash"), config)
            persistence.save_upload_info(_make_upload_info(binary_hash="new_hash"), config)

            loaded = persistence.load_upload_info(config)
            self.assertEqual(loaded.binary_hash, "new_hash")


class DeploymentPersistenceUpdatePayloadTest(TestBase):

    def test_update_payload_creates_file_when_not_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            target = persistence.persistence_dir / "new_file.json"
            self.assertFalse(target.exists())

            persistence._update_payload(target, {"key": "value"})

            self.assertTrue(target.exists())
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["key"], "value")

    def test_update_payload_merges_with_existing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            target = persistence.persistence_dir / "existing.json"
            target.write_text(json.dumps({"existing_key": "existing_value"}), encoding="utf-8")

            persistence._update_payload(target, {"new_key": "new_value"})

            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["existing_key"], "existing_value")
            self.assertEqual(data["new_key"], "new_value")

    def test_update_payload_overwrites_existing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            target = persistence.persistence_dir / "overwrite.json"
            target.write_text(json.dumps({"key": "old_value"}), encoding="utf-8")

            persistence._update_payload(target, {"key": "new_value"})

            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["key"], "new_value")

    def test_update_payload_cleans_up_tmp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            persistence = _make_persistence(Path(tmp))
            target = persistence.persistence_dir / "cleanup.json"

            persistence._update_payload(target, {"x": 1})

            tmp_file = target.with_suffix(".json.tmp")
            self.assertFalse(tmp_file.exists())

