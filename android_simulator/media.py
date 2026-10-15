from __future__ import annotations

from pathlib import Path
from typing import Any

from . import adb as adb_module
from .config import Toolchain
from .errors import AndroidSimError


def import_file(toolchain: Toolchain, serial: str, source: Path) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise AndroidSimError(f"File not found: {source}")
    remote = f"/sdcard/Download/{source.name}"
    adb_module.adb(toolchain, serial, ["push", source, remote], capture=False)
    adb_module.shell(toolchain, serial, ["am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{remote}"], check=False, quiet=True)
    return {"source": str(source), "destination": remote}


def export_file(toolchain: Toolchain, serial: str, remote: str, destination: Path) -> dict[str, Any]:
    if not remote.startswith("/sdcard/"):
        raise AndroidSimError("Only /sdcard paths can be exported")
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    adb_module.adb(toolchain, serial, ["pull", remote, destination], capture=False)
    return {"source": remote, "destination": str(destination)}


def capture(toolchain: Toolchain, serial: str, destination: Path) -> dict[str, Any]:
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Binary-safe capture uses adb pull through a temporary device file.
    remote = "/sdcard/Download/.tempera-capture.png"
    adb_module.adb(toolchain, serial, ["shell", "screencap", "-p", remote], capture=False)
    adb_module.adb(toolchain, serial, ["pull", remote, destination], capture=False)
    adb_module.adb(toolchain, serial, ["shell", "rm", "-f", remote], capture=False)
    return {"destination": str(destination)}


def record(toolchain: Toolchain, serial: str, destination: Path, seconds: int) -> dict[str, Any]:
    if seconds < 1 or seconds > 180:
        raise AndroidSimError("Recording duration must be between 1 and 180 seconds")
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    remote = "/sdcard/Download/.tempera-recording.mp4"
    adb_module.adb(
        toolchain,
        serial,
        ["shell", "screenrecord", "--time-limit", str(seconds), remote],
        capture=False,
    )
    adb_module.adb(toolchain, serial, ["pull", remote, destination], capture=False)
    adb_module.adb(toolchain, serial, ["shell", "rm", "-f", remote], capture=False)
    return {"destination": str(destination), "seconds": seconds}
