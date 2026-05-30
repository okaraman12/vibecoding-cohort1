import json
import os
import subprocess
from typing import Iterator

from llm import client
import llm_anthropic
from tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

AGENT_WORKSPACE = "/tmp/agent_workspace"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": (
                "Terminalde bir shell komutu çalıştırır ve çıktısını döner. "
                f"Çalışma dizini: {AGENT_WORKSPACE}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Çalıştırılacak shell komutu"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dosya_oku",
            "description": "Bir dosyanın içeriğini okur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "yol": {"type": "string", "description": "Dosya yolu"},
                },
                "required": ["yol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dosya_yaz",
            "description": "Bir dosyaya içerik yazar; dosya yoksa oluşturur, varsa üzerine yazar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "yol": {"type": "string", "description": "Dosya yolu"},
                    "icerik": {"type": "string", "description": "Dosyaya yazılacak içerik"},
                },
                "required": ["yol", "icerik"],
            },
        },
    },
]


def _terminal(command: str) -> str:
    os.makedirs(AGENT_WORKSPACE, exist_ok=True)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=AGENT_WORKSPACE,
        )
        output = (result.stdout + result.stderr).strip()
        return output or "(komut çıktı üretmedi)"
    except subprocess.TimeoutExpired:
        return "Hata: Komut 30 saniyede tamamlanamadı."
    except Exception as e:
        return f"Hata: {e}"


def _dosya_oku(yol: str) -> str:
    try:
        with open(yol, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Hata: {e}"


def _dosya_yaz(yol: str, icerik: str) -> str:
    try:
        dizin = os.path.dirname(yol)
        if dizin:
            os.makedirs(dizin, exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            f.write(icerik)
        return f"Başarıyla yazıldı: {yol}"
    except Exception as e:
        return f"Hata: {e}"


_TOOL_MAP = {
    "terminal": lambda a: _terminal(a["command"]),
    "dosya_oku": lambda a: _dosya_oku(a["yol"]),
    "dosya_yaz": lambda a: _dosya_yaz(a["yol"], a["icerik"]),
    **TOOL_FUNCTIONS,
}

# Merge specialized tool definitions (deploy_army, ...) into the schema list.
TOOLS.extend(TOOL_DEFINITIONS)


class Agent:
    """
    Tool-calling agentic loop. Her turda modeli çağırır; model tool istiyorsa
    çalıştırır ve history'ye ekleyerek döngüye devam eder. Model düz metin
    yanıt verince loop sona erer.

    calistir() bir Generator'dür ve her olay için bir dict yield eder:
      {"type": "step_start", "step": int}
      {"type": "thinking",   "content": str}   — tool call öncesi model metni
      {"type": "tool_call",  "name": str, "args": dict}
      {"type": "tool_result","name": str, "result": str}
      {"type": "text",       "content": str}   — son yanıt
      {"type": "done"}
    """

    def __init__(self, system_instructions: str, model: str = "gpt-4.1-mini"):
        self.model = model
        self.history: list[dict] = [
            {"role": "system", "content": system_instructions}
        ]

    def calistir(self, user_prompt: str) -> Iterator[dict]:
        self.history.append({"role": "user", "content": user_prompt})
        step = 0

        while True:
            step += 1
            yield {"type": "step_start", "step": step}

            if self.model.startswith("claude-"):
                msg = llm_anthropic.call(self.history, TOOLS, self.model)
            else:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=self.history,
                    tools=TOOLS,
                    tool_choice="auto",
                )
                msg = response.choices[0].message

            # History'e eklenecek asistan mesajı
            history_msg: dict = {"role": "assistant"}
            if msg.content:
                history_msg["content"] = msg.content
            if msg.tool_calls:
                history_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            self.history.append(history_msg)

            if msg.content:
                # Tool call varsa bu metin "düşünme" sürecini yansıtır
                kind = "thinking" if msg.tool_calls else "text"
                yield {"type": kind, "content": msg.content}

            if not msg.tool_calls:
                yield {"type": "done"}
                return

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                yield {"type": "tool_call", "name": name, "args": args}

                fn = _TOOL_MAP.get(name)
                result = fn(args) if fn else f"Bilinmeyen araç: {name}"

                yield {"type": "tool_result", "name": name, "result": result}

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
