import json
import uuid
from flask import Flask, Response, request, send_from_directory, stream_with_context
from llm import stream_llm
from asistan import Asistan
from agent import Agent

app = Flask(__name__, static_folder="frontend")

ALLOWED_MODELS = {
    # OpenAI
    "gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini",
    # Anthropic (routed in agent.py when prefix == "claude-")
    "claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5",
    "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest",
}

# Aktif asistan oturumları: session_id -> Asistan nesnesi
_asistanlar: dict[str, Asistan] = {}

# Aktif agent oturumları: session_id -> Agent nesnesi
_agentlar: dict[str, Agent] = {}


@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    system_instructions = data.get("system_instructions", "")
    user_prompt = data.get("user_prompt", "").strip()
    model = data.get("model", "gpt-4.1-mini")

    if not user_prompt:
        return {"error": "user_prompt bos olamaz"}, 400

    if model not in ALLOWED_MODELS:
        return {"error": "Gecersiz model"}, 400

    def generate():
        try:
            yield from stream_llm(system_instructions, user_prompt, model)
        except Exception:
            yield "\n[HATA: Model yaniti alinirken bir sorun olustu.]"

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain",
    )


@app.route("/asistan")
def asistan_sayfasi():
    return send_from_directory("frontend", "asistan.html")


@app.route("/api/asistan/yeni", methods=["POST"])
def asistan_yeni():
    data = request.get_json(silent=True) or {}
    system_instructions = data.get("system_instructions", "Sen yardımsever bir asistansın.")
    model = data.get("model", "gpt-4.1-mini")

    if model not in ALLOWED_MODELS:
        return {"error": "Geçersiz model"}, 400

    session_id = str(uuid.uuid4())
    _asistanlar[session_id] = Asistan(system_instructions, model)
    return {"session_id": session_id}


@app.route("/api/asistan/sohbet", methods=["POST"])
def asistan_sohbet():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    user_prompt = data.get("user_prompt", "").strip()

    if not user_prompt:
        return {"error": "user_prompt boş olamaz"}, 400

    if session_id not in _asistanlar:
        return {"error": "Geçersiz veya süresi dolmuş oturum"}, 404

    asistan = _asistanlar[session_id]

    def generate():
        try:
            yield from asistan.stream_sohbet(user_prompt)
        except Exception:
            yield "\n[HATA: Yanıt alınırken bir sorun oluştu.]"

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain",
    )


@app.route("/agent")
def agent_sayfasi():
    return send_from_directory("frontend", "agent.html")


@app.route("/api/agent/yeni", methods=["POST"])
def agent_yeni():
    data = request.get_json(silent=True) or {}
    system_instructions = data.get(
        "system_instructions",
        "Sen bir kodlama agentisin. Görevleri tamamlamak için araçlarını kullan.",
    )
    model = data.get("model", "gpt-4.1-mini")

    if model not in ALLOWED_MODELS:
        return {"error": "Geçersiz model"}, 400

    session_id = str(uuid.uuid4())
    _agentlar[session_id] = Agent(system_instructions, model)
    return {"session_id": session_id}


@app.route("/api/agent/calistir", methods=["POST"])
def agent_calistir():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    user_prompt = data.get("user_prompt", "").strip()

    if not user_prompt:
        return {"error": "user_prompt boş olamaz"}, 400

    if session_id not in _agentlar:
        return {"error": "Geçersiz veya süresi dolmuş oturum"}, 404

    ag = _agentlar[session_id]

    def generate():
        try:
            for event in ag.calistir(user_prompt):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
    )


if __name__ == "__main__":
    app.run(debug=True)
