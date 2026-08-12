# AloSM Voice — AI Booking Assistant

Trợ lý đặt xe bằng giọng nói/tin nhắn cho AloSM: khách nói/nhắn nhu cầu → Agent AI
hiểu, thu thập điểm đón/đến, xác nhận → đặt xe hoặc chuyển tổng đài viên nếu cần.
Xem PRD đầy đủ tại [`docs/PRD_AloSM_Voice.md`](docs/PRD_AloSM_Voice.md).

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

- **Backend**: FastAPI, entrypoint `src/main.py` → `src/backend/main.py`. Domain
  services (auth, session, booking, trip, handoff, call) hiện lưu **in-memory**
  (dict cấp class) — xem [`mustdo.md`](mustdo.md) mục 5 cho lộ trình chuyển sang
  Postgres (Supabase) đã có sẵn hạ tầng tại `src/backend/db/`.
- **Agentic AI** (`src/agents/`): LangGraph agent thật điều khiển hội thoại đặt xe
  (thay cho rule-engine đơn giản ban đầu) — xem `src/agents/README.md`.
- **Voice AI**: hiện có **2 hệ thống song song**, xem
  [`docs/voice-ai/architecture-note-2-voice-systems.md`](docs/voice-ai/architecture-note-2-voice-systems.md)
  để biết cái nào frontend đang dùng thật và vì sao.
- **Frontend** (`src/frontend/`): React + Vite + Tailwind. Trang thật đang chạy:
  `/login` và `/` (chat/voice assistant) — các trang khác (`Booking`, `Tracking`,
  `Payment`, `Profile`, `Activity`, `Home`) hiện **không có route nào trỏ tới**.

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
| `src/voice/` | Voice AI engine (ASR/TTS provider, VAD, gazetteer, formatter) — 1 trong 2 hệ thống voice, xem ghi chú kiến trúc ở trên |
| `src/models/` | Schema dùng chung giữa Backend và Voice (WS protocol) |
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
| `docs/PRD_AloSM_Voice.md`, `docs/MVP.md`, `docs/BACKEND_TODOS_v3.md` | Yêu cầu sản phẩm, kế hoạch MVP |
| `docs/architecture_diagram.md`, `docs/interface_design.md` | Kiến trúc & thiết kế giao diện |
| `docs/voice-ai/` | Tài liệu Voice AI (thiết kế, TODO, dev local, ghi chú 2-hệ-thống) |
| `docs/database_supabase.md` | Thiết kế + hướng dẫn setup database Supabase |
| `docs/reports/` | Báo cáo tiến độ theo mốc thời gian (lịch sử, không phải tài liệu tham chiếu hiện hành) |
| `docs/guide/`, `specification_documents/` | Tài liệu/template gốc của khoá học AI20K — không phải tài liệu riêng của project này, giữ nguyên để tham khảo |

## Ghi chú quan trọng

- **`mustdo.md`** liệt kê mọi việc cần thao tác thủ công (tạo tài khoản Supabase,
  Payment Gateway thật, v.v.) — luôn xem file này trước khi hỏi "sao chưa hoạt động".
- Backend hiện là **in-memory MVP** (không phải bug) — dữ liệu mất khi restart server,
  cho tới khi các service được nối vào `src/backend/db/` (hạ tầng Postgres đã sẵn
  sàng, xem `docs/database_supabase.md`).
