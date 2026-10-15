#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent
LOCK_PATH = ENGINE_ROOT / "engine.lock.json"
SHA_RE = re.compile(r"[0-9a-f]{40}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"engine lock error: {message}")


def main() -> None:
    value = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if value.get("schema_version") != 2:
        fail("schema_version must be 2")
    if value.get("target") != "macos-arm64":
        fail("target must be macos-arm64")

    manifest = value["manifest"]
    overlay = ENGINE_ROOT / manifest["frozen_overlay"]
    if digest(overlay) != manifest["frozen_overlay_sha256"]:
        fail("frozen manifest SHA-256 does not match the lock")
    projects = ET.parse(overlay).getroot().findall("extend-project")
    if len(projects) != manifest["project_count"]:
        fail("frozen manifest project count does not match the lock")
    paths = {project.attrib["path"] for project in projects}
    if len(paths) != len(projects):
        fail("frozen manifest contains duplicate project paths")
    revisions = {project.attrib["path"]: project.attrib["revision"] for project in projects}
    if any(not SHA_RE.fullmatch(revision) for revision in revisions.values()):
        fail("every frozen project revision must be a full lowercase Git SHA")

    for name in ("aemu", "gfxstream"):
        component = value["components"][name]
        if revisions.get(component["path"]) != component["commit"]:
            fail(f"{name} commit disagrees with the frozen manifest")
    moltenvk = value["components"]["moltenvk"]
    if not SHA_RE.fullmatch(moltenvk["commit"]):
        fail("MoltenVK commit must be a full lowercase Git SHA")

    patch_series = value["patch_series"]
    patch_path = ENGINE_ROOT / patch_series["path"]
    if digest(patch_path) != patch_series["sha256"]:
        fail("patch series SHA-256 does not match the lock")
    patches = json.loads(patch_path.read_text(encoding="utf-8"))
    if patches.get("schema_version") != 1 or not isinstance(patches.get("patches"), list):
        fail("invalid patch series")

    print(
        json.dumps(
            {
                "lock_id": value["lock_id"],
                "lock_sha256": digest(LOCK_PATH),
                "frozen_projects": len(projects),
                "patches": len(patches["patches"]),
                "status": "ok",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
