from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = 1


@dataclass
class Response:
    status: str = "ok"
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "request_id": self.request_id,
            "status": self.status,
            "data": self.data,
            "warnings": self.warnings,
            "error": self.error,
        }


def emit(response: Response) -> None:
    print(json.dumps(response.as_dict(), indent=2, sort_keys=True))


def emit_event(event: str, data: Any, *, request_id: str) -> None:
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "event": event,
                "data": data,
            },
            sort_keys=True,
        ),
        flush=True,
    )
