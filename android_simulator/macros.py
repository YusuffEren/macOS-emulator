from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import agent
from .config import Toolchain, macros_root
from .errors import AndroidSimError
from .util import save_json


MACRO_VERSION = 1
MAX_STEPS = 10_000


def validate(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("version") != MACRO_VERSION:
        raise AndroidSimError(f"Macro version must be {MACRO_VERSION}")
    name = value.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
        raise AndroidSimError("Macro name must be 1-80 safe filename characters")
    steps = value.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise AndroidSimError(f"Macro steps must contain 1-{MAX_STEPS} actions")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("action") not in agent.ALLOWED_ACTIONS:
            raise AndroidSimError(f"Macro step {index} has an unsupported action")
        if not isinstance(step.get("arguments", {}), dict):
            raise AndroidSimError(f"Macro step {index} arguments must be an object")
        if step["action"] == "wait":
            seconds = float(step.get("arguments", {}).get("seconds", 1))
            if seconds < 0 or seconds > 60:
                raise AndroidSimError(f"Macro step {index} wait must be between 0 and 60 seconds")
    return value


def import_macro(source: Path) -> dict[str, Any]:
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AndroidSimError(f"Could not read macro {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise AndroidSimError("Macro must be a JSON object")
    validate(value)
    destination = macros_root() / f"{value['name']}.json"
    save_json(destination, value)
    return {"name": value["name"], "steps": len(value["steps"]), "path": str(destination)}


def list_macros() -> list[dict[str, Any]]:
    root = macros_root()
    if not root.exists():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate(value)
            result.append({"name": value["name"], "steps": len(value["steps"]), "path": str(path)})
        except (OSError, json.JSONDecodeError, AndroidSimError):
            result.append({"path": str(path), "invalid": True})
    return result


def run_macro(
    toolchain: Toolchain,
    serial: str,
    name: str,
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
        raise AndroidSimError("Invalid macro name")
    path = macros_root() / f"{name}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AndroidSimError(f"Could not read macro {name!r}: {exc}") from exc
    validate(value)
    actions = [
        agent.Action(step["action"], dict(step.get("arguments", {})), str(step.get("description", "")))
        for step in value["steps"]
    ]
    if not confirmed and any(agent.requires_confirmation(action) for action in actions):
        raise AndroidSimError("Macro contains sensitive actions; inspect it and re-run with --yes")
    for action in actions:
        agent.execute(toolchain, serial, action, confirmed=confirmed)
    return {"name": name, "executed_steps": len(actions)}
