from __future__ import annotations

"""JSONL audit log -- one line per execution.

Records env key NAMES (never values), durations, exit codes, and resource
limits. Lives at builds/audit.log. Mirrors the schema of the Agent Army
SQLAlchemy AuditLog model without requiring a database.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_LOG_PATH = Path("builds") / "audit.log"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_entry(
    *,
    task_id: str,
    mode: str,
    role: str,
    image: str | None,
    env_keys: list[str],
    resource_limits: dict[str, Any],
    network_mode: str,
    started_at: float,
    finished_at: float | None,
    exit_code: int | None,
    status: str,
) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    duration = (finished_at - started_at) if finished_at else None
    entry = {
        "task_id": task_id,
        "mode": mode,
        "role": role,
        "image": image,
        "env_keys": env_keys,
        "resource_limits": resource_limits,
        "network_mode": network_mode,
        "started_at": datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat(timespec="seconds"),
        "finished_at": (
            datetime.fromtimestamp(finished_at, tz=timezone.utc).isoformat(timespec="seconds")
            if finished_at else None
        ),
        "duration_seconds": round(duration, 3) if duration is not None else None,
        "exit_code": exit_code,
        "status": status,
        "logged_at": _now_iso(),
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def time_now() -> float:
    return time.time()
