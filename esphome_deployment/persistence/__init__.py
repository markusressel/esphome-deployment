import datetime
import json
from pathlib import Path
from typing import Optional

from esphome_deployment.deployment import EspHomeDeploymentConfiguration, CompileInfo, UploadInfo
from esphome_deployment.util.semver import SemVerVersion


class DeploymentPersistence:
    """
    Saves and retrieves data by writing into a file.
    1 file per deployment, stored in a 'deployment-state' folder.
    1 file per deployment, named <deployment_name>.json

    Each file contains:
    {
        "last_successful_compile": {
            "config_hash": "<hash>",
            "esphome_version": "<version>"
        }
    }
    """

    def __init__(self, base_path: Optional[Path] = None):
        # Base path where the persistence folder will be created. If not provided,
        # use the package directory for esphome_deployment.
        if base_path is None:
            base_path = Path(__file__).parent
        self.base_path = Path(base_path)
        self.persistence_dir = self.base_path / '.deployment-state'
        self.persistence_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_for_deployment(self, deployment: EspHomeDeploymentConfiguration) -> Path:
        # filename is <deployment_name>.json
        return self.persistence_dir / f"{deployment.name}.json"

    def save_compile_info(self, compile_info: CompileInfo, deployment: EspHomeDeploymentConfiguration):
        """Save the remembered compile info for a deployment."""
        target_file = self._get_file_for_deployment(deployment)
        payload = {
            "last_successful_compile": {
                "config_hash": compile_info.config_hash,
                "esphome_version": compile_info.esphome_version,
                "binary_hash": compile_info.binary_hash,
            }
        }
        self._update_payload(target_file, payload)

    def load_compile_info(self, deployment: EspHomeDeploymentConfiguration) -> Optional[CompileInfo]:
        """Load the remembered compile info for a deployment."""
        target_file = self._get_file_for_deployment(deployment)
        if not target_file.exists():
            return None

        data = self._load_deployment_file(target_file)
        if data is None:
            return None

        last = data.get('last_successful_compile', {})
        if not last:
            return None

        config_hash = last.get('config_hash', None)
        esphome_version = last.get('esphome_version', None)
        binary_hash = last.get('binary_hash', None)
        if not isinstance(config_hash, str) or not isinstance(esphome_version, str) or not isinstance(binary_hash, str):
            return None

        return CompileInfo(
            config_hash=config_hash,
            esphome_version=SemVerVersion(esphome_version),
            binary_hash=binary_hash,
        )

    def save_upload_info(self, upload_info: UploadInfo, deployment: EspHomeDeploymentConfiguration):
        """Save the remembered upload info for a deployment."""
        target_file = self._get_file_for_deployment(deployment)
        payload = {
            "last_successful_upload": {
                "binary_hash": upload_info.binary_hash,
                "timestamp": upload_info.timestamp,
            }
        }
        self._update_payload(target_file, payload)

    def load_upload_info(self, deployment: EspHomeDeploymentConfiguration) -> Optional[UploadInfo]:
        """Load the remembered upload info for a deployment."""
        target_file = self._get_file_for_deployment(deployment)
        if not target_file.exists():
            return None

        data = self._load_deployment_file(target_file)
        if data is None:
            return None

        last = data.get('last_successful_upload', {})
        if not last:
            return None

        binary_hash = last.get('binary_hash', None)
        timestamp = last.get('timestamp', None)
        if not isinstance(binary_hash, str) or not isinstance(timestamp, str):
            return None

        converted_timestamp = datetime.datetime.fromisoformat(timestamp)
        return UploadInfo(
            binary_hash=binary_hash,
            timestamp=converted_timestamp
        )

    def _update_payload(self, target_file, payload):
        """
        Update the payload in the target file by merging its current content with the new payload.
        :param target_file:
        :param payload:
        :return:
        """

        # load the current file content
        current_data = {}
        if target_file.exists():
            current_data = self._load_deployment_file(target_file) or {}
        # merge with new payload
        current_data.update(payload)
        payload = current_data

        tmp_file = target_file.with_suffix('.json.tmp')
        try:
            with tmp_file.open('w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True, default=str)
            tmp_file.replace(target_file)
        finally:
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    def _load_deployment_file(self, target_file: Path) -> Optional[dict]:
        try:
            with target_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return None
                return data
        except Exception:
            return None
