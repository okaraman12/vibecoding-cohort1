"""Anthropic provider for the agent loop.

Exposes `call(history, tools, model)` returning an object that mimics the
shape `agent.py` reads from the OpenAI ChatCompletion response:

    msg.content     -> str | None
    msg.tool_calls  -> list[ToolCall] | None  (with .id, .function.name, .function.arguments)

That keeps `agent.py` provider-agnostic: history stays in OpenAI shape, and
this module converts at call time.

Auth resolution order:
  1. CLAUDE_CODE_OAUTH_TOKEN env  -> passed as Bearer (Claude Max OAuth path,
     unofficial but commonly works with the oauth-2025-04-20 beta header)
  2. ANTHROPIC_API_KEY env        -> standard x-api-key path
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Cache the resolved OAuth token in process memory only -- never written to
# disk, never logged. Re-read from Keychain if it expires.
_cached_oauth: str | None = None


def _read_keychain_oauth() -> str | None:
    """Pull the Claude Code OAuth access token from macOS Keychain.

    Token stays in memory only. Never printed, never persisted by this code.
    Returns None on any platform without the Keychain entry.
    """
    try:
        raw = subprocess.run(
            ["security", "find-generic-password",
             "-s", "Claude Code-credentials",
             "-a", os.environ.get("USER", ""),
             "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if raw.returncode != 0:
            return None
        data = json.loads(raw.stdout)
        return data.get("claudeAiOauth", {}).get("accessToken")
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def _resolve_oauth() -> str | None:
    global _cached_oauth
    if _cached_oauth:
        return _cached_oauth
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or _read_keychain_oauth()
    _cached_oauth = token
    return token


def _client():
    import anthropic  # lazy import so OpenAI-only users don't need it installed

    oauth = _resolve_oauth()
    if oauth:
        return anthropic.Anthropic(
            auth_token=oauth,
            default_headers={"anthropic-beta": "oauth-2025-04-20"},
        )
    return anthropic.Anthropic()  # falls back to ANTHROPIC_API_KEY


def _convert_tools(openai_tools: list[dict]) -> list[dict]:
    out = []
    for t in openai_tools:
        f = t["function"]
        out.append({
            "name": f["name"],
            "description": f["description"],
            "input_schema": f["parameters"],
        })
    return out


def _convert_messages(history: list[dict]) -> tuple[str, list[dict]]:
    """Return (system_prompt, anthropic_messages) from OpenAI-shaped history."""
    system = ""
    msgs: list[dict] = []

    for m in history:
        role = m["role"]

        if role == "system":
            system = m.get("content", "") or ""

        elif role == "user":
            msgs.append({"role": "user", "content": m["content"]})

        elif role == "assistant":
            blocks: list[dict] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                try:
                    inp = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    inp = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": inp,
                })
            if not blocks:
                blocks = [{"type": "text", "text": ""}]
            msgs.append({"role": "assistant", "content": blocks})

        elif role == "tool":
            msgs.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": m["content"],
                }],
            })

    return system, msgs


class _Func:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id: str, name: str, arguments: str):
        self.id = id
        self.type = "function"
        self.function = _Func(name, arguments)


class _Msg:
    def __init__(self, content: str | None, tool_calls: list[_ToolCall] | None):
        self.content = content
        self.tool_calls = tool_calls


def call(history: list[dict], tools: list[dict], model: str) -> _Msg:
    """One Anthropic Messages turn. Returns an OpenAI-shaped message object."""
    system, msgs = _convert_messages(history)
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": msgs,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = _convert_tools(tools)

    resp = _client().messages.create(**kwargs)

    text_parts: list[str] = []
    tool_calls: list[_ToolCall] = []
    for block in resp.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(block.text)
        elif btype == "tool_use":
            tool_calls.append(_ToolCall(
                id=block.id,
                name=block.name,
                arguments=json.dumps(block.input or {}, ensure_ascii=False),
            ))

    return _Msg(
        content="\n".join(text_parts) if text_parts else None,
        tool_calls=tool_calls or None,
    )
