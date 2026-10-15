from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import library_path
from .errors import AndroidSimError
from .util import load_json, save_json


LIBRARY_VERSION = 1
PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$")


def _load() -> dict[str, Any]:
    path = library_path()
    if not path.exists():
        return {"version": LIBRARY_VERSION, "apps": []}
    value = load_json(path)
    if value.get("version") != LIBRARY_VERSION or not isinstance(value.get("apps"), list):
        raise AndroidSimError(f"Unsupported library schema in {path}")
    return value


def list_apps() -> list[dict[str, Any]]:
    return sorted(_load()["apps"], key=lambda app: (not app.get("favorite", False), app["title"].casefold()))


def add(package: str, title: str, *, cover: str | None = None, favorite: bool = False, control_profile: str | None = None) -> dict[str, Any]:
    if not PACKAGE_RE.fullmatch(package):
        raise AndroidSimError("Invalid Android package name")
    value = _load()
    if any(app["package"] == package for app in value["apps"]):
        raise AndroidSimError(f"{package} is already in the library")
    entry = {
        "package": package,
        "title": title.strip() or package,
        "cover": str(Path(cover).expanduser().resolve()) if cover else None,
        "favorite": favorite,
        "control_profile": control_profile,
        "last_used_at": None,
    }
    value["apps"].append(entry)
    save_json(library_path(), value)
    return entry


def remove(package: str) -> dict[str, Any]:
    value = _load()
    before = len(value["apps"])
    value["apps"] = [app for app in value["apps"] if app["package"] != package]
    if len(value["apps"]) == before:
        raise AndroidSimError(f"{package} is not in the library")
    save_json(library_path(), value)
    return {"package": package, "removed": True}


def touch(package: str) -> None:
    value = _load()
    for app in value["apps"]:
        if app["package"] == package:
            app["last_used_at"] = datetime.now(timezone.utc).isoformat()
            save_json(library_path(), value)
            return
