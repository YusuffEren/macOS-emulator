from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import avd as avd_module
from .config import (
    Toolchain,
    avd_home,
    backups_root,
    instance_metadata_path,
    validate_avd_name,
)
from .errors import AndroidSimError
from .util import load_json, save_json

BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
_BACKUP_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,120}")


def _backup_dir(backup_id: str) -> Path:
    if not _BACKUP_ID_PATTERN.fullmatch(backup_id):
        raise AndroidSimError("Invalid backup id")
    return backups_root() / backup_id


def _manifest_path(backup_id: str) -> Path:
    return _backup_dir(backup_id) / MANIFEST_NAME


def _read_manifest(backup_id: str) -> dict[str, Any]:
    path = _manifest_path(backup_id)
    manifest = load_json(path)
    if manifest.get("version") != BACKUP_VERSION:
        raise AndroidSimError(f"Unsupported backup manifest version in {backup_id!r}")
    if manifest.get("backup_id") != backup_id:
        raise AndroidSimError(f"Backup id mismatch in manifest for {backup_id!r}")
    return manifest


def _scan_files(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": str(item.relative_to(root)), "bytes": item.stat().st_size}
        for item in sorted(root.rglob("*"))
        if item.is_file()
    ]


def create(toolchain: Toolchain, name: str, *, notes: str | None = None) -> dict[str, Any]:
    """Back up a stopped managed instance, including its writable data and snapshots."""
    validate_avd_name(name)
    if not instance_metadata_path(name).is_file():
        raise AndroidSimError(f"No managed instance metadata for {name!r}")
    running_serial = avd_module._running_serial_for_avd(toolchain, name)
    if running_serial:
        raise AndroidSimError(f"Instance {name!r} is running as {running_serial}; stop it before backing it up")
    source_dir = avd_home() / f"{name}.avd"
    source_ini = avd_home() / f"{name}.ini"
    if not source_dir.is_dir() or not source_ini.is_file():
        raise AndroidSimError(f"AVD files for {name!r} are incomplete")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"{name}-{timestamp}-{uuid.uuid4().hex[:6]}"
    destination = _backup_dir(backup_id)
    if destination.exists():
        raise AndroidSimError(f"Backup destination already exists: {destination}")
    try:
        avd_destination = destination / "avd"
        shutil.copytree(source_dir, avd_destination)
        shutil.copy2(source_ini, destination / "instance.ini")
        shutil.copy2(instance_metadata_path(name), destination / "instance.json")
        files = _scan_files(destination)
        manifest = {
            "version": BACKUP_VERSION,
            "backup_id": backup_id,
            "instance": {"name": name},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes or "",
            "avd_home": str(avd_home()),
            "files": files,
            "bytes": sum(entry["bytes"] for entry in files),
            "file_count": len(files),
        }
        save_json(_manifest_path(backup_id), manifest)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
    return {
        "backup_id": backup_id,
        "instance": name,
        "bytes": manifest["bytes"],
        "file_count": manifest["file_count"],
        "path": str(destination),
    }


def list_backups() -> list[dict[str, Any]]:
    root = backups_root()
    if not root.exists():
        return []
    result: list[dict[str, Any]] = []
    for manifest_path in sorted(root.glob(f"*/{MANIFEST_NAME}")):
        backup_id = manifest_path.parent.name
        try:
            manifest = _read_manifest(backup_id)
        except AndroidSimError:
            result.append({"backup_id": backup_id, "path": str(manifest_path.parent), "invalid": True})
            continue
        result.append(
            {
                "backup_id": manifest["backup_id"],
                "instance": manifest["instance"]["name"],
                "created_at": manifest["created_at"],
                "bytes": manifest["bytes"],
                "file_count": manifest["file_count"],
                "notes": manifest.get("notes", ""),
                "path": str(manifest_path.parent),
            }
        )
    return sorted(result, key=lambda item: str(item.get("created_at", "")), reverse=True)


def verify(backup_id: str) -> dict[str, Any]:
    """Check that every file recorded in the manifest is present with the expected size."""
    manifest = _read_manifest(backup_id)
    root = _backup_dir(backup_id)
    mismatches: list[str] = []
    for entry in manifest["files"]:
        path = root / str(entry["path"])
        if not path.is_file():
            mismatches.append(f"missing: {entry['path']}")
        elif path.stat().st_size != entry["bytes"]:
            mismatches.append(f"size mismatch: {entry['path']}")
    return {
        "backup_id": backup_id,
        "instance": manifest["instance"]["name"],
        "ok": not mismatches,
        "mismatches": mismatches,
    }


def restore(toolchain: Toolchain, backup_id: str, *, name: str | None = None) -> dict[str, Any]:
    """Restore a verified backup as a managed instance."""
    manifest = _read_manifest(backup_id)
    report = verify(backup_id)
    if not report["ok"]:
        raise AndroidSimError(
            f"Backup integrity check failed for {backup_id!r}: " + "; ".join(report["mismatches"][:10])
        )
    target = validate_avd_name(name or str(manifest["instance"]["name"]))
    if target in avd_module.list_avds(toolchain):
        raise AndroidSimError(f"AVD {target!r} already exists; restore to a different name with --name")
    running_serial = avd_module._running_serial_for_avd(toolchain, target)
    if running_serial:
        raise AndroidSimError(f"Instance {target!r} is running as {running_serial}; stop it before restoring")

    source_root = _backup_dir(backup_id)
    destination_dir = avd_home() / f"{target}.avd"
    destination_ini = avd_home() / f"{target}.ini"
    destination_metadata = instance_metadata_path(target)
    if destination_dir.exists() or destination_ini.exists():
        raise AndroidSimError(f"AVD files for {target!r} already exist on disk")
    try:
        shutil.copytree(source_root / "avd", destination_dir)
        ini = avd_module._read_ini(source_root / "instance.ini")
        ini["path"] = str(destination_dir)
        ini["path.rel"] = f"avd/{target}.avd"
        avd_module._write_ini(destination_ini, ini)
        config_path = destination_dir / "config.ini"
        config = avd_module._read_ini(config_path)
        config["AvdId"] = target
        config["avd.ini.displayname"] = target
        avd_module._write_ini(config_path, config)
        metadata = load_json(source_root / "instance.json")
        metadata.update(
            {
                "name": target,
                "instance_uuid": str(uuid.uuid4()),
                "restored_from": backup_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "config_path": str(config_path),
            }
        )
        save_json(destination_metadata, metadata)
    except Exception:
        if destination_dir.exists():
            shutil.rmtree(destination_dir)
        destination_ini.unlink(missing_ok=True)
        destination_metadata.unlink(missing_ok=True)
        raise
    return metadata


def delete(backup_id: str, *, confirmed: bool = False) -> dict[str, Any]:
    if not confirmed:
        raise AndroidSimError("Backup deletion is destructive; re-run with --yes")
    manifest = _read_manifest(backup_id)
    root = backups_root().resolve()
    target = _backup_dir(backup_id).resolve()
    if not target.is_relative_to(root):
        raise AndroidSimError(f"Refusing to delete path outside managed backups: {target}")
    shutil.rmtree(target)
    return {"deleted": backup_id, "bytes": manifest["bytes"]}
