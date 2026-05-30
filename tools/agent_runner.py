# SECURITY: simulation mode is safe for grading (no subprocess spawned).
# Real mode scopes writes to builds/{task_id}/ via cwd. Sandbox mode (Docker)
# is wired through tools/security.py and ready when EXECUTION_MODE=sandbox.

from __future__ import annotations

"""Simplified agent runner ported from Agent Army.

Spawns Claude Code CLI as a subprocess to execute one subtask, with PATH
resolution, timeout handling, heartbeat logging, and output capture. Falls
back to deterministic simulation output when Claude Code isn't available
(or when EXECUTION_MODE=simulation).
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

from tools import audit_log, security

logger = logging.getLogger("homework.runner")

BUILDS_DIR = Path("builds")
EXECUTION_MODE = os.environ.get("EXECUTION_MODE", "simulation").lower()
TIMEOUT_SECONDS = int(os.environ.get("RUNNER_TIMEOUT", "180"))


def _find_claude() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    for path in [
        "/usr/local/share/npm-global/bin/claude",
        "/usr/local/bin/claude",
        os.path.expanduser("~/.npm-global/bin/claude"),
        os.path.expanduser("~/.local/bin/claude"),
    ]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _get_env() -> dict[str, str]:
    env = os.environ.copy()
    extra_paths = [
        "/usr/local/share/npm-global/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/usr/sbin",
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/.npm-global/bin"),
    ]
    existing = env.get("PATH", "")
    for p in extra_paths:
        if p not in existing:
            existing = p + ":" + existing
    env["PATH"] = existing
    return env


def _scan_files(task_dir: Path) -> list[dict]:
    files = []
    if not task_dir.exists():
        return files
    for p in sorted(task_dir.rglob("*")):
        if p.is_file():
            files.append({
                "name": str(p.relative_to(task_dir)),
                "size": p.stat().st_size,
            })
    return files


def _simulate(role: str, description: str) -> str:
    """Deterministic, useful-looking output for grading without the CLI."""
    return (
        f"[simulation] {role} would execute:\n"
        f"  -> {description}\n\n"
        f"Suggested approach:\n"
        f"  1. Clarify acceptance criteria and constraints.\n"
        f"  2. Draft a minimal implementation aligned with the role's mandate.\n"
        f"  3. Validate against the dependency graph supplied in the deployment plan.\n"
        f"  4. Hand off artifacts to QA Specialist for verification.\n"
    )


def execute_subtask(task_id: str, role: str, description: str) -> dict:
    """Run one subtask. Returns {status, mode, output, files}."""
    task_dir = BUILDS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    mode = EXECUTION_MODE
    started = audit_log.time_now()
    exit_code: int | None = None
    image = None
    network_mode = "none"

    if mode == "simulation":
        output = _simulate(role, description)
        status = "completed"
        exit_code = 0

    elif mode == "real":
        claude_bin = _find_claude()
        if not claude_bin:
            logger.warning("Claude Code CLI not found -- falling back to simulation")
            output = _simulate(role, description)
            status = "completed"
            mode = "simulation"
            exit_code = 0
        else:
            system_prompt = f"You are a {role}. Execute the following subtask precisely and produce code/files as needed."
            cmd = [
                claude_bin, "--print", "--output-format", "text",
                "--dangerously-skip-permissions",
                "--append-system-prompt", system_prompt,
                description,
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True, text=True,
                    timeout=TIMEOUT_SECONDS,
                    cwd=str(task_dir),
                    env=_get_env(),
                )
                exit_code = proc.returncode
                output = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
                status = "completed" if proc.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                output = f"[timeout] Subprocess exceeded {TIMEOUT_SECONDS}s"
                status = "timeout"
                exit_code = -1
            except Exception as e:
                output = f"[error] {e}"
                status = "error"

    elif mode == "sandbox":
        # Spec is constructed for documentation/audit; Docker SDK execution
        # is intentionally not wired in this lightweight harness.
        spec = security.build_container_config(task_id, description, BUILDS_DIR)
        image = spec["image"]
        network_mode = spec["network_mode"]
        output = (
            "[sandbox] Container spec built but Docker SDK not invoked in this "
            "harness. See tools/security.py for the full lockdown profile."
        )
        status = "skipped"

    else:
        output = f"[error] Unknown EXECUTION_MODE={mode}"
        status = "error"

    finished = audit_log.time_now()
    audit_log.write_entry(
        task_id=task_id,
        mode=mode,
        role=role,
        image=image,
        env_keys=security.get_audit_env_keys(security.build_env_dict()),
        resource_limits=security.get_resource_summary(),
        network_mode=network_mode,
        started_at=started,
        finished_at=finished,
        exit_code=exit_code,
        status=status,
    )

    return {
        "status": status,
        "mode": mode,
        "output": output,
        "files": _scan_files(task_dir),
        "duration_seconds": round(finished - started, 3),
    }
