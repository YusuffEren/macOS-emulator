from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import agent, macros
from .config import macros_root
from .errors import AndroidSimError
from .util import load_json, save_json

RECORDING_VERSION = 1
SESSION_NAME = "recording-session.json"


def session_path() -> Path:
    return macros_root() / SESSION_NAME


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
        raise AndroidSimError("Recording name must be 1-80 safe filename characters")
    return name


def _contains_typed_text(steps: list[dict[str, Any]]) -> bool:
    return any(step.get("action") == "type" for step in steps)


def start(name: str, *, notes: str = "") -> dict[str, Any]:
    """Open a guarded recording session that captures executed agent actions."""
    _validate_name(name)
    if session_path().exists():
        raise AndroidSimError("A recording session is already open; stop or cancel it first")
    session = {
        "version": RECORDING_VERSION,
        "name": name,
        "notes": notes,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [],
    }
    save_json(session_path(), session)
    return {"name": name, "recording": True, "steps": 0}


def status() -> dict[str, Any]:
    if not session_path().exists():
        return {"recording": False}
    session = load_json(session_path())
    steps = session.get("steps", [])
    return {
        "recording": True,
        "name": session.get("name", ""),
        "started_at": session.get("started_at", ""),
        "steps": len(steps),
        "contains_typed_text": _contains_typed_text(steps),
    }


def record_step(action: agent.Action) -> dict[str, Any] | None:
    """Append one executed action to the open session, if any."""
    if not session_path().exists():
        return None
    session = load_json(session_path())
    steps = session.setdefault("steps", [])
    steps.append(
        {"action": action.name, "arguments": dict(action.arguments), "description": action.description}
    )
    save_json(session_path(), session)
    return {"name": session.get("name", ""), "steps": len(steps)}


def stop() -> dict[str, Any]:
    """Validate and save the open session as a replayable macro."""
    if not session_path().exists():
        raise AndroidSimError("No recording session is open")
    session = load_json(session_path())
    steps = session.get("steps", [])
    if not steps:
        raise AndroidSimError("Recording is empty; cancel it instead of stopping")
    macro = {
        "version": macros.MACRO_VERSION,
        "name": session.get("name", ""),
        "steps": steps,
    }
    macros.validate(macro)
    destination = macros_root() / f"{macro['name']}.json"
    save_json(destination, macro)
    session_path().unlink()
    return {
        "name": macro["name"],
        "steps": len(steps),
        "path": str(destination),
        "contains_typed_text": _contains_typed_text(steps),
    }


def cancel() -> dict[str, Any]:
    if not session_path().exists():
        raise AndroidSimError("No recording session is open")
    session = load_json(session_path())
    session_path().unlink()
    return {
        "cancelled": session.get("name", ""),
        "steps_discarded": len(session.get("steps", [])),
    }
