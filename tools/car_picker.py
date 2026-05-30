"""pick_car -- recommend ranked car candidates for a buyer's profile.

Uses the LLM to produce a strict-JSON recommendation card with 3-5 candidates,
category badges, fit scores, and tradeoff notes. The frontend renders this as
a comparison card (clone of the deploy_army plan card).
"""

from __future__ import annotations

import json
import re

from llm import text_complete

CATEGORIES = [
    "Daily Driver",
    "Family Hauler",
    "Performance",
    "Off-road",
    "EV / Hybrid",
    "Luxury",
    "Budget",
]

DEFINITION = {
    "type": "function",
    "function": {
        "name": "pick_car",
        "description": (
            "Recommend 3-5 ranked car candidates for a buyer's profile. Returns a "
            "structured JSON card with fit score (Strong/Good/Stretch), category "
            "badge (Daily Driver, Family Hauler, Performance, Off-road, EV/Hybrid, "
            "Luxury, Budget), pros, cons, approximate price, and tradeoff notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "budget":      {"type": "string", "description": "Budget range, e.g. '$25k-$35k' or 'under 800k TL'."},
                "use_case":    {"type": "string", "description": "Primary use: daily commute, family road trips, weekend off-road, track days, etc."},
                "must_haves":  {"type": "string", "description": "Hard requirements: AWD, 7 seats, manual, etc. Empty if none."},
                "preferences": {"type": "string", "description": "Soft preferences: brand, fuel type, body style, color, country of origin, etc."},
            },
            "required": ["budget", "use_case"],
        },
    },
}


_SYSTEM = (
    "You are a senior automotive advisor. Given a buyer's profile, return STRICT JSON "
    "(no prose outside JSON) with this shape:\n"
    "{\n"
    '  "summary": "<one-sentence buyer profile recap>",\n'
    '  "tradeoffs": "<short paragraph: depreciation, repair cost, insurance, resale>",\n'
    '  "candidates": [\n'
    '    {"rank": 1, "make": "<brand>", "model": "<model + year range>",\n'
    '     "category": "Daily Driver|Family Hauler|Performance|Off-road|EV / Hybrid|Luxury|Budget",\n'
    '     "fit": "Strong|Good|Stretch",\n'
    '     "price_estimate": "<approx price range in user\'s currency>",\n'
    '     "pros": ["<bullet>", ...], "cons": ["<bullet>", ...],\n'
    '     "why": "<1-2 sentences on why this fits>"}\n'
    "  ]\n"
    "}\n"
    "Use 3-5 candidates. Use exact category strings. Rank 1 = best match. Be realistic."
)


def _coerce(raw: str, budget: str, use_case: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    plan = {}
    if m:
        try:
            plan = json.loads(m.group(0))
        except json.JSONDecodeError:
            plan = {}

    plan.setdefault("summary", f"Buyer wants a vehicle for {use_case} within {budget}.")
    plan.setdefault("tradeoffs", "No tradeoff notes provided.")
    cands = plan.get("candidates") or []
    cleaned = []
    for i, c in enumerate(cands, start=1):
        if not isinstance(c, dict):
            continue
        cat = c.get("category") if c.get("category") in CATEGORIES else CATEGORIES[0]
        fit = c.get("fit") if c.get("fit") in {"Strong", "Good", "Stretch"} else "Good"
        cleaned.append({
            "rank": c.get("rank") or i,
            "make": c.get("make") or "Unknown",
            "model": c.get("model") or "Unknown",
            "category": cat,
            "fit": fit,
            "price_estimate": c.get("price_estimate") or "—",
            "pros": [str(p) for p in (c.get("pros") or [])][:5],
            "cons": [str(p) for p in (c.get("cons") or [])][:5],
            "why": c.get("why") or "",
        })
    if not cleaned:
        cleaned = [{
            "rank": 1, "make": "—", "model": "No candidates generated",
            "category": "Daily Driver", "fit": "Good", "price_estimate": "—",
            "pros": [], "cons": [], "why": "Planner returned no candidates.",
        }]
    plan["candidates"] = cleaned
    return plan


def run(budget: str, use_case: str, must_haves: str = "", preferences: str = "") -> str:
    profile = (
        f"Budget: {budget}\n"
        f"Primary use: {use_case}\n"
        f"Must-haves: {must_haves or '(none)'}\n"
        f"Preferences: {preferences or '(none)'}"
    )
    raw = text_complete(_SYSTEM, profile, temperature=0.4)
    plan = _coerce(raw, budget, use_case)
    plan["profile"] = {
        "budget": budget, "use_case": use_case,
        "must_haves": must_haves, "preferences": preferences,
    }
    return json.dumps(plan, ensure_ascii=False, indent=2)
