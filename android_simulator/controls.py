from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import controls_root
from .errors import AndroidSimError
from .util import save_json


CONTROL_VERSION = 1
ACTIONS = {
    "tap", "repeat_tap", "swipe", "swipe_hold", "dpad", "free_look",
    "aim_pan_shoot", "pinch", "mouse_zoom", "tilt", "key", "native_cursor",
}


def _validate_point(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, (int, float)) for item in value):
        raise AndroidSimError(f"{label} must be [x, y]")
    if not all(0.0 <= float(item) <= 1.0 for item in value):
        raise AndroidSimError(f"{label} coordinates must be normalized between 0 and 1")


def validate(profile: dict[str, Any]) -> dict[str, Any]:
    if profile.get("version") != CONTROL_VERSION:
        raise AndroidSimError(f"Control profile version must be {CONTROL_VERSION}")
    if profile.get("orientation") not in {"portrait", "landscape", "any"}:
        raise AndroidSimError("orientation must be portrait, landscape, or any")
    mappings = profile.get("mappings")
    if not isinstance(mappings, list):
        raise AndroidSimError("mappings must be a list")
    for mapping in mappings:
        if not isinstance(mapping, dict) or mapping.get("action") not in ACTIONS:
            raise AndroidSimError("Each mapping must contain a supported action")
        if not isinstance(mapping.get("input"), str) or not mapping["input"]:
            raise AndroidSimError("Each mapping must contain a non-empty input")
        for field in ("point", "start", "end", "center"):
            if field in mapping:
                _validate_point(mapping[field], field)
    return profile


def import_profile(source: Path) -> dict[str, Any]:
    try:
        profile = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AndroidSimError(f"Could not read control profile {source}: {exc}") from exc
    if not isinstance(profile, dict):
        raise AndroidSimError("Control profile must be a JSON object")
    validate(profile)
    package = str(profile.get("package", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        raise AndroidSimError("Control profile package is invalid")
    destination = controls_root() / f"{package}.{profile['orientation']}.json"
    save_json(destination, profile)
    return {"profile": profile, "path": str(destination)}


def list_profiles() -> list[dict[str, Any]]:
    root = controls_root()
    if not root.exists():
        return []
    result = []
    for path in sorted(root.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate(value)
            result.append({"path": str(path), "package": value.get("package"), "orientation": value.get("orientation"), "mappings": len(value["mappings"])})
        except (OSError, json.JSONDecodeError, AndroidSimError):
            result.append({"path": str(path), "invalid": True})
    return result
