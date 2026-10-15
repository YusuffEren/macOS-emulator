#!/usr/bin/env python3
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def revisions(path: Path, tag: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for project in ET.parse(path).getroot().findall(tag):
        project_path = project.attrib.get("path") or project.attrib.get("name")
        revision = project.attrib.get("revision")
        if project_path and revision:
            result[project_path] = revision
    return result


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify-source-manifest.py FROZEN_OVERLAY RESOLVED_MANIFEST")
    expected = revisions(Path(sys.argv[1]), "extend-project")
    actual = revisions(Path(sys.argv[2]), "project")
    mismatches = [
        f"{path}: expected {revision}, got {actual.get(path, 'missing')}"
        for path, revision in expected.items()
        if actual.get(path) != revision
    ]
    if mismatches:
        raise SystemExit("source manifest mismatch:\n" + "\n".join(mismatches))
    print(f"verified {len(expected)} frozen source revisions")


if __name__ == "__main__":
    main()
