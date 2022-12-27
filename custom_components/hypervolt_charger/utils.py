import logging
import json
import os

_LOGGER = logging.getLogger(__name__)


def get_version_from_manifest() -> str:
    """Attempt to read the manifest.json file and extract the version number. Returns 0.0.0 on failure"""
    try:
        manifest_filename = os.path.join(os.path.dirname(__file__), "manifest.json")
        _LOGGER.debug(
            f"get_version_from_manifest loading manifest: {manifest_filename}"
        )
        with open(manifest_filename, encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
            version = manifest["version"]
            _LOGGER.debug(f"get_version_from_manifest returning version: {version}")

            return version

    except Exception as exc:
        _LOGGER.error(f"get_version_from_manifest, version not found. Error: {exc}")
        return "0.0.0"
