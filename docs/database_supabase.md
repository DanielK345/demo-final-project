# PostgreSQL/Supabase persistence và quote integrity

Cập nhật: **2026-08-16** · nhánh `feature/voice-ai` · migration head `0004_maps_places_routes`.

Đây là tài liệu nguồn chuẩn cho persistence. Các mô tả cũ nói runtime còn lưu hoàn toàn bằng RAM không còn đúng với môi trường development/production. `APP_ENV=test` vẫn giữ adapter bộ nhớ cũ cho các unit test lịch sử; bài nghiệm thu persistence mới dùng database thật, không mock repository hay transaction.

## 1. Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| ORM và migration | Đã triển khai trong `src/backend/db/models.py` và `migrations/versions/9e9b6f420a9a_*.py` và `0004_maps_places_routes.py` |
| Runtime repository | Đã nối Auth, token/2FA, Session, Settings, Conversation, Booking, Trip, Handoff và Call |
| Quote integrity | Quote lưu DB, HMAC-SHA256, TTL, single-use, ownership check, idempotency và snapshot bất biến |
| Pricing snapshot | Lưu catalog version/checksum, route, rate, surcharge, promotion và tổng tiền vào quote/booking |
| PostgreSQL live | Kết nối đọc thành công; DB hiện còn ở `0002_handoff_operations` |
| Migration live mới | Chưa áp dụng vì thao tác schema/RLS live cần phê duyệt mutation rõ ràng |
| Test code | `501 passed, 2 skipped`; integration persistence SQLite thật pass |
| Production gate | Vẫn fail-closed bằng `DURABLE_SERVICE_PERSISTENCE_REQUIRED` cho đến khi migration và script PostgreSQL live pass |

Không được tuyên bố `PRODUCTION_READY` khi catalog giá còn `DEMO`, chưa có Maps/Promotion/Dispatch provider và chưa hoàn thành backup/restore/pentest.

## 2. Luồng dữ liệu chuẩn

```text
Place/Route provider
  -> PricingService + immutable pricing_catalog_versions
  -> fare_quotes (TTL + context_hash + HMAC signature + snapshots)
  -> explicit confirmation
  -> transaction SELECT ... FOR UPDATE
  -> bookings + consumed quote + idempotency_records + outbox_events
  -> trips / handoff / conversation history
```

Nguyên tắc bắt buộc:

- Client chỉ gửi `quote_id`; không được gửi hoặc quyết định giá.
- Booking dùng đúng `user_id`, `session_id`, route và vehicle đã ký.
- Quote hết hạn, đã dùng, bị sửa hoặc khác owner đều bị từ chối.
- Retry cùng `Idempotency-Key` không tạo booking thứ hai.
- Booking giữ bản chụp giá/route/promotion để lịch sử không đổi khi catalog mới được phát hành.
- Tiền dùng integer VND; timestamp dùng UTC; JSON dùng JSONB trên PostgreSQL.
- Lệnh gọi LLM/provider chạy ngoài transaction; transaction chỉ bao quanh thao tác DB ngắn.

## 3. Bảng chính

- Identity: `users`, `policy_acceptances`, `auth_tokens`, `auth_challenges`, `user_settings`.
- Conversation: `ride_sessions`, `conversation_messages`, `conversation_events`.
- Operations: `handoffs`, `calls`, `trips`.
- Quote/booking: `pricing_catalog_versions`, `fare_quotes`, `bookings`.
- Reliability: `idempotency_records`, `outbox_events`.
- Maps: `places`, `route_snapshots` (head `0004_maps_places_routes`).

`pricing_catalog_versions` là append-only theo `(version, region)`. Cùng version/region nhưng checksum khác bị từ chối. `fare_quotes` là single-use; `bookings.quote_id` unique. `idempotency_records` chặn retry side effect; `outbox_events` chuẩn bị cho worker phát sự kiện đáng tin cậy.

## 4. Connection đúng mục đích

```env
# Runtime FastAPI: Supavisor transaction pooler, thường cổng 6543
DATABASE_URL=postgresql://...

# Alembic: direct/session connection, thường cổng 5432
DATABASE_URL_MIGRATIONS=postgresql://...

# Hai secret độc lập, tối thiểu 32 ký tự; không commit
QUOTE_SIGNING_KEY=...
FIELD_ENCRYPTION_KEY=...
```

