from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

from . import adb as adb_module
from .config import Toolchain, state_root
from .errors import AndroidSimError


ALLOWED_ACTIONS = {"tap", "type", "swipe", "wait", "back", "home"}
SENSITIVE_TERMS = {
    "buy", "purchase", "pay", "checkout", "send", "delete", "remove account",
    "satın al", "ödeme", "gönder", "sil", "hesabı kaldır",
}


@dataclass(frozen=True)
class Action:
    name: str
    arguments: dict[str, Any]
    description: str = ""


def requires_confirmation(action: Action) -> bool:
    text = f"{action.name} {action.description} {action.arguments}".casefold()
    return any(term in text for term in SENSITIVE_TERMS)


def _audit(serial: str, action: Action, status: str, *, confirmation_required: bool) -> None:
    arguments = dict(action.arguments)
    if "text" in arguments:
        arguments["text"] = "<redacted>"
    path = state_root() / "logs" / "agent-audit.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "serial": serial,
        "action": action.name,
        "arguments": arguments,
        "description": action.description,
        "confirmation_required": confirmation_required,
        "status": status,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _record_step(action: Action) -> None:
    """Append an executed action to the open recording session, if any."""
    from . import recording

    recording.record_step(action)


def execute(toolchain: Toolchain, serial: str, action: Action, *, confirmed: bool = False) -> dict[str, Any]:
    if action.name not in ALLOWED_ACTIONS:
        raise AndroidSimError(f"Unsupported agent action: {action.name}")
    confirmation_required = requires_confirmation(action)
    if confirmation_required and not confirmed:
        _audit(serial, action, "denied", confirmation_required=True)
        raise AndroidSimError("This action requires explicit confirmation; re-run with --yes")
    args = action.arguments
    if action.name == "tap":
        command = ["input", "tap", str(int(args["x"])), str(int(args["y"]))]
    elif action.name == "type":
        text = str(args["text"]).replace(" ", "%s")
        command = ["input", "text", text]
    elif action.name == "swipe":
        command = ["input", "swipe", *(str(int(args[key])) for key in ("x1", "y1", "x2", "y2")), str(int(args.get("duration_ms", 300)))]
    elif action.name == "back":
        command = ["input", "keyevent", "KEYCODE_BACK"]
    elif action.name == "home":
        command = ["input", "keyevent", "KEYCODE_HOME"]
    else:
        import time
        time.sleep(float(args.get("seconds", 1)))
        _audit(serial, action, "executed", confirmation_required=confirmation_required)
        _record_step(action)
        return {"action": action.name, "executed": True}
    adb_module.shell(toolchain, serial, command)
    _audit(serial, action, "executed", confirmation_required=confirmation_required)
    _record_step(action)
    return {"action": action.name, "executed": True}
