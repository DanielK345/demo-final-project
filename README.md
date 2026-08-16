# AloSM AI Booking Assistant

Web MVP đặt xe bằng **text hoặc voice**. Phạm vi chính gồm Login/Auth và Homepage với AloSM Assistant; chưa gồm live tracking, trip history, payment hoặc wallet.

Kiến trúc: [`docs/MVP_ARCHITECTURE.md`](docs/MVP_ARCHITECTURE.md) · Runtime truth: [`docs/PROJECT_SOURCE_OF_TRUTH.md`](docs/PROJECT_SOURCE_OF_TRUTH.md)

## 1. Setup

Yêu cầu: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js/npm và FFmpeg/FFprobe.

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head

cd src/frontend
npm ci
```

Chạy hai terminal:

```bash
# Terminal 1 — backend: http://localhost:8000
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend: http://localhost:5173
cd src/frontend
npm run dev
```

Demo account local:

```text
Phone:    0901234567
Password: Password123!
```

## 2. Environment variables

Copy `.env.example` thành `.env`; không commit secret.

| Biến | Khi nào cần | Giá trị/vai trò |
|---|---|---|
| `APP_ENV` | Luôn có | `development`, `test` hoặc `production` |
| `DATABASE_URL` | Luôn có | SQLite local hoặc PostgreSQL runtime URL |
| `DATABASE_URL_MIGRATIONS` | Supabase/PostgreSQL | Connection riêng cho Alembic |
| `AGENT_LLM_ENABLED` | Chat/booking qua LLM | `true` |
| `AGENT_LLM_MODEL` | Chat/booking qua LLM | Model hỗ trợ tool calling |
| `AGENT_LLM_BASE_URL` | LLM | OpenAI endpoint hoặc OpenRouter endpoint |
| `OPENAI_API_KEY` | OpenAI Agent/STT/TTS | Không thay thế bằng OpenRouter key cho Speech API |
| `OPENROUTER_API_KEY` | LLM/rewrite qua OpenRouter | Chỉ dùng với `openrouter.ai` base URL |
| `VOICE_PROVIDER` | Voice REST | `auto`, `zipformer`, `openai` hoặc `gemini` |
| `VOICE_TRANSCRIPT_REWRITE_ENABLED` | Sửa transcript | `true` để bật contextual rewrite |
| `VOICE_TTS_PROVIDER` | Voice output | `openai` hoặc `edge` |
| `GROQ_API_KEY` | WebSocket ASR fallback | Groq Whisper |
| `GEMINI_API_KEY` | Gemini ASR | Chỉ cần khi chọn Gemini |
| `QUOTE_SIGNING_KEY` | Durable quote | Secret tối thiểu 32 ký tự |
| `FIELD_ENCRYPTION_KEY` | 2FA fields | Secret tối thiểu 32 ký tự |
| `VITE_API_URL` | Frontend deploy khác origin | Mặc định `http://localhost:8000` |

### OpenRouter cho Agent và rewrite

```env
OPENROUTER_API_KEY=...
AGENT_LLM_ENABLED=true
AGENT_LLM_BASE_URL=https://openrouter.ai/api/v1
AGENT_LLM_MODEL=openai/gpt-5.6-luna-pro
VOICE_TRANSCRIPT_REWRITE_ENABLED=true
VOICE_TRANSCRIPT_REWRITE_BASE_URL=https://openrouter.ai/api/v1
VOICE_TRANSCRIPT_REWRITE_MODEL=openai/gpt-5.6-luna-pro
```

### OpenAI trực tiếp và Voice REST

```env
OPENAI_API_KEY=...
AGENT_LLM_BASE_URL=https://api.openai.com/v1
AGENT_LLM_MODEL=<OPENAI_MODEL_SUPPORTING_TOOL_CALLS>
VOICE_PROVIDER=openai
VOICE_STT_MODEL=gpt-4o-transcribe
VOICE_STT_FALLBACK_MODEL=whisper-1
VOICE_TTS_PROVIDER=openai
VOICE_TTS_MODEL=tts-1
VOICE_OPENAI_TTS_VOICE=nova
```

### Database

Local không cần Supabase:

```env
DATABASE_URL=sqlite:///./data/app.db
```

Với Supabase, project này dùng transaction pooler cho app và direct/session connection cho migration:

```env
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<PASSWORD>@<POOLER_HOST>:6543/postgres
DATABASE_URL_MIGRATIONS=postgresql://postgres:<PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres
```

Direct connection thường cần IPv6; lấy đúng URL từ nút **Connect** trong Supabase Dashboard. Không đưa database password hoặc service-role key vào frontend. Chi tiết: [`docs/database_supabase.md`](docs/database_supabase.md) và [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

Tạo hai application secrets độc lập:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. Sample queries

Happy path Hà Nội hiện yêu cầu chọn candidate cụ thể cho VinUni và Hồ Gươm:

```text
User: Cho tôi xe 4 chỗ từ VinUni tới Hồ Gươm.
User: Tôi chọn Cổng chính VinUni.
User: Tôi chọn Bưu điện Hà Nội.
User: Đúng, tôi xác nhận đặt chuyến này.
```

Các câu thử Voice rewrite:

```text
Đón tôi ở Bình Yuni rồi đi Hồ Cương.
Tôi chọn cổng thành cũng.       # khi Agent đang hỏi cổng VinUni
Không, tôi muốn sửa điểm đến.
```

API examples:

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"phone":"0901234567","password":"Password123!"}'

# Text turn
curl -X POST http://localhost:8000/api/v1/sessions/<SESSION_ID>/messages \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"message":"Cho tôi xe 4 chỗ từ VinUni tới Hồ Gươm","source":"TEXT"}'

# Voice turn
curl -X POST http://localhost:8000/api/v1/voice/turn \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -F 'session_id=<SESSION_ID>' \
  -F 'audio=@sample.webm;type=audio/webm'
```

## 4. Tests và eval evidence

```bash
# Full backend/agent/voice suite
uv run pytest -q
uv run ruff check src tests eval_cases

# Frontend
cd src/frontend
npm run lint
npm run build
```

Chạy 7 MVP eval cases offline và selected regression tests:

```bash
uv run python -m eval_cases.run_mvp_evals
```

Kết quả tổng hợp nằm tại [`eval_cases/mvp_eval_results.json`](eval_cases/mvp_eval_results.json); input, expected và actual output của từng case nằm trong [`eval_cases/results/`](eval_cases/results/). Xem [`eval_cases/README.md`](eval_cases/README.md) để đọc schema và tái chạy evidence.

Các eval dùng deterministic adapters, không gọi provider thật và không cần API key. Live provider checks nằm trong [`docs/voice-ai/`](docs/voice-ai/README.md).

## 5. Project layout

| Thư mục | Nội dung |
|---|---|
| `src/frontend/` | React Login, Homepage và Assistant popup |
| `src/backend/` | FastAPI routes, services, repositories và provider adapters |
| `src/agents/` | Core Agent model/tool loop, typed state và guardrails |
| `src/voice/` | ASR, VAD, transcript processing và TTS |
| `migrations/` | Alembic migrations |
| `data/gazetteer/` | Hà Nội places, ASR aliases và landmark candidates |
| `eval_cases/` | Reproducible MVP evaluation và JSON evidence |
| `docs/` | Architecture, runtime contracts và operations guides |
