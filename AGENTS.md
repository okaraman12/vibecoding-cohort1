# AGENTS.md — Repository Guidelines

## ZORUNLU KURAL: Bu Dosyaları Her Zaman Güncelle

**Her kod değişikliğinin ardından, commit yapmadan önce `CLAUDE.md` ve `AGENTS.md` dosyalarını güncellemelisin.**

Aşağıdaki durumlarda ilgili bölümleri güncelle:

| Değişiklik | Güncelle |
|---|---|
| Yeni modül / dosya eklendi | "Proje Yapısı" bölümü her iki dosyada |
| Yeni API endpoint'i | `CLAUDE.md` endpoint tablosu + bu dosyadaki routing bölümü |
| Yeni frontend sayfası | `CLAUDE.md` mimari tablosu + bu dosyadaki yapı bölümü |
| Yeni `pip` bağımlılığı | Bu dosyadaki bağımlılıklar bölümü |
| Yeni ortam değişkeni | Her iki dosyadaki ilgili notlar |

Bu dosyaları güncellemeden commit atmak yasaktır.

---

## Proje Yapısı

```
app.py                  # Flask uygulaması; routing, doğrulama, oturum yönetimi
llm.py                  # OpenAI istemcisi; hafızasız stream_llm() fonksiyonu
asistan.py              # Asistan sınıfı; conversation history + stream_sohbet()
agent.py                # Agent sınıfı; tool-calling agentic loop + calistir() generator
tools/
  __init__.py           # TOOL_DEFINITIONS / TOOL_FUNCTIONS — agent.py'a merge edilir
  car_picker.py         # pick_car: bütçe+amaç → sıralı araç adayları (JSON card)
  compare_specs.py      # compare_specs: iki model side-by-side
  estimate_ownership_cost.py  # 5-yıllık TCO; LLM yok, deterministik formül
  deploy_army.py        # Bonus: görev decomposition + rol atama + opsiyonel execution
  agent_runner.py       # Subprocess runner (simulation / real / sandbox modes)
  security.py           # Env allowlist + Docker container spec builder
  audit_log.py          # builds/audit.log JSONL append-only audit log
SECURITY.md             # Execution model, threat model, audit log şeması
builds/                 # Per-task çalışma dizinleri + audit.log (gitignore önerilir)
frontend/
  index.html            # LLM arayüzü: tek seferlik prompt/yanıt sayfası
  asistan.html          # Asistan arayüzü: çok turlu, baloncuklu sohbet sayfası
  agent.html            # Agent arayüzü: tool call'ları ve adımları görsel gösterim
requirements.txt        # Python bağımlılıkları
.env                    # Yerel sırlar (commit edilmez); OPENAI_API_KEY buraya
CLAUDE.md               # Claude Code'a mimari rehberlik
AGENTS.md               # Bu dosya; geliştirici ve ajan kuralları
```

Backend routing ve doğrulama `app.py`'de kalır. Provider'a özgü LLM çağrıları `llm.py`, `asistan.py` veya `agent.py`'de kalır. Statik dosyalar `frontend/` altına eklenir.

---

## API Endpoint'leri

| Method | Path | Body | Açıklama |
|---|---|---|---|
| POST | `/api/chat` | `{model, system_instructions, user_prompt}` | Hafızasız, tek seferlik LLM çağrısı (streaming, text/plain) |
| POST | `/api/asistan/yeni` | `{model, system_instructions}` | Yeni asistan oturumu oluşturur, `session_id` döner |
| POST | `/api/asistan/sohbet` | `{session_id, user_prompt}` | Asistana mesaj gönderir (streaming, text/plain) |
| POST | `/api/agent/yeni` | `{model, system_instructions}` | Yeni agent oturumu oluşturur, `session_id` döner |
| POST | `/api/agent/calistir` | `{session_id, user_prompt}` | Agent'ı çalıştırır (NDJSON stream; event tipleri: `step_start`, `thinking`, `tool_call`, `tool_result`, `text`, `done`, `error`) |

---

## Geliştirme Komutları

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug   # http://127.0.0.1:5000
```

---

## Kod Stili

- Python 3, 4 boşluk girinti, yeniden kullanılabilir yardımcılar için type hint.
- `stream_llm(...) -> Iterator[str]` ve `stream_sohbet(...) -> Iterator[str]` imzası örnek alınmalı.
- Hata mesajları API sınırını geçiyorsa kullanıcıya yönelik, provider hatası gizlenmeli.
- Frontend: sade HTML/CSS/JS, `camelCase` JS değişkenleri, amaca uygun `id` isimleri.

---

## Test Kılavuzu

Otomatik test suite mevcut değil. Test eklenecekse:

- `tests/` dizini oluştur, `pytest` kullan.
- Dosyaları `test_*.py` olarak adlandır.
- Öncelikli test alanları: Flask route doğrulama, `ALLOWED_MODELS` kontrolü, streaming hata yönetimi, asistan history doğruluğu.

```sh
pytest
```

Frontend değişikliklerinde tarayıcıda şunları manuel doğrula: boş prompt engelleme, model seçimi, streaming render, asistan history sürekliliği.

---

## Commit ve PR Kuralları

- Commit mesajları kısa ve imperative: `Add streaming assistant`, `Validate chat payload`.
- PR'lara: kısa özet, test notları, gerekli `.env` değişiklikleri, UI değişimi varsa ekran görüntüsü ekle.

---

## Güvenlik

- API anahtarları yalnızca `.env`'de; `python-dotenv` ile yükle. Commit etme.
- Log veya API yanıtında sır basmak yasak.
- `ALLOWED_MODELS` değiştiğinde `app.py` ve tüm frontend `<select>` elementleri birlikte güncellenmeli.
- `_asistanlar` dict'i sunucu hafızasında; production için kalıcı depolama gerekir.
