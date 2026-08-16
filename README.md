# AloSM Voice — AI Booking Assistant

Trợ lý đặt xe bằng giọng nói/tin nhắn cho AloSM: khách nói/nhắn nhu cầu → Agent AI
hiểu, thu thập điểm đón/đến, xác nhận → đặt xe hoặc chuyển tổng đài viên nếu cần.
Bắt đầu tại [`docs/PROJECT_SOURCE_OF_TRUTH.md`](docs/PROJECT_SOURCE_OF_TRUTH.md) để
biết nguồn dữ liệu nào có thẩm quyền, trạng thái thật của từng miền và trình tự hoàn
thiện. Tóm tắt sản phẩm nằm tại [`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md); yêu cầu chuẩn nằm tại [`docs/PRD_AloSM_Voice.md`](docs/PRD_AloSM_Voice.md).

## Kiến trúc tổng quan

```
Frontend (React/Vite)  --HTTP/WS-->  Backend (FastAPI)
                                        │
                        ┌───────────────┼──────────────────┐
                        │               │                  │
                   Agentic AI       Voice AI           Auth/Session/
                (src/agents/)     (src/voice/,        Booking/Trip
                LangGraph agent,   src/backend/       (src/backend/
                RAG, tools,        api/routes/         services/,
                guardrails         voice.py)           controllers/)
```

- **Backend**: FastAPI, entrypoint `src/main.py` → `src/backend/main.py`. Auth,
  token/2FA, session, settings, conversation, quote, booking, trip, handoff và call
  đã dùng repository PostgreSQL trong development/production. `APP_ENV=test` giữ
  adapter bộ nhớ cũ cho unit test lịch sử; xem [`docs/database_supabase.md`](docs/database_supabase.md).
- **Agentic AI** (`src/agents/`): LangGraph agent thật điều khiển hội thoại đặt xe
  (thay cho rule-engine đơn giản ban đầu) — xem `src/agents/README.md`.
- **Voice AI**: một pipeline kiểm duyệt dùng chung với ba transport: `/voice/turn`
  cho một lượt audio hoàn chỉnh, `/voice/speak` cho text→speech và `/voice/stream`
  cho WebSocket. Xem
  [`docs/voice-ai/voice-runtime-architecture.md`](docs/voice-ai/voice-runtime-architecture.md).
- **Frontend** (`src/frontend/`): React + Vite + Tailwind. Các route `/`, `/booking`,
  `/tracking`, `/activity`, `/payment`, `/profile` đã được đăng ký; `/assistant`
  mở popup Voice rồi redirect về `/`. Một số màn vẫn dùng catalog/UI demo và được
  phân loại rõ trong `docs/PROJECT_SOURCE_OF_TRUTH.md`.

## Chạy dự án

### Backend

```bash
cp .env.example .env   # điền GROQ_API_KEY / OPENAI_API_KEY / DATABASE_URL... theo nhu cầu
pip install -r requirements.txt
make run                # hoặc: uvicorn src.main:app --reload --port 8000
```

### Frontend

```bash
cd src/frontend
npm install
npm run dev
```

### Test / lint

```bash
make test        # pytest tests/ -v
make lint         # ruff check
cd src/frontend && npm run lint && npx tsc -b && npm run build
```

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
|---|---|
| `src/backend/` | FastAPI app: routes, controllers, services, schemas, DB layer |
| `src/agents/` | Agentic AI (LangGraph agent, RAG, tools, guardrails, workflows) |
| `src/voice/` | Voice runtime: audio/VAD, ASR, normalization, TTS và WebSocket gateway |
| `src/backend/schemas/`, `src/voice/schemas.py` | DTO HTTP và protocol Voice/WebSocket hiện hành |
| `src/frontend/` | React app (Vite) |
| `docs/` | Tài liệu dự án — xem bảng dưới |
| `mustdo.md` | Việc cần người thật làm (credential, tài khoản, quyết định sản phẩm) — không phải việc code được |
| `tests/` | Test (pytest cho backend/agents/voice) |
| `migrations/` | Alembic migration (Postgres/Supabase) |
| `examples/`, `demo/` | Script/demo độc lập, không phải production code |
| `scripts/` | Script hạ tầng (AI usage logging hooks — yêu cầu của khoá học) |

## Tài liệu (`docs/`)

| Thư mục | Nội dung |
|---|---|
| `docs/README.md`, `docs/PROJECT_SOURCE_OF_TRUTH.md` | Chỉ mục, trạng thái và trình tự hoàn thiện chuẩn |
| `docs/AI_LOGS.md` | Trạng thái kết nối, privacy redaction và runbook AI Logs |
| `docs/PRODUCT_BRIEF.md`, `docs/PRD_AloSM_Voice.md`, `docs/MVP.md` | Tóm tắt, yêu cầu chuẩn v1.2 và phạm vi MVP |
| `docs/architecture_diagram.md`, `docs/interface_design.md` | Kiến trúc runtime và HTTP/WS contract hiện hành |
| `docs/voice-ai/` | Voice runtime, local runbook, ASR/rewrite/TTS và evidence |
| `docs/database_supabase.md` | Thiết kế + hướng dẫn setup database Supabase |
| `docs/DOCUMENTATION_REMEDIATION_PROMPT.md` | Quy trình audit/làm sạch tài liệu có thể tái sử dụng |
| `docs/guide/`, `specification_documents/` | Tài liệu/template gốc của khoá học AI20K — không phải tài liệu riêng của project này, giữ nguyên để tham khảo |

## Ghi chú quan trọng

- **`mustdo.md`** liệt kê mọi việc cần thao tác thủ công (tạo tài khoản Supabase,
  Payment Gateway thật, v.v.) — luôn xem file này trước khi hỏi "sao chưa hoạt động".
- Runtime development/production đã dùng persistence và quote snapshot. Database live
  vẫn phải được migrate lên `9e9b6f420a9a` và chạy acceptance trước khi bỏ production gate;
  xem `docs/verification/database.md` và `mustdo.md`.
