from __future__ import annotations

import json
import hashlib
import platform
import sys
from pathlib import Path
from typing import Any

from .config import engine_root
from .errors import AndroidSimError


LOCK_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "engine" / "engine.lock.json",
    Path(sys.prefix) / "share" / "tempera-air" / "engine" / "engine.lock.json",
)


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _lock_path() -> Path:
    lock_path = next((path for path in LOCK_CANDIDATES if path.is_file()), None)
    if lock_path is None:
        searched = ", ".join(str(path) for path in LOCK_CANDIDATES)
        raise AndroidSimError(f"Engine lock not found; searched: {searched}")
    return lock_path


def lock() -> dict[str, Any]:
    lock_path = _lock_path()
    try:
        value = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AndroidSimError(f"Invalid engine lock: {exc}") from exc
    if value.get("schema_version") != 2:
        raise AndroidSimError("Unsupported engine lock schema")
    return value


def installation() -> dict[str, Any]:
    expected_lock = lock()
    current = engine_root() / "current"
    emulator = current / expected_lock["build"]["executable"]
    receipt_path = current / "build-receipt.json"
    result: dict[str, Any] = {
        "root": str(current),
        "emulator": str(emulator),
        "receipt": str(receipt_path),
        "valid": False,
        "reason": None,
    }
    if not emulator.is_file():
        result["reason"] = "custom_engine_missing"
        return result
    if not receipt_path.is_file():
        result["reason"] = "build_receipt_missing"
        return result
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        result["reason"] = "build_receipt_invalid"
        return result
    if receipt.get("schema_version") != 1 or receipt.get("lock_id") != expected_lock["lock_id"]:
        result["reason"] = "build_receipt_lock_mismatch"
        return result
    expected_digest = _digest(_lock_path())
    if receipt.get("lock_sha256") != expected_digest:
        result["reason"] = "build_receipt_digest_mismatch"
        return result
    emulator_entry = next(
        (item for item in receipt.get("files", []) if item.get("path") == expected_lock["build"]["executable"]),
        None,
    )
    if not emulator_entry or emulator_entry.get("sha256") != _digest(emulator):
        result["reason"] = "emulator_digest_mismatch"
        return result
    result.update({"valid": True, "reason": None, "receipt_data": receipt})
    return result


def custom_emulator() -> Path | None:
    if platform.system() != "Darwin" or platform.machine() not in {"arm64", "aarch64"}:
        return None
    candidate = installation()
    if not candidate["valid"]:
        return None
    return Path(candidate["emulator"])


def status() -> dict[str, Any]:
    root = engine_root()
    installed = installation()
    host_supported = platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}
    selected = installed["valid"] and host_supported
    return {
        "lock": lock(),
        "lock_sha256": _digest(_lock_path()),
        "root": str(root),
        "custom_engine": installed["emulator"],
        "installation": installed,
        "installed": installed["valid"],
        "selected": "custom" if selected else "sdk-fallback",
        "fallback_reason": None if selected else (installed["reason"] or "host_unsupported"),
        "host_supported": host_supported,
    }
