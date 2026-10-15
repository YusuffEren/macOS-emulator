from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .config import avd_home, state_root
from .errors import AndroidSimError


def _size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def disk_report() -> dict[str, Any]:
    candidates = [state_root() / "logs", state_root() / "recordings"]
    snapshot_dirs = list(avd_home().glob("*.avd/snapshots")) if avd_home().exists() else []
    rows = [{"path": str(path), "bytes": _size(path), "kind": "cache"} for path in candidates]
    rows.extend({"path": str(path), "bytes": _size(path), "kind": "snapshot"} for path in snapshot_dirs)
    return {"reclaimable_bytes": sum(row["bytes"] for row in rows), "items": rows}


def clean(*, confirmed: bool, running_names: set[str] | None = None) -> dict[str, Any]:
    if not confirmed:
        raise AndroidSimError("Disk cleanup is destructive; re-run with --yes")
    report = disk_report()
    running_names = running_names or set()
    blocked = [
        item["path"]
        for item in report["items"]
        if item["kind"] == "snapshot" and Path(item["path"]).parent.name.removesuffix(".avd") in running_names
    ]
    if blocked:
        raise AndroidSimError("Stop running instances before cleaning snapshots: " + ", ".join(blocked))
    for item in report["items"]:
        path = Path(item["path"])
        if not path.exists():
            continue
        resolved = path.resolve()
        allowed = (state_root().resolve(), avd_home().resolve())
        if not any(resolved.is_relative_to(root) for root in allowed):
            raise AndroidSimError(f"Refusing to clean path outside managed roots: {resolved}")
        shutil.rmtree(resolved)
    return {"reclaimed_bytes": report["reclaimable_bytes"], "removed": [item["path"] for item in report["items"]]}
