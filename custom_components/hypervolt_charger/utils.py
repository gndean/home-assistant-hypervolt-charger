import logging
import json
import os
import aiofiles

from .hypervolt_device_state import HypervoltDayOfWeek

_LOGGER = logging.getLogger(__name__)


async def get_version_from_manifest() -> str:
    """Attempt to read the manifest.json file and extract the version number. Returns 0.0.0 on failure"""
    try:
        manifest_filename = os.path.join(os.path.dirname(__file__), "manifest.json")
        _LOGGER.debug(
            f"get_version_from_manifest loading manifest: {manifest_filename}"
        )
        async with aiofiles.open(manifest_filename, encoding="utf-8") as manifest_file:
            contents = await manifest_file.read()
            manifest = json.loads(contents)
            version = manifest["version"]
            _LOGGER.debug(f"get_version_from_manifest returning version: {version}")

            return version

    except Exception as exc:
        _LOGGER.error(f"get_version_from_manifest, version not found. Error: {exc}")
        return "0.0.0"


def get_days_from_days_of_week(days_of_week: int) -> list[str]:
    """Convert a days_of_week bitmask to a list of strings"""
    days = []
    for day in HypervoltDayOfWeek:
        if days_of_week & day.value and day != HypervoltDayOfWeek.ALL:
            days.append(day.name)

    return days
