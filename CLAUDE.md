# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ZORUNLU KURAL: Bu Dosyaları Her Zaman Güncelle

**Her kod değişikliğinin ardından, commit yapmadan önce `CLAUDE.md` ve `AGENTS.md` dosyalarını güncellemelisin.**

Güncelleme gerektiren durumlar:
- Yeni dosya veya modül eklenmesi
- Yeni API endpoint'i eklenmesi veya kaldırılması
- Yeni frontend sayfası eklenmesi
- Mevcut bir modülün sorumluluğunun değişmesi
- Yeni bağımlılık veya ortam değişkeni eklenmesi

Güncelleme yapmazsan mimari bilgisi eskir ve gelecekteki Claude oturumları yanlış varsayımlarla çalışır.

---

## Geliştirme Ortamı

```bash
# Sanal ortamı aktifleştir
source .venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı çalıştır (http://localhost:5000)
flask --app app run --debug
```

`.env` dosyasında `OPENAI_API_KEY` tanımlı olmalıdır.

---

## Mimari

Flask backend + vanilla JS frontend. Üç ayrı sayfa sunar:

| Sayfa | URL | Açıklama |
|---|---|---|
| LLM Arayüzü | `/` | Tek seferlik, hafızasız LLM çağrısı |
| Asistan | `/asistan` | Conversation history tutan sohbet arayüzü |
| Araç Seçici | `/agent` | Tool-calling agent — car advisor (pick_car, compare_specs, estimate_ownership_cost, +deploy_army bonus) |

### Dosya Sorumlulukları

- **`app.py`** — Flask uygulaması. Routing, model doğrulaması, asistan ve agent oturum yönetimi.
- **`llm.py`** — OpenAI istemcisi kurulumu ve `stream_llm()` fonksiyonu. Tek seferlik, history'siz.
- **`asistan.py`** — `Asistan` sınıfı. Conversation history tutan, `sohbet()` ve `stream_sohbet()` metodları.
- **`agent.py`** — `Agent` sınıfı. Tool-calling agentic loop; `calistir()` generator'ı her adımda event dict'i yield eder. Tool'lar: `terminal`, `dosya_oku`, `dosya_yaz`, ve `tools/` paketinden gelen `deploy_army`.
- **`tools/__init__.py`** — Özel araç paketi. `TOOL_DEFINITIONS` ve `TOOL_FUNCTIONS` sözlüklerini dışa açar; `agent.py` bunları `TOOLS` / `_TOOL_MAP`'e merge eder.
- **`tools/car_picker.py`** — `pick_car`: bütçe + kullanım amacı + tercihler → 3-5 sıralı araç adayı (kategori badge, fit skoru, artı/eksi, fiyat tahmini). LLM ile JSON üretir, regex + coercion ile temizlenir.
- **`tools/compare_specs.py`** — `compare_specs`: iki modeli yan yana karşılaştırır (motor, beygir, yakıt, 0-100, kargo, koltuk, güvenlik, MSRP) + per-row winner.
- **`tools/estimate_ownership_cost.py`** — `estimate_ownership_cost`: deterministik 5 yıllık TCO hesabı (amortisman, yakıt, sigorta, bakım). LLM çağrısı yok, kategori-bazlı heuristic tablodan formül.
- **`tools/deploy_army.py`** — Bonus tool: bir görevi alt görevlere ayırır, rol atar (Lead Architect, Senior Engineer, Code Reviewer, Security Analyst, QA Specialist), karmaşıklık ve risk değerlendirmesi içeren JSON deployment plan döner. `execute=true` ise `agent_runner` üzerinden alt görevleri gerçekten çalıştırır.
- **`tools/agent_runner.py`** — Agent Army'den uyarlanmış subprocess runner. `EXECUTION_MODE` ortam değişkenine göre `simulation` (default, güvenli), `real` (Claude Code CLI'yi `builds/{task_id}/` cwd'de çalıştırır) veya `sandbox` (Docker container spec) modunda çalışır.
- **`tools/security.py`** — Env allowlist + Docker container spec builder (read-only root, `--network=none`, mem/cpu/PID limit). `sandbox` mode için hazır; Docker SDK çağrısı bu harness'ta kasıtlı olarak bağlanmadı.
- **`tools/audit_log.py`** — `builds/audit.log` dosyasına JSONL append. Her execution için: rol, mode, env key **adları** (değerleri asla), süre, exit code, status.
- **`SECURITY.md`** — Execution model dokümantasyonu, threat model, audit log şeması.
- **`frontend/index.html`** — LLM arayüzü. Tek prompt → tek yanıt.
- **`frontend/asistan.html`** — Sohbet arayüzü. Baloncuklu, çok turlu, session tabanlı.
- **`frontend/agent.html`** — Agent arayüzü. Her adımı, tool call'ları, sonuçlarını ve thinking text'ini görsel olarak gösterir.

