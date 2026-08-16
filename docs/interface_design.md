# Interface contract — AloSM Voice

Cập nhật: **2026-08-16** · Trạng thái: `CURRENT`.

OpenAPI runtime tại `/openapi.json` và schema trong `src/backend/schemas/` có thẩm
quyền cao hơn ví dụ trong tài liệu. Agent tool contract nằm tại
`src/agents/docs/BACKEND_INTEGRATION.md`.

## HTTP surface hiện hành

| Miền | Endpoint chính |
|---|---|
| Health | `GET /health`, `/ready`; ASR `/health/live`, `/health/ready`, `/metrics` |
| Auth | `POST /api/v1/auth/register`, `/login`, `/2fa/*`, `/change-password`; `GET /auth/me` |
| Session | `POST /api/v1/sessions`, `GET/PATCH /sessions/{id}`, `POST /messages`, `/resume`, `/feedback`, `/end` |
| History | `GET /api/v1/sessions/history`, `/history/{id}` |
| Booking | `POST/GET /api/v1/bookings` |
| Trip | `GET /api/v1/trips/status` |
| Handoff | `POST/GET /api/v1/handoffs`, `POST /handoffs/{id}/accept` |
| Settings | `GET/PUT /api/v1/users/me/settings` |
| Voice | `POST /api/v1/voice/turn`, `/speak`; health/metrics dưới `/api/v1/voice/*` |
| Local ASR | `POST /v1/audio/transcriptions` |
| Compatibility | `POST /api/v1/chat`, `GET /api/v1/status` |

WebSocket: `/api/v1/voice/stream` cho Voice Gateway và
`/api/v1/calls/{call_id}/stream` cho call transport hiện hành.

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
  -> POST /sessions/{id}/messages hoặc Voice turn
  -> Backend adapter gọi Core Agent
  -> apply state_updates
  -> execute CALL_TOOL nếu có
  -> correlated ToolResult về Agent
  -> ASK_USER / RESPOND / HANDOFF / END_SESSION
```

Action hợp lệ: `ASK_USER`, `RESPOND`, `CALL_TOOL`, `HANDOFF`, `END_SESSION`.
Chỉ `CALL_TOOL` chứa `tool_call`.

## Voice contracts

- `/voice/turn`: multipart audio + session, trả transcript/rewrite metadata,
  assistant text và optional validated audio/TTS metadata.
- `/voice/speak`: JSON text + review context, trả audio và `X-TTS-*` headers.
- `/voice/stream`: control JSON + PCM16 binary; server trả status/transcript/
  message/handoff/error JSON và `audio_meta` trước binary TTS.
- Không route nào được trả transcript/audio giả khi provider unavailable.

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
