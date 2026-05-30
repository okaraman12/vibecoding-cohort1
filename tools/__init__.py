"""Specialized tools for the homework agent.

Tool pattern: each tool module exports `DEFINITION` (OpenAI function schema)
and a `run(**kwargs) -> str` callable. The aggregate dicts below are imported
by `agent.py` and merged into its `TOOLS` / `_TOOL_MAP`.
"""

from tools import car_picker, compare_specs, deploy_army, estimate_ownership_cost

TOOL_DEFINITIONS = [
    car_picker.DEFINITION,
    compare_specs.DEFINITION,
    estimate_ownership_cost.DEFINITION,
    # Bonus: meta-agent tool kept from the original build.
    deploy_army.DEFINITION,
]

TOOL_FUNCTIONS = {
    "pick_car":                lambda a: car_picker.run(**a),
    "compare_specs":           lambda a: compare_specs.run(**a),
    "estimate_ownership_cost": lambda a: estimate_ownership_cost.run(**a),
    "deploy_army":             lambda a: deploy_army.run(**a),
}
