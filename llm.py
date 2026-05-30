import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import Iterator

load_dotenv()

# Lazy: only construct the OpenAI client if a key is actually present, so the
# app can run in Claude-only mode without an OPENAI_API_KEY.
client = OpenAI() if os.environ.get("OPENAI_API_KEY") else None


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
