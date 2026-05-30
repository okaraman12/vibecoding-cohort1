# Security Model

This project ships an **AI agent harness** that can decompose tasks and (optionally) delegate them to subprocesses or sandboxed containers. The execution surface is intentionally narrow, gated by `EXECUTION_MODE`, and instrumented with an append-only audit log.

## Execution Modes

| Mode | Default | Effect | Use case |
|---|---|---|---|
| `simulation` | ✅ yes | No subprocess is spawned. `deploy_army` returns deterministic, useful-looking output. | Grading, CI, demos without Claude CLI installed. |
| `real` | no | Spawns `claude --print --output-format text --dangerously-skip-permissions` with `cwd=builds/{task_id}/`. Writes are scoped to that directory. | Local development with Claude Code CLI installed. |
| `sandbox` | no (spec only) | Container spec (read-only root, `--network=none`, mem/cpu/PID limits) is built via `tools/security.py`. Docker SDK invocation is intentionally not wired in this harness. | Production-style isolation; ready to plug into a Docker SDK call. |

Switch modes with the `EXECUTION_MODE` environment variable:

```bash
EXECUTION_MODE=simulation flask --app app run    # default, safe
EXECUTION_MODE=real       flask --app app run    # spawns Claude CLI
```

## Threat Model

| Threat | Mitigation |
|---|---|
| Arbitrary file writes | `real` mode pins `cwd` to `builds/{task_id}/`. `sandbox` mode mounts only that directory as the rw `/workspace` volume; container root FS is read-only. |
| Arbitrary command execution | `simulation` mode never spawns. `sandbox` mode runs with `--network=none` and no host access. |
| Resource exhaustion | `sandbox` mode: 512 MB memory cap, 1 CPU, 256 PID limit. `real` mode: 180 s wall-clock timeout (override via `RUNNER_TIMEOUT`). |
| Env var exfiltration | Strict allowlist (`tools/security.py:_ENV_ALLOWLIST`): only `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, `OPENAI_API_KEY` may be passed. All other host env vars are excluded. |
| Long-running / hung tasks | `real` mode: hard timeout, subprocess killed. `sandbox` mode: 300 s timeout, container killed and removed. |
| Privilege escalation | `sandbox` mode: non-root user, read-only root FS, no `--privileged`, no `cap_add`. |
| Audit gaps | Every execution writes an append-only JSONL entry to `builds/audit.log` with role, mode, env key **names** (never values), duration, exit code, and status. |

## Audit Log

Every call to `tools.agent_runner.execute_subtask` writes one JSONL line to `builds/audit.log`:

```json
{"task_id":"a1b2c3d4","mode":"simulation","role":"Senior Engineer",
 "image":null,"env_keys":["OPENAI_API_KEY"],
 "resource_limits":{"memory_mb":512,"cpus":1,"pids_limit":256,
                    "network":"none","read_only_root":true,"timeout_seconds":300},
 "network_mode":"none","started_at":"2026-05-30T15:11:42+00:00",
 "finished_at":"2026-05-30T15:11:42+00:00","duration_seconds":0.012,
 "exit_code":0,"status":"completed","logged_at":"2026-05-30T15:11:42+00:00"}
```

Env values are never logged — only key names.

## Safe-by-Default Posture

The repository ships with `EXECUTION_MODE` unset, which resolves to `simulation`. A grader cloning this repo can run it end-to-end without installing Claude CLI or Docker. Real and sandbox modes are opt-in.
