# Interface contract — AloSM Voice

Cập nhật: **2026-08-16** · Trạng thái: `CURRENT`.

OpenAPI runtime tại `/openapi.json` và schema trong `src/backend/schemas/` có thẩm
quyền cao hơn ví dụ trong tài liệu. Agent tool contract nằm tại
`src/agents/docs/BACKEND_INTEGRATION.md`.

## HTTP surface hiện hành

| Miền | Endpoint chính |
|---|---|
| Health | `GET /health`, `/ready` |
| Auth | `POST /api/v1/auth/register`, `/login`, `/2fa/*`, `/change-password`; `GET /auth/me` |
| Policy | `GET /api/v1/policies/current`, `/policies/current/source`; register bắt buộc policy versions |
| Session | `POST /api/v1/sessions`, `GET/PATCH /sessions/{id}`, `POST /messages`, `/resume`, `/feedback`, `/end` |
| History | `GET /api/v1/sessions/history`, `/history/{id}` |
| Booking | `POST/GET /api/v1/bookings` |
| Trip | `GET /api/v1/trips/status` |
| Handoff | `POST/GET /api/v1/handoffs`, `POST /handoffs/{id}/accept` |
| Settings | `GET/PUT /api/v1/users/me/settings` |
| LiveKit | connection details/token endpoints dưới `/api/v1/livekit/*` |
| Compatibility | `POST /api/v1/chat`, `GET /api/v1/status` |

Media, transcript và data-channel realtime đi qua LiveKit Room.

## Shared rules

- Bearer token bảo vệ resource theo user/session ownership.
- API time dùng ISO-8601 có timezone; tiền là integer + currency.
- Client không tự tạo fare, ETA, place ID, booking ID hoặc handoff result.
- Create booking yêu cầu explicit confirmation và idempotency key.
- Tool result phải khớp `call_id`/`tool_name`; unknown side-effect outcome đi
  reconciliation, không retry mù.
- Breaking field semantics cần version/migration; optional additive field có thể
  backward-compatible.

## Session/Agent lifecycle

```text
POST /sessions
  -> POST /sessions/{id}/messages hoặc LiveKit AgentSession
  -> Backend adapter gọi Core Agent
  -> apply state_updates
  -> execute CALL_TOOL nếu có
  -> correlated ToolResult về Agent
  -> ASK_USER / RESPOND / HANDOFF / END_SESSION
```

Action hợp lệ: `ASK_USER`, `RESPOND`, `CALL_TOOL`, `HANDOFF`, `END_SESSION`.
Chỉ `CALL_TOOL` chứa `tool_call`.

## LiveKit voice contracts

- Backend cấp participant token ngắn hạn và chỉ sau khi kiểm tra auth/session ownership.
- Browser publish microphone và nhận audio/transcript qua LiveKit Room.
- Worker publish booking/handoff state qua data channel; side effect vẫn qua typed backend tools.
- LiveKit API key/secret không được xuất hiện trong payload frontend.

## Error behavior

Frontend phải xử lý theo HTTP status và typed error/code khi có; không parse câu
message để điều khiển nghiệp vụ. Validation/auth/not-found/conflict/provider timeout
phải giữ nguyên semantics qua route/controller/service.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m compileall -q src tests scripts
cd src\frontend
npm run lint
npx tsc -b
npm run build
```

Provider/live acceptance chạy riêng theo runbook Voice. External contracts chưa có
credential/business owner vẫn nằm trong `mustdo.md`, không được mock thành production.
