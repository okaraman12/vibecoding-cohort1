"""Specialized tools for the homework agent.

Tool pattern: each tool module exports `DEFINITION` (OpenAI function schema) and
a `run(**kwargs) -> str` callable. The aggregate dicts below are imported by
`agent.py` and merged into its `TOOLS` / `_TOOL_MAP`.
"""

from tools import deploy_army

TOOL_DEFINITIONS = [
    deploy_army.DEFINITION,
]

TOOL_FUNCTIONS = {
    "deploy_army": lambda a: deploy_army.run(**a),
}
