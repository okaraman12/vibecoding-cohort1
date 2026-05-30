"""deploy_army -- decompose a task and assign it to specialized AI agents.

Returns a structured deployment plan: mission summary, subtask breakdown,
role assignments, complexity per subtask, risk assessment, and strategic
dependencies. When EXECUTION_MODE != "simulation" each subtask is actually
executed via tools.agent_runner; otherwise the plan is returned alone.
"""

from __future__ import annotations

import json
import os
import re
import uuid

from llm import text_complete
from tools import agent_runner

ROLES = [
    "Lead Architect",
    "Senior Engineer",
    "Code Reviewer",
    "Security Analyst",
    "QA Specialist",
]

DEFINITION = {
    "type": "function",
    "function": {
        "name": "deploy_army",
        "description": (
            "Analyze a task description, decompose it into subtasks, and produce a "
            "professional deployment plan with role assignments (Lead Architect, "
            "Senior Engineer, Code Reviewer, Security Analyst, QA Specialist), "
            "complexity ratings, risk assessment, and dependency graph. Returns a "
            "structured JSON deployment plan. When EXECUTION_MODE is 'real', also "
            "spawns Claude Code subprocesses to execute each subtask."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "High-level task description to decompose and deploy.",
                },
                "execute": {
                    "type": "boolean",
                    "description": "If true, execute subtasks via the agent runner. Defaults to false (plan only).",
                },
            },
            "required": ["task"],
        },
    },
}


_DECOMP_SYSTEM = (
    "You are a senior engineering planner. Given a task, produce a strict JSON "
    "deployment plan with this shape (no prose outside JSON):\n"
    "{\n"
    '  "mission_summary": "<1-2 sentence summary>",\n'
    '  "risk_assessment": "<short paragraph naming concrete risks>",\n'
    '  "subtasks": [\n'
    '    {"id": "T1", "role": "Lead Architect|Senior Engineer|Code Reviewer|Security Analyst|QA Specialist",\n'
    '     "title": "<short>", "description": "<actionable detail>",\n'
    '     "complexity": "Low|Medium|High", "depends_on": ["T0", ...]}\n'
    "  ]\n"
    "}\n"
    "Use 3-6 subtasks. Every role in the list above must appear at least once if the task warrants it. "
    "Order subtasks so dependencies are satisfiable. Use exact role strings."
)


def _coerce_plan(task: str, raw: str) -> dict:
    """Parse the LLM response into a plan dict, with sturdy fallbacks."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            plan = json.loads(m.group(0))
        except json.JSONDecodeError:
            plan = {}
    else:
        plan = {}

    plan.setdefault("mission_summary", task.strip()[:200])
    plan.setdefault("risk_assessment", "No explicit risks identified by planner.")
    subtasks = plan.get("subtasks") or []
    # Sanitize roles and required fields.
    cleaned = []
    for i, st in enumerate(subtasks, start=1):
        role = st.get("role") if isinstance(st, dict) else None
        if role not in ROLES:
            role = ROLES[(i - 1) % len(ROLES)]
        cleaned.append({
            "id": st.get("id") or f"T{i}",
            "role": role,
            "title": st.get("title") or f"Subtask {i}",
            "description": st.get("description") or "",
            "complexity": st.get("complexity") if st.get("complexity") in {"Low", "Medium", "High"} else "Medium",
            "depends_on": [d for d in (st.get("depends_on") or []) if isinstance(d, str)],
        })
    if not cleaned:
        cleaned = [{
            "id": "T1", "role": "Lead Architect", "title": "Define approach",
            "description": task, "complexity": "Medium", "depends_on": [],
        }]
    plan["subtasks"] = cleaned
    return plan


def _decompose(task: str) -> dict:
    return _coerce_plan(task, text_complete(_DECOMP_SYSTEM, task, temperature=0.2))


def run(task: str, execute: bool = False) -> str:
    task = (task or "").strip()
    if not task:
        return json.dumps({"error": "task is required"}, ensure_ascii=False)

    task_id = uuid.uuid4().hex[:8]
    plan = _decompose(task)
    plan["task_id"] = task_id
    plan["execution_mode"] = agent_runner.EXECUTION_MODE
    plan["execute"] = bool(execute)

    if execute:
        results = []
        for st in plan["subtasks"]:
            res = agent_runner.execute_subtask(
                task_id=task_id,
                role=st["role"],
                description=f"{st['title']}\n\n{st['description']}",
            )
            results.append({"subtask_id": st["id"], **res})
        plan["execution_results"] = results

    return json.dumps(plan, ensure_ascii=False, indent=2)
