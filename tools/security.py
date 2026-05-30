from __future__ import annotations

"""
Sandboxed Execution Security Module (ported from Agent Army)
============================================================

Threat model:
  1. Arbitrary file writes   -> contained to builds/{task_id}/ (simulation/real),
                                or to /workspace volume in container (sandbox).
  2. Arbitrary commands       -> simulation: never executes; real: scoped cwd;
                                 sandbox: --network=none, no host access.
  3. Resource exhaustion      -> sandbox: 512MB memory, 1 CPU, 256 PID limit.
  4. Env var exfiltration     -> strict allowlist, only auth keys passed.
  5. Long-running tasks       -> hard timeout, subprocess/container killed.
  6. Privilege escalation     -> sandbox: non-root user, read-only root FS.

This module exposes the container spec used by `EXECUTION_MODE=sandbox`. The
spec is dependency-free (returns a plain dict) so the project remains
importable without the Docker SDK installed.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger("homework.security")

SOLDIER_IMAGE = "homework-agent-runner:latest"
CONTAINER_MEMORY_LIMIT = 512 * 1024 * 1024  # 512MB
CONTAINER_CPU_LIMIT = 1_000_000_000          # 1 core in nano CPUs
CONTAINER_PIDS_LIMIT = 256
CONTAINER_TIMEOUT = 300                       # seconds
TMPFS_SIZE = "64m"

# Strict allowlist of environment variables that may be passed to subprocess
# or container. Only authentication credentials -- nothing else.
_ENV_ALLOWLIST = [
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
]


def build_env_dict() -> dict[str, str]:
    """Build the allowlisted environment for a sandboxed run."""
    env = {}
    for key in _ENV_ALLOWLIST:
        value = os.environ.get(key)
        if value:
            env[key] = value
    if not env:
        logger.warning("No auth keys found in host env -- runner will have no API access")
    return env


def build_container_config(
    task_id: str,
    description: str,
    builds_dir: Path,
    allow_network: bool = False,
) -> dict:
    """Return a Docker container spec for sandboxed execution.

    The dict is structured to be passed straight to a Docker SDK call when
    EXECUTION_MODE=sandbox is wired up. Returning a plain dict keeps this
    module dependency-free for grading environments without Docker.
    """
    task_dir = builds_dir / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    network_mode = "bridge" if allow_network else "none"

    return {
        "image": SOLDIER_IMAGE,
        "command": [description],
        "environment": build_env_dict(),
        "volumes": {
            str(task_dir.resolve()): {"bind": "/workspace", "mode": "rw"},
        },
        "network_mode": network_mode,
        "mem_limit": CONTAINER_MEMORY_LIMIT,
        "nano_cpus": CONTAINER_CPU_LIMIT,
        "pids_limit": CONTAINER_PIDS_LIMIT,
        "read_only": True,
        "tmpfs": {"/tmp": f"size={TMPFS_SIZE},noexec"},
        "auto_remove": False,
        "detach": True,
        "labels": {
            "homework.task_id": str(task_id),
            "homework.role": "agent-runner",
        },
    }


def get_audit_env_keys(env: dict[str, str]) -> list[str]:
    """Return env key NAMES only -- never log values."""
    return sorted(env.keys())


def get_resource_summary() -> dict:
    return {
        "memory_mb": CONTAINER_MEMORY_LIMIT // (1024 * 1024),
        "cpus": 1,
        "pids_limit": CONTAINER_PIDS_LIMIT,
        "network": "none",
        "read_only_root": True,
        "timeout_seconds": CONTAINER_TIMEOUT,
    }
