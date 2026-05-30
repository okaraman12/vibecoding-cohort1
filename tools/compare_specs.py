"""compare_specs -- side-by-side spec comparison of two car models."""

from __future__ import annotations

import json
import re

from llm import text_complete

DEFINITION = {
    "type": "function",
    "function": {
        "name": "compare_specs",
        "description": (
            "Compare two car models side-by-side across key specs (engine, "
            "horsepower, mpg/L/100km, 0-60, cargo, seats, safety rating, MSRP). "
            "Returns structured JSON for tabular rendering."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_a": {"type": "string", "description": "First model (e.g. 'Toyota RAV4 2024')."},
                "model_b": {"type": "string", "description": "Second model (e.g. 'Honda CR-V 2024')."},
            },
            "required": ["model_a", "model_b"],
        },
    },
}

_SYSTEM = (
    "You are an automotive spec analyst. Return STRICT JSON (no prose) with shape:\n"
    "{\n"
    '  "model_a": "<name>", "model_b": "<name>",\n'
    '  "verdict": "<1-sentence summary of which wins for whom>",\n'
    '  "rows": [\n'
    '    {"spec": "Engine", "a": "<value>", "b": "<value>", "winner": "a|b|tie"},\n'
    '    {"spec": "Horsepower", ...},\n'
    "    ...\n"
    "  ]\n"
    "}\n"
    "Include at minimum: Engine, Horsepower, Torque, Fuel Economy, 0-60 mph (or 0-100 km/h), "
    "Cargo Volume, Seating, Safety Rating, Base Price. Use realistic figures."
)


def _coerce(raw: str, a: str, b: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    data = {}
    if m:
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            data = {}
    data.setdefault("model_a", a)
    data.setdefault("model_b", b)
    data.setdefault("verdict", "No verdict generated.")
    rows = data.get("rows") or []
    cleaned = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        winner = r.get("winner") if r.get("winner") in {"a", "b", "tie"} else "tie"
        cleaned.append({
            "spec": str(r.get("spec") or "—"),
            "a": str(r.get("a") or "—"),
            "b": str(r.get("b") or "—"),
            "winner": winner,
        })
    data["rows"] = cleaned
    return data


def run(model_a: str, model_b: str) -> str:
    raw = text_complete(_SYSTEM, f"Compare {model_a} vs {model_b}.", temperature=0.2)
    return json.dumps(_coerce(raw, model_a, model_b), ensure_ascii=False, indent=2)
