# Backend

FastAPI application layer của AloSM Voice. Nguồn điều phối chung:
[`docs/PROJECT_SOURCE_OF_TRUTH.md`](../../docs/PROJECT_SOURCE_OF_TRUTH.md).

## Trách nhiệm

- Xác thực, 2FA và settings API.
- Session lifecycle, typed turn, feedback và history.
- Thực thi tool/side effect do Core Agent yêu cầu.
- Booking idempotency, trip lookup và handoff lifecycle.
- LiveKit token/connection details và business state cho voice worker.
- Health/readiness và observability hooks.

Core Agent không thuộc Backend và không thực thi I/O; contract integration nằm tại
`src/agents/docs/BACKEND_INTEGRATION.md`.

## Entrypoint và route ownership

App nằm tại `src/backend/main.py`, được export qua `src/main.py`. Router nghiệp vụ
được mount dưới `/api/v1`. Voice realtime đi qua LiveKit Room; FastAPI chỉ cấp
connection details và xử lý business/persistence.

Nhóm API chính:

- `/api/v1/auth/*`
- `/api/v1/sessions/*`
- `/api/v1/bookings`
- `/api/v1/trips/status`
- `/api/v1/handoffs/*`
- `/api/v1/users/me/settings`
- `/api/v1/livekit/*`
- `/api/v1/status`, `/api/v1/chat` (legacy compatibility)
- `/health`, `/ready`

OpenAPI runtime (`/openapi.json`) và schema trong `src/backend/schemas/` có thẩm
quyền cao hơn danh sách tóm tắt này.

## Persistence truth

`src/backend/db/models.py` và Alembic migrations đã định nghĩa bảng cho user, token,
ride session, booking, trip, handoff, call và conversation event. Tuy nhiên các
service chính vẫn dùng class-level dictionary/process memory. Vì vậy:

- restart có thể mất dữ liệu;
- chưa đạt multi-instance consistency;
- model/migration có sẵn không đồng nghĩa repository đã nối;
- trạng thái hiện tại là `DEMO/STAGING_ONLY`, không phải production persistence.

Thứ tự migration sang production: auth/settings -> session/state -> booking/trip ->
handoff/call -> audit event. Mỗi bước cần transaction, concurrency/idempotency,
rollback và integration test.

## Cấu trúc

- `api/`: route và dependency wiring
- `controllers/`: request orchestration
- `services/`: business/application logic
- `integrations/`: provider adapters và tool executor boundary
- `repositories/`: data-access abstraction
- `db/`: SQLAlchemy base/models/session
- `schemas/`: HTTP DTO
- `models/`: domain model
- `observability/`: logging/metrics helpers
- `workers/`: background work

## Configuration

`src/backend/config.py` đọc `.env`; contract mẫu duy nhất là `.env.example`.
Credential LiveKit, LLM và database phải nằm ở backend/worker; không đưa secret vào frontend.

Không commit `.env` hoặc secret vào tài liệu/log.

## Chạy và kiểm tra

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m compileall -q src tests
```

Production blockers và tiêu chí verify nằm tại `mustdo.md`; data contract/provenance
nằm tại `src/agents/DATAFINDING.md` và `data/catalog.json`.
