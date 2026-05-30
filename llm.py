import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import Iterator

load_dotenv()

# Lazy: only construct the OpenAI client if a key is actually present, so the
# app can run in Claude-only mode without an OPENAI_API_KEY.
client = OpenAI() if os.environ.get("OPENAI_API_KEY") else None


def text_complete(system: str, user: str, openai_model: str = "gpt-4.1-mini",
                  claude_model: str = "claude-haiku-4-5",
                  temperature: float = 0.3) -> str:
    """Provider-agnostic one-shot text helper used by tools.

    Routes to OpenAI when OPENAI_API_KEY is configured, otherwise to Claude
    (via Keychain OAuth or ANTHROPIC_API_KEY).
    """
    if client is not None:
        resp = client.chat.completions.create(
            model=openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    import llm_anthropic
    return llm_anthropic.simple_text(system, user, model=claude_model, temperature=temperature)


def stream_llm(
    system_instructions: str,
    user_prompt: str,
    model: str = "gpt-4.1-mini",
) -> Iterator[str]:
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
