# Proje Adı

vbl1

## Proje Hakkında

Bu proje, çeşitli Python modüllerinden oluşan bir yazılım uygulamasıdır. Projede agent ve asistan dosyaları ile, front-end tarafında ise HTML dosyaları ile kullanıcı ara yüzleri oluşturulmuştur.

## Kurulum

Projeyi çalıştırmak için gereksinim dosyasındakı paketlerin kurulması gerekmektedir. Bunun için:

```
pip install -r requirements.txt
```

komutunu çalıştırarak gerekli tüm bağımlılıkları yükleyebilirsiniz.

## Kullanım

Proje, arka planda `app.py`, `agent.py`, `asistan.py` ve `llm.py` Python dosyaları ve ön yüzde `frontend` klasöründeki HTML dosyaları ile çalışmaktadır. Her bir bileşen spesifik işlemler için tasarlanmıştır.

## `deploy_army` — Specialized Agent Deployment Tool

`deploy_army` is a first-class tool exposed to the coding agent at `/agent`. Given a free-form task description, it produces a structured deployment plan: a mission summary, a decomposition into 3–6 subtasks, role assignments drawn from a fixed roster of professional titles, a per-subtask complexity rating, a risk assessment, and a strategic dependency graph. When `EXECUTION_MODE=real`, it also delegates each subtask to a Claude Code subprocess scoped to `builds/{task_id}/` and returns the captured output alongside the plan.

### Roles

- **Lead Architect** — system design, interface contracts, decomposition.
- **Senior Engineer** — implementation, refactors, integration work.
- **Code Reviewer** — diff review, style, maintainability checks.
- **Security Analyst** — threat modeling, secrets handling, sandbox posture.
- **QA Specialist** — test design, acceptance verification.

### Example

Open `/agent`, start a session, and send:

> Build a small CLI that ingests a CSV of users, validates emails, and writes a cleaned CSV. Plan and execute.

The agent will call `deploy_army(task=..., execute=true)`. The frontend renders the result as a deployment-plan card: header chips (task id, execution mode, subtask count), a mission summary, a risk paragraph, and one row per subtask with a colored role badge, the subtask description, dependency list, complexity pill, and — when `execute=true` — a collapsed execution panel showing status, mode, duration, and captured stdout.

### Tech Approach

- **Decomposition** uses the OpenAI Chat Completions API with a strict JSON-only system prompt; the response is parsed with a regex-bounded `json.loads` and defensively coerced to a clean schema, so a malformed model response still yields a runnable plan.
- **Execution** is delegated to `tools/agent_runner.py`, a simplified port of [Agent Army's](https://github.com/) runner. It resolves the `claude` binary across the common install paths (Homebrew, npm-global, `~/.local/bin`), runs `claude --print --output-format text --dangerously-skip-permissions` with `cwd` pinned to `builds/{task_id}/`, captures stdout/stderr, enforces a wall-clock timeout, and degrades gracefully to simulation when the CLI is absent.
- **Security** is centralized in `tools/security.py`: a strict env-var allowlist, plus a fully built Docker container spec (read-only root, `--network=none`, 512 MB / 1 CPU / 256 PID limits, tmpfs `/tmp`) that is ready to plug into a Docker SDK call when `EXECUTION_MODE=sandbox`. See [`SECURITY.md`](./SECURITY.md) for the full threat model.
- **Auditability** is provided by `tools/audit_log.py`, which appends one JSONL entry per execution to `builds/audit.log` — env key **names** (never values), durations, exit codes, and resource limits.

### Modes

| `EXECUTION_MODE` | Behavior |
|---|---|
| `simulation` *(default)* | Returns a deterministic plan + role-aware mock output. No subprocess. Safe for grading without Claude CLI. |
| `real` | Spawns `claude` subprocesses scoped to `builds/{task_id}/`. Requires Claude Code CLI on PATH. |
| `sandbox` | Builds the Docker container spec via `tools/security.py`. Wire-up to the Docker SDK is intentionally left out of this lightweight harness. |

## Katkıda Bulunma

Katkıda bulunmak isteyenler standart bir pull request süreci üzerinden projeye katkıda bulunabilirler.

## Lisans

Bu projeye ait lisans bilgileri burada yer alacaktır.