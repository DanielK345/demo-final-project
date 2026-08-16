# Repository audit — persistence và quote integrity

Date: **2026-08-16** · Branch: `feature/voice-ai`.

| Finding trước đây | Trạng thái mới | Evidence |
|---|---|---|
| Auth/session/settings/booking/trip dùng RAM ở runtime | `RESOLVED_IN_CODE` | `PersistenceRepository`; durable methods và route/controller wiring |
| Handoff/call không bền vững | `RESOLVED_IN_CODE` | DB-backed handoff/call lifecycle |
| Conversation history đọc file | `RESOLVED_IN_CODE` cho runtime | `conversation_messages`; file logger chỉ còn shadow/test compatibility |
| Quote không được lưu/consume atomically | `RESOLVED_IN_CODE` | `fare_quotes`, row lock, TTL, ownership, single-use |
| Client có thể ảnh hưởng giá booking | `RESOLVED_IN_CODE` | booking API nhận `quote_id`, giá lấy từ DB snapshot |
| Retry có thể tạo side effect lặp | `RESOLVED_IN_CODE` | `idempotency_records`, unique constraints, outbox |
| Pricing thay đổi làm lịch sử đổi | `RESOLVED_IN_CODE` | immutable catalog + booking pricing/route/promotion snapshot |
| Production bật trước nghiệm thu DB | `FAIL_CLOSED` | `DURABLE_SERVICE_PERSISTENCE_REQUIRED` vẫn bật |
| Maps/Promotion/Fleet/Dispatch production | `EXTERNAL_BLOCKED` | provider/credential/business approval chưa có |
| Giá hiện hành | `DEMO` | không được coi là AloSM production pricing |

Test double trong `APP_ENV=test` vẫn được giữ để không phá unit test lịch sử; nó không phải bằng chứng nghiệm thu persistence. Bằng chứng mới là real SQL integration và script `scripts/verify_postgres_persistence.py`.

P0 còn lại là áp dụng migration live có phê duyệt, chạy acceptance PostgreSQL, tạo runtime role least-privilege, backup/restore drill và multi-instance soak. Đây là thao tác hạ tầng/owner, không phải phần code còn bỏ trống.
