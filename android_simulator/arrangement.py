from __future__ import annotations

import math
from typing import Any

from . import settings
from .config import validate_avd_name
from .errors import AndroidSimError

DEFAULT_CELL_WIDTH = 460
DEFAULT_CELL_HEIGHT = 820
DEFAULT_MARGIN = 40
DEFAULT_ORIGIN_X = 60
DEFAULT_ORIGIN_Y = 60


def plan(
    names: list[str],
    *,
    columns: int | None = None,
    cell_width: int = DEFAULT_CELL_WIDTH,
    cell_height: int = DEFAULT_CELL_HEIGHT,
    margin: int = DEFAULT_MARGIN,
    origin_x: int = DEFAULT_ORIGIN_X,
    origin_y: int = DEFAULT_ORIGIN_Y,
) -> list[dict[str, Any]]:
    """Compute a row-major grid placement for a set of instance windows."""
    if not names:
        raise AndroidSimError("Arrange requires at least one instance name")
    if len(set(names)) != len(names):
        raise AndroidSimError("Arrange received duplicate instance names")
    for name in names:
        validate_avd_name(name)
    if cell_width < 160 or cell_height < 160:
        raise AndroidSimError("Cell size must be at least 160x160")
    if not 0 <= margin <= 2000:
        raise AndroidSimError("Margin must be between 0 and 2000")
    if not 0 <= origin_x <= 65535 or not 0 <= origin_y <= 65535:
        raise AndroidSimError("Origin coordinates must be between 0 and 65535")
    count = len(names)
    if columns is None:
        columns = max(1, math.ceil(math.sqrt(count)))
    if not 1 <= columns <= count:
        raise AndroidSimError(f"Columns must be between 1 and the instance count ({count})")

    placements: list[dict[str, Any]] = []
    for index, name in enumerate(names):
        row, column = divmod(index, columns)
        placements.append(
            {
                "name": name,
                "row": row,
                "column": column,
                "x": origin_x + column * (cell_width + margin),
                "y": origin_y + row * (cell_height + margin),
            }
        )
    return placements


def apply(placements: list[dict[str, Any]], *, dry_run: bool = False) -> dict[str, Any]:
    """Persist planned window offsets as per-instance settings applied on next start."""
    results: list[dict[str, Any]] = []
    for placement in placements:
        name = str(placement["name"])
        if dry_run:
            settings.get(name)  # validates that the managed instance exists
            results.append({"name": name, "window_x": placement["x"], "window_y": placement["y"], "applied": False})
            continue
        updated = settings.update(name, {"window_x": placement["x"], "window_y": placement["y"]})
        results.append(
            {
                "name": name,
                "window_x": placement["x"],
                "window_y": placement["y"],
                "applied": True,
                "restart_required": updated["restart_required"],
            }
        )
    return {
        "plan": placements,
        "applied": not dry_run,
        "instances": results,
    }
