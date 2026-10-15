from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import instance_metadata_path
from .errors import AndroidSimError
from .util import load_json, save_json


SETTINGS_VERSION = 1
RENDERERS = {"auto", "host", "gfxstream", "angle", "swiftshader_indirect"}
FPS_VALUES = {30, 60, 90, 120, 144, 240}

DEFAULT_SETTINGS: dict[str, Any] = {
    "version": SETTINGS_VERSION,
    "cpu_cores": 4,
    "ram_mb": 4096,
    "data_gb": 16,
    "width": 1080,
    "height": 1920,
    "dpi": 420,
    "fps": 60,
    "vsync": True,
    "renderer": "auto",
    "camera": "virtualscene",
    "microphone": False,
    "locale": "en-US",
}


def validate(values: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(DEFAULT_SETTINGS)
    result.update(values)
    if int(result["cpu_cores"]) not in range(1, 17):
        raise AndroidSimError("cpu_cores must be between 1 and 16")
    if int(result["ram_mb"]) not in range(2048, 16385):
        raise AndroidSimError("ram_mb must be between 2048 and 16384")
    if int(result["data_gb"]) < 8:
        raise AndroidSimError("data_gb must be at least 8")
    for key in ("width", "height"):
        if int(result[key]) < 320 or int(result[key]) > 7680:
            raise AndroidSimError(f"{key} must be between 320 and 7680")
    if int(result["dpi"]) < 120 or int(result["dpi"]) > 640:
        raise AndroidSimError("dpi must be between 120 and 640")
    if int(result["fps"]) not in FPS_VALUES:
        raise AndroidSimError("fps must be one of: 30, 60, 90, 120, 144, 240")
    if result["renderer"] not in RENDERERS:
        raise AndroidSimError("renderer must be one of: " + ", ".join(sorted(RENDERERS)))
    if result["camera"] not in {"none", "webcam0", "virtualscene"}:
        raise AndroidSimError("camera must be none, webcam0, or virtualscene")
    if not isinstance(result["vsync"], bool) or not isinstance(result["microphone"], bool):
        raise AndroidSimError("vsync and microphone must be booleans")
    result["version"] = SETTINGS_VERSION
    return result


def get(name: str) -> dict[str, Any]:
    path = instance_metadata_path(name)
    metadata = load_json(path)
    legacy = {
        "ram_mb": metadata.get("ram_mb", DEFAULT_SETTINGS["ram_mb"]),
        "data_gb": metadata.get("data_gb", DEFAULT_SETTINGS["data_gb"]),
    }
    return validate({**legacy, **dict(metadata.get("settings", {}))})


def update(name: str, changes: dict[str, Any]) -> dict[str, Any]:
    path = instance_metadata_path(name)
    metadata = load_json(path)
    previous = get(name)
    current = validate({**previous, **changes})
    if "settings" not in metadata:
        backup = path.with_suffix(".json.v0.bak")
        if not backup.exists():
            save_json(backup, metadata)
    metadata["schema_version"] = 2
    metadata["settings"] = current
    metadata["ram_mb"] = current["ram_mb"]
    metadata["data_gb"] = current["data_gb"]
    save_json(path, metadata)
    restart_fields = {
        key for key in changes if key not in {"microphone", "locale"} and previous.get(key) != current.get(key)
    }
    return {"name": name, "settings": current, "restart_required": bool(restart_fields), "restart_fields": sorted(restart_fields)}


def parse_assignment(assignment: str) -> tuple[str, Any]:
    if "=" not in assignment:
        raise AndroidSimError("setting must use key=value")
    key, raw = assignment.split("=", 1)
    if key not in DEFAULT_SETTINGS or key == "version":
        raise AndroidSimError(f"unknown setting: {key}")
    default = DEFAULT_SETTINGS[key]
    if isinstance(default, bool):
        if raw.lower() not in {"true", "false"}:
            raise AndroidSimError(f"{key} must be true or false")
        value: Any = raw.lower() == "true"
    elif isinstance(default, int):
        try:
            value = int(raw)
        except ValueError as exc:
            raise AndroidSimError(f"{key} must be an integer") from exc
    else:
        value = raw
    return key, value
