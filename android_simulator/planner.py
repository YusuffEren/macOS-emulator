from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import agent, macros
from .config import macros_root, state_root
from .errors import AndroidSimError
from .util import load_json, save_json

PLANNER_VERSION = 1
WIRE_VERSION = 1
MAX_RESPONSE_BYTES = 1024 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

ACTION_ARGUMENTS: dict[str, dict[str, str]] = {
    "tap": {"x": "integer", "y": "integer"},
    "type": {"text": "string"},
    "swipe": {
        "x1": "integer",
        "y1": "integer",
        "x2": "integer",
        "y2": "integer",
        "duration_ms": "optional integer, default 300",
    },
    "back": {},
    "home": {},
    "wait": {"seconds": "optional number between 0 and 60, default 1"},
}


def planners_path() -> Path:
    return state_root() / "planners.json"


def _validate_profile_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name):
        raise AndroidSimError("Planner name must be 1-64 safe filename characters")
    return name


def _validate_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.hostname or ""
    if parsed.scheme == "https":
        return endpoint
    if parsed.scheme == "http" and host in LOOPBACK_HOSTS:
        return endpoint
    requirement = "HTTPS (or HTTP on a loopback host for local models)"
    raise AndroidSimError(f"Planner endpoint must use {requirement}: {endpoint}")


def _load_profiles() -> dict[str, Any]:
    path = planners_path()
    if not path.exists():
        return {"version": PLANNER_VERSION, "planners": []}
    value = load_json(path)
    if value.get("version") != PLANNER_VERSION:
        raise AndroidSimError(f"Unsupported planner store version: {value.get('version')!r}")
    if not isinstance(value.get("planners"), list):
        raise AndroidSimError("Planner store is corrupt: 'planners' must be a list")
    return value


def _save_profiles(store: dict[str, Any]) -> None:
    save_json(planners_path(), store)


def _find_profile(store: dict[str, Any], name: str) -> dict[str, Any]:
    for profile in store["planners"]:
        if profile.get("name") == name:
            return profile
    raise AndroidSimError(f"Unknown planner profile: {name!r}")


def add(
    name: str,
    endpoint: str,
    *,
    api_key_env: str = "",
    model: str = "",
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Register a BYOK planner profile. The API key itself is never stored."""
    _validate_profile_name(name)
    _validate_endpoint(endpoint)
    if api_key_env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
        raise AndroidSimError("api_key_env must be a valid environment variable name")
    if not 5 <= timeout_seconds <= 300:
        raise AndroidSimError("timeout must be between 5 and 300 seconds")
    store = _load_profiles()
    if any(profile.get("name") == name for profile in store["planners"]):
        raise AndroidSimError(f"Planner profile {name!r} already exists; remove it first")
    profile = {
        "name": name,
        "endpoint": endpoint,
        "api_key_env": api_key_env,
        "model": model,
        "timeout_seconds": timeout_seconds,
    }
    store["planners"].append(profile)
    _save_profiles(store)
    return profile


def list_planners() -> list[dict[str, Any]]:
    return list(_load_profiles()["planners"])


def remove(name: str) -> dict[str, Any]:
    _validate_profile_name(name)
    store = _load_profiles()
    _find_profile(store, name)
    store["planners"] = [profile for profile in store["planners"] if profile.get("name") != name]
    _save_profiles(store)
    return {"removed": name}


def _post_json(
    endpoint: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise AndroidSimError(f"Planner endpoint returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise AndroidSimError(f"Could not reach planner endpoint: {exc.reason}") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise AndroidSimError(f"Planner response exceeded {MAX_RESPONSE_BYTES} bytes")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AndroidSimError(f"Planner response is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AndroidSimError("Planner response must be a JSON object")
    return value


def _slugify_goal(goal: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", goal.strip()).strip("-")
    return (slug[:60].rstrip("-") or "plan").lstrip("-") or "plan"


def plan(
    profile_name: str,
    goal: str,
    *,
    save_as: str | None = None,
    force: bool = False,
    transport=None,
) -> dict[str, Any]:
    """Ask a BYOK planner for an action plan and save it as a guarded macro.

    The planner never executes anything: its output is validated against the
    same contract as imported macros and replay must pass the existing
    confirmation gates.
    """
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000:
        raise AndroidSimError("Goal must be 1-2000 characters")
    profile = _find_profile(_load_profiles(), _validate_profile_name(profile_name))
    api_key = ""
    if profile.get("api_key_env"):
        api_key = os.environ.get(profile["api_key_env"], "")
        if not api_key:
            raise AndroidSimError(
                f"Planner API key is not set; export it as {profile['api_key_env']}"
            )
    payload = {
        "schema_version": WIRE_VERSION,
        "goal": goal,
        "model": profile.get("model", ""),
        "allowed_actions": sorted(agent.ALLOWED_ACTIONS),
        "action_arguments": ACTION_ARGUMENTS,
    }
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    post = transport or _post_json
    response = post(
        profile["endpoint"],
        payload,
        headers=headers,
        timeout_seconds=int(profile.get("timeout_seconds", 60)),
    )
    if response.get("schema_version") != WIRE_VERSION:
        raise AndroidSimError("Planner response schema_version must be 1")
    steps = response.get("steps")
    if not isinstance(steps, list):
        raise AndroidSimError("Planner response must contain a 'steps' array")
    name = save_as or _slugify_goal(goal)
    macro = {"version": macros.MACRO_VERSION, "name": name, "steps": steps}
    macros.validate(macro)
    destination = macros_root() / f"{name}.json"
    if destination.exists() and not force:
        raise AndroidSimError(f"A macro named {name!r} already exists; re-run with --force to replace it")
    save_json(destination, macro)
    actions = [
        agent.Action(step["action"], dict(step.get("arguments", {})), str(step.get("description", "")))
        for step in steps
    ]
    return {
        "planner": profile_name,
        "goal": goal,
        "saved_as": name,
        "steps": len(steps),
        "path": str(destination),
        "requires_confirmation": any(agent.requires_confirmation(action) for action in actions),
        "contains_typed_text": any(action.name == "type" for action in actions),
    }