### LLM Arayüzü Veri Akışı

1. `frontend/index.html` → `POST /api/chat` (model, system_instructions, user_prompt)
2. `app.py` → `stream_llm()` çağrısı
3. `llm.py` → OpenAI Streaming API → chunk'lar `text/plain` olarak istemciye aktarılır
4. Frontend `ReadableStream` ile chunk'ları okur, `#response` div'ine ekler

### Asistan Veri Akışı

1. `frontend/asistan.html` → `POST /api/asistan/yeni` (model, system_instructions) → `session_id` döner
2. `frontend/asistan.html` → `POST /api/asistan/sohbet` (session_id, user_prompt)
3. `app.py` → `_asistanlar[session_id].stream_sohbet()` çağrısı
4. `asistan.py` → OpenAI Streaming API → chunk yield eder, bitince history'ye ekler
5. Frontend chunk'ları asistan balonuna akıtır

### Agent Veri Akışı

1. `frontend/agent.html` → `POST /api/agent/yeni` (model, system_instructions) → `session_id` döner
2. `frontend/agent.html` → `POST /api/agent/calistir` (session_id, user_prompt)
3. `app.py` → `_agentlar[session_id].calistir()` generator'ını iter eder
4. `agent.py` → OpenAI tool-calling API → her event için JSON satırı yield eder (NDJSON)
5. Frontend NDJSON satırlarını parse eder; event tipine göre (`step_start`, `thinking`, `tool_call`, `tool_result`, `text`, `done`) görsel bloklar oluşturur

### API Endpoint'leri

| Method | Path | Açıklama |
|---|---|---|
| POST | `/api/chat` | Tek seferlik LLM çağrısı (streaming, text/plain) |
| POST | `/api/asistan/yeni` | Yeni asistan oturumu oluştur |
| POST | `/api/asistan/sohbet` | Asistana mesaj gönder (streaming, text/plain) |
| POST | `/api/agent/yeni` | Yeni agent oturumu oluştur |
| POST | `/api/agent/calistir` | Agent'ı çalıştır (NDJSON stream) |

### Kritik Noktalar

- Model doğrulaması `app.py`'deki `ALLOWED_MODELS` set'i üzerinden yapılır; yeni model eklendiğinde hem burası hem `index.html`, `asistan.html` ve `agent.html` içindeki `<select>` güncellenmeli.
- `llm.py` modül yüklendiğinde `client = OpenAI()` oluşturulur; `OPENAI_API_KEY` `.env`'de yoksa uygulama başlamaz.
- `_asistanlar` ve `_agentlar` dict'leri sunucu hafızasındadır; sunucu yeniden başlatılınca tüm oturumlar sıfırlanır.
- Asistan yanıtları `text/plain`, agent yanıtları `application/x-ndjson` olarak stream edilir.
- Agent terminal tool'u `/tmp/agent_workspace` dizininde çalışır; `shell=True` ile arbitrary komut çalıştırır (eğitim ortamı, localhost).
- Agent `thinking` event'i: model tool çağrısından önce metin üretirse bu `thinking` olarak işaretlenir; son yanıt `text` olarak işaretlenir.