Runtime asyncpg đã tắt prepared-statement cache để tương thích transaction pooler. Alembic dùng psycopg2 và URL migration riêng. Không dùng owner/direct credential của migration làm credential runtime production lâu dài.

## 5. Quy trình migration live an toàn

1. Chụp backup/snapshot hoặc xác nhận PITR đang hoạt động.
2. Dừng deploy ghi dữ liệu hoặc bật maintenance window.
3. Xác nhận `.env` trỏ đúng environment; tuyệt đối không in URL/password:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic heads
   .\.venv\Scripts\python.exe -m alembic current
   ```

   Expected trước migration: head `0004_maps_places_routes`, current `0002_handoff_operations`.

4. Review SQL/migration và cấp phê duyệt mutation database live.
5. Áp dụng:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe -m alembic current
   .\.venv\Scripts\python.exe -m alembic check
   ```

   Expected: current `0004_maps_places_routes (head)` và `No new upgrade operations detected`.

6. Chạy nghiệm thu PostgreSQL thật:

   ```powershell
   .\.venv\Scripts\python.exe scripts\verify_postgres_persistence.py
   ```

   Expected: `POSTGRES_PERSISTENCE_ACCEPTANCE=PASS`, quote tamper rejection, concurrent idempotency, restart readback và RLS đều pass. Script chỉ xóa đúng record có ID nó vừa tạo; immutable pricing catalog verification được giữ lại.

7. Chạy Supabase Database Advisors trong Dashboard: **Database → Advisors → Security** và **Performance**. Không được bỏ qua lỗi RLS, exposed table, missing FK index hoặc duplicate index.
8. Chạy smoke API hai process/instance cùng database, retry cùng idempotency key và xác nhận chỉ một booking.
9. Sau khi evidence trên pass mới xóa code gate `DURABLE_SERVICE_PERSISTENCE_REQUIRED` và chạy lại toàn bộ release suite.

Nếu migration lỗi: dừng ngay, lưu nguyên lỗi và revision, không stamp head thủ công, không sửa trực tiếp bảng để “chạy tiếp”. Restore/rollback chỉ thực hiện theo backup/runbook đã duyệt.

## 6. Security/RLS

Migration bật RLS cho toàn bộ bảng `public` và thu hồi quyền `anon`/`authenticated` nếu các role này tồn tại. Backend hiện dùng direct SQLAlchemy, vì vậy không tạo policy dựa trên `auth.uid()` giả cho custom auth. Trước production cần tạo runtime DB role least-privilege không phải owner, cấp đúng DML/sequence, giữ migration role riêng và kiểm tra runtime role không có `BYPASSRLS`/DDL.

Secret rotation:

1. Tạo key mới trong secret manager, không gửi qua chat/log.
2. Với `QUOTE_SIGNING_KEY`, chỉ đổi sau khi quote cũ hết TTL hoặc hỗ trợ key version/key ring.
3. Với `FIELD_ENCRYPTION_KEY`, phải có migration decrypt-old/encrypt-new theo batch và khả năng rollback; đổi thẳng sẽ làm TOTP cũ không giải mã được.
4. Restart canary, kiểm tra login/2FA/quote, rồi rollout.

## 7. Definition of Done

Persistence/quote chỉ đạt production gate khi đồng thời có:

- migration live ở `0004_maps_places_routes`;
- script PostgreSQL acceptance pass;
- restart và multi-instance duplicate booking bằng 0;
- runtime role least-privilege, RLS/advisors không còn lỗi P0;
- backup/PITR và restore drill có bằng chứng;
- key rotation, retention, deletion/export và audit được duyệt;
- pricing/route/promotion catalog production có owner, version và approval;
- metrics/alert cho DB latency, transaction error, quote rejection, idempotency collision và outbox lag.

Các việc cần owner/hạ tầng được hướng dẫn chi tiết ở `mustdo.md`; phần còn lại thuộc trách nhiệm code và không được chuyển sang mustdo.
