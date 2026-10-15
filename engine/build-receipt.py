#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def output(*command: str) -> str:
    return subprocess.run(command, check=False, capture_output=True, text=True).stdout.strip()


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: build-receipt.py LOCK DISTRIBUTION SOURCE_MANIFEST OUTPUT")
    lock_path, distribution, source_manifest, receipt_path = map(Path, sys.argv[1:])
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    emulator = distribution / lock["build"]["executable"]
    if not emulator.is_file():
        raise SystemExit(f"missing emulator executable: {emulator}")
    files = []
    for relative in (
        lock["build"]["executable"],
        "lib64/vulkan/libMoltenVK-tempera.dylib",
        lock["components"]["moltenvk"]["staged_icd"],
    ):
        candidate = distribution / relative
        if not candidate.is_file():
            raise SystemExit(f"missing required engine artifact: {candidate}")
        files.append({"path": relative, "bytes": candidate.stat().st_size, "sha256": digest(candidate)})
    receipt = {
        "schema_version": 1,
        "lock_id": lock["lock_id"],
        "lock_sha256": digest(lock_path),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "host": {"system": platform.system(), "machine": platform.machine(), "release": platform.release()},
        "toolchain": {
            "xcode": output("xcodebuild", "-version"),
            "clang": output("clang", "--version").splitlines()[0],
            "repo": output("repo", "--version"),
        },
        "source_manifest_sha256": digest(source_manifest),
        "components": {name: component["commit"] for name, component in lock["components"].items()},
        "files": files,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
