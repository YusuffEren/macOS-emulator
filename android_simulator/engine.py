from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .config import engine_root
from .errors import AndroidSimError


LOCK_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "engine" / "engine.lock.json",
    Path(sys.prefix) / "share" / "tempera-air" / "engine.lock.json",
)


def lock() -> dict[str, Any]:
    lock_path = next((path for path in LOCK_CANDIDATES if path.is_file()), None)
    if lock_path is None:
        searched = ", ".join(str(path) for path in LOCK_CANDIDATES)
        raise AndroidSimError(f"Engine lock not found; searched: {searched}")
    try:
        value = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AndroidSimError(f"Invalid engine lock: {exc}") from exc
    if value.get("schema_version") != 1:
        raise AndroidSimError("Unsupported engine lock schema")
    return value


def status() -> dict[str, Any]:
    root = engine_root()
    current = root / "current" / "emulator"
    return {
        "lock": lock(),
        "root": str(root),
        "custom_engine": str(current),
        "installed": current.is_file(),
        "host_supported": __import__("platform").system() == "Darwin" and __import__("platform").machine() in {"arm64", "aarch64"},
    }
