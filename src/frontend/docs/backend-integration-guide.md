# Frontend ↔ Backend integration

Cập nhật: **2026-08-16** · Trạng thái: `CURRENT`.

OpenAPI `/openapi.json`, DTO Backend và TypeScript type/API client hiện hành là nguồn
chuẩn. Không dùng payload minh họa cũ để xây endpoint mới.

## Client và auth

- Base URL: `src/app/config/api.ts`.
- Bearer token do `src/features/auth` quản lý.
- `fetchApi` chuẩn hóa JSON/error và gắn auth header.
- `401/403` phải clear/redirect đúng session policy; không coi lỗi network là auth fail.

## Feature mapping

| Frontend | API |
|---|---|
| Auth/2FA/password | `/api/v1/auth/*` |
| Ride session/typed turn | `/api/v1/sessions`, `/sessions/{id}/messages` |
| Resume/end/feedback | `/api/v1/sessions/{id}/{resume,end,feedback}` |
| Activity/history | `/api/v1/bookings`, `/api/v1/sessions/history*` |
| Tracking | `/api/v1/trips/status?session_id=...` |
| Settings | `/api/v1/users/me/settings` |
| Voice realtime | LiveKit Room; connection details từ `/api/v1/livekit/*` |
| Agent readiness | `/api/v1/status` |

## Booking boundary

Frontend gửi utterance/selection qua session flow; Core Agent + Backend quyết định
tool lifecycle. CTA chỉ mở popup/prefill draft. UI không gọi create-booking để bypass
confirmation, không tự resolve location và không tự tính fare/voucher.

Khi Backend trả booking progress, FE có thể hiển thị candidate/vehicle/quote. Sửa
location/vehicle phải làm stale quote/confirmation biến mất theo Backend state.

## Voice transport

Frontend dùng LiveKit components để publish microphone, nhận audio/transcript và gửi
text fallback. API key/secret không bao giờ được đưa vào bundle trình duyệt.

## Demo isolation

`features/booking/mockData.ts` chỉ là service catalog minh họa. Map/fleet/voucher/
payment demo phải gắn nhãn và không đi vào booking payload như business truth.

## Contract change process

1. Sửa Backend schema/OpenAPI và contract test.
2. Cập nhật TypeScript type/API client.
3. Cập nhật status/user flow nếu semantics thay đổi.
4. Chạy backend tests và frontend lint/typecheck/build.

Không dùng `file://` path, endpoint tưởng tượng hoặc token/example credential trong tài liệu.
