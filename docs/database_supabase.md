# PostgreSQL/Supabase persistence, quote integrity và Maps data

Cập nhật: **2026-08-17** · nhánh `feature/voice-ai` · migration head `fc877ccd583a`.

Đây là tài liệu nguồn chuẩn duy nhất cho persistence layer. Các mô tả cũ nói runtime còn lưu hoàn toàn bằng RAM không còn đúng với môi trường development/production. `APP_ENV=test` vẫn giữ adapter bộ nhớ cũ cho các unit test lịch sử; bài nghiệm thu persistence mới dùng database thật, không mock repository hay transaction.

---

## 1. Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| ORM models | 18 bảng trong `src/backend/db/models.py` |
| Migration chain | `0001_initial_schema` → `0002_handoff_operations` → `9e9b6f420a9a` → `0004_maps_places_routes` → `fc877ccd583a` (head) |
| Runtime repository | Đã nối Auth, token/2FA, Session, Settings, Conversation, Booking, Trip, Handoff, Call, Places và RouteSnapshots |
| Quote integrity | Quote lưu DB, HMAC-SHA256, TTL, single-use, ownership check, idempotency và snapshot bất biến |
| Pricing snapshot | Lưu catalog version/checksum, route, rate, surcharge, promotion và tổng tiền vào quote/booking |
| Maps persistence | `places` + `route_snapshots` tables; `fare_quotes.route_snapshot_id` FK link |
| PostgreSQL live | Kết nối đọc thành công; DB hiện còn ở `0002_handoff_operations` |
| Migration live mới | Chưa áp dụng — cần phê duyệt mutation rõ ràng (xem §5) |
| Test code | `501 passed, 2 skipped`; integration persistence SQLite thật pass |
| Production gate | Fail-closed bằng `DURABLE_SERVICE_PERSISTENCE_REQUIRED` |

Không được tuyên bố `PRODUCTION_READY` khi catalog giá còn `DEMO`, chưa có Maps/Promotion/Dispatch provider production và chưa hoàn thành backup/restore/pentest.

---

## 2. Luồng dữ liệu chuẩn

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        AloSM Data Flow                                  │
│                                                                          │
│  Client search query                                                     │
│      ↓                                                                   │
│  MapsService → GeocodingProvider (Nominatim) → PlaceCandidate[]          │
│      ↓ (user confirms)                                                   │
│  resolve_place → places table (plc_<uuid>)                               │
│      ↓                                                                   │
│  MapsService → RoutingProvider (OSRM) → route_snapshots (rte_<uuid>)     │
│      ↓                                                                   │
│  PricingService + immutable pricing_catalog_versions                     │
│      ↓                                                                   │
│  fare_quotes (TTL + context_hash + HMAC + route_snapshot_id FK)          │
│      ↓ (explicit user confirmation — KHÔNG auto-book)                    │
│  transaction: SELECT ... FOR UPDATE                                      │
│      ↓                                                                   │
│  bookings + consumed quote + idempotency_records + outbox_events         │
│      ↓                                                                   │
│  trips / handoff / conversation history                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Nguyên tắc bắt buộc

1. Client chỉ gửi `quote_id`; không được gửi hoặc quyết định giá.
2. Booking dùng đúng `user_id`, `session_id`, route và vehicle đã ký.
3. Quote hết hạn, đã dùng, bị sửa hoặc khác owner đều bị từ chối.
4. Retry cùng `Idempotency-Key` không tạo booking thứ hai.
5. Booking giữ bản chụp giá/route/promotion để lịch sử không đổi khi catalog mới được phát hành.
6. Tiền dùng integer VND (BigInteger); timestamp dùng UTC `DateTime(timezone=True)`; JSON dùng JSONB trên PostgreSQL, JSON trên SQLite.
7. Lệnh gọi LLM/provider/Nominatim/OSRM chạy **ngoài** transaction; transaction chỉ bao quanh thao tác DB ngắn.
8. Places được resolve trước khi routing; route_snapshot được tạo trước khi quote.
9. `route_snapshot` là bất biến — nếu route thay đổi, tạo snapshot mới.

---

## 3. Entity Relationship Diagram

### 3.1 Nhóm Identity (5 bảng)

| Bảng | PK | Mục đích | FK / Constraint đáng chú ý |
|---|---|---|---|
| `users` | `id` (String 32, `usr_<hex>`) | Tài khoản người dùng | `phone` UNIQUE; có 2FA/TOTP |
| `auth_tokens` | `token` (String 64) | Bearer token đăng nhập | FK `users.id` CASCADE; `token_hash` UNIQUE |
| `auth_challenges` | `id` (String 32) | OTP / 2FA challenge | FK `users.id` CASCADE; `challenge_token_hash` UNIQUE |
| `policy_acceptances` | `id` (String 32) | Chấp nhận điều khoản/privacy | FK `users.id` CASCADE; `source_sha256` integrity |
| `user_settings` | `user_id` (String 32) | Cài đặt ngôn ngữ/theme/notification | FK `users.id` CASCADE; 1:1 |

### 3.2 Nhóm Conversation (3 bảng)

| Bảng | PK | Mục đích | FK / Constraint đáng chú ý |
|---|---|---|---|
| `ride_sessions` | `id` (String 32, `sess_<hex>`) | Phiên hội thoại đặt xe | FK `users.id`; `booking_id` soft-ref; `version` cho optimistic lock |
| `conversation_messages` | `id` (BigInt auto) | Tin nhắn agent ↔ user | FK `ride_sessions.id` CASCADE; UNIQUE `(session_id, turn_id, sequence)` |
| `conversation_events` | `id` (Integer auto) | Audit log hội thoại | FK `ride_sessions.id`; index `created_at` |

### 3.3 Nhóm Operations (3 bảng)

| Bảng | PK | Mục đích | FK / Constraint đáng chú ý |
|---|---|---|---|
| `handoffs` | `id` (String 32) | Chuyển người thật | FK `ride_sessions.id`; index `(status, priority)` |
| `calls` | `id` (String 32) | Cuộc gọi voice | FK `ride_sessions.id`; `customer_phone_hash` SHA-256 |
| `trips` | `id` (String 32) | Chuyến xe gắn booking | FK `bookings.id` UNIQUE; 1:1 |

### 3.4 Nhóm Quote/Booking (4 bảng)

| Bảng | PK | Mục đích | FK / Constraint đáng chú ý |
|---|---|---|---|
| `pricing_catalog_versions` | `id` (String 32) | Phiên bản bảng giá | UNIQUE `(version, region)`; `source_sha256` UNIQUE; append-only |
| `fare_quotes` | `id` (String 32, `quote_<hex>`) | Báo giá có HMAC, TTL, single-use | FK `users`, `ride_sessions`, `pricing_catalog_versions`, `route_snapshots` (nullable); giữ snapshot JSONB |
| `bookings` | `id` (String 32, `booking_<hex>`) | Đặt xe đã xác nhận | FK `ride_sessions`, `users`, `fare_quotes`; `quote_id` UNIQUE; `idempotency_key` UNIQUE |
| `idempotency_records` | `(scope, idempotency_key)` | Chặn duplicate side effect | Composite PK; `response_snapshot` JSONB; `expires_at` |

### 3.5 Nhóm Reliability (1 bảng)

| Bảng | PK | Mục đích | FK / Constraint đáng chú ý |
|---|---|---|---|
| `outbox_events` | `id` (BigInt auto) | Outbox cho reliable event delivery | `aggregate_type + aggregate_id`; `status` PENDING → PROCESSED |

### 3.6 Nhóm Maps (2 bảng)

| Bảng | PK | Mục đích | FK / Constraint đáng chú ý |
|---|---|---|---|
| `places` | `id` (String 32, `plc_<hex>`) | Địa điểm đã resolve | UNIQUE `(provider, provider_place_id)`; index `created_at`, `serviceable`; `lat/lon` Numeric(10,7) |
| `route_snapshots` | `id` (String 32, `rte_<hex>`) | Snapshot tuyến đường bất biến | FK `places.id` × 2 (pickup, destination); `geometry` JSONB; `distance_meters` Numeric(12,2) |

### 3.7 Quan hệ then chốt

```
users ──1:N──> auth_tokens
users ──1:N──> ride_sessions
users ──1:N──> fare_quotes
ride_sessions ──1:N──> bookings
ride_sessions ──1:N──> conversation_messages
ride_sessions ──1:N──> handoffs
ride_sessions ──0:1──> calls
bookings ──1:1──> trips
bookings ──N:1──> fare_quotes (quote_id UNIQUE → mỗi quote chỉ dùng 1 lần)
fare_quotes ──N:1──> pricing_catalog_versions
fare_quotes ──N:1──> route_snapshots (nullable — legacy/DEMO quotes không có)
route_snapshots ──N:1──> places (pickup)
route_snapshots ──N:1──> places (destination)
pricing_catalog_versions: UNIQUE(version, region) + source_sha256 UNIQUE → append-only
idempotency_records: composite PK(scope, key) → chặn duplicate booking
outbox_events: worker poll PENDING → PROCESSED
```

---

## 4. Migration chain

| Revision | Tên | Nội dung chính |
|---|---|---|
| `0001_initial_schema` | Initial | users, auth_tokens, ride_sessions, bookings, trips, handoffs, calls, conversation_events, policy_acceptances |
| `0002_handoff_operations` | Handoff ops | auth_challenges, user_settings, conversation_messages |
| `9e9b6f420a9a` | Durable persistence | 2FA columns, PricingCatalogVersion, FareQuote, IdempotencyRecord, OutboxEvent, RLS enable, anon/authenticated revoke |
| `0004_maps_places_routes` | Maps | places, route_snapshots tables |
| `fc877ccd583a` (head) | FK link | `fare_quotes.route_snapshot_id` FK → `route_snapshots.id` |

**Live status:** `0002_handoff_operations` — cần chạy 3 migration còn lại (xem §5).

---

## 5. Connection đúng mục đích

```env
# Runtime FastAPI: Supavisor transaction pooler, thường cổng 6543
DATABASE_URL=postgresql://...

# Alembic: direct/session connection, thường cổng 5432
DATABASE_URL_MIGRATIONS=postgresql://...

# Hai secret độc lập, tối thiểu 32 ký tự; không commit
QUOTE_SIGNING_KEY=...
FIELD_ENCRYPTION_KEY=...
```

### 5.1 Tại sao cần 2 URL

| Concern | Runtime URL | Migration URL |
|---|---|---|
| Driver | asyncpg (async) | psycopg2 (sync) |
| Pooler | Transaction pooler (Supavisor, port 6543) | Direct/Session (port 5432) |
| Statement cache | Tắt (`statement_cache_size=0`) | N/A |
| SQLAlchemy pool | `NullPool` (pooler quản lý) | Default |
| Quyền | Chỉ DML (SELECT/INSERT/UPDATE) | DDL owner (CREATE/ALTER/DROP) |
| Khi dùng | Mọi request HTTP | Chỉ khi chạy `alembic upgrade` |

Runtime asyncpg đã tắt prepared-statement cache để tương thích transaction pooler. Alembic dùng psycopg2 và URL migration riêng. Không dùng owner/direct credential của migration làm credential runtime production.

### 5.2 SQLite cho dev/test

Khi `DATABASE_URL=sqlite:///./data/test.db`, hệ thống tự chuyển sang `sqlite+aiosqlite` (async) với pool mặc định. Test conftest đặt `APP_ENV=test` → nhiều service dùng adapter in-memory thay vì gọi DB. Integration tests dùng SQLite thật để kiểm tra persistence thật nhưng không cần Supabase.

---

## 6. Quy trình migration live an toàn

### 6.1 Chuẩn bị

1. Chụp backup/snapshot hoặc xác nhận PITR đang hoạt động.
2. Dừng deploy ghi dữ liệu hoặc bật maintenance window.
3. Xác nhận `.env` trỏ đúng environment; tuyệt đối không in URL/password:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic heads
   .\.venv\Scripts\python.exe -m alembic current
   ```

   Expected trước migration: head `fc877ccd583a`, current `0002_handoff_operations`.

### 6.2 Phê duyệt và thực thi

4. Review SQL/migration code:
   - `9e9b6f420a9a`: thêm 2FA columns, bảng pricing/quote/idempotency/outbox, bật RLS, revoke anon
   - `0004_maps_places_routes`: thêm places, route_snapshots
   - `fc877ccd583a`: thêm `fare_quotes.route_snapshot_id` FK + index

5. Cấp phê duyệt mutation database live.

6. Áp dụng:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe -m alembic current
   .\.venv\Scripts\python.exe -m alembic check
   ```

   Expected: current `fc877ccd583a (head)` và `No new upgrade operations detected`.

### 6.3 Nghiệm thu

7. Chạy acceptance PostgreSQL thật:

   ```powershell
   .\.venv\Scripts\python.exe scripts\verify_postgres_persistence.py
   ```

   Expected: tất cả `PASS`:
   - `POSTGRES_PERSISTENCE_ACCEPTANCE=PASS`
   - `QUOTE_TAMPER_REJECTION=PASS`
   - `CONCURRENT_IDEMPOTENCY=PASS`
   - `RESTART_READBACK=PASS`
   - `RLS_ENABLED=PASS`

   Script chỉ xóa đúng record có ID nó vừa tạo; immutable pricing catalog verification được giữ lại.

8. Chạy Supabase Database Advisors: **Dashboard → Database → Advisors → Security** và **Performance**. Không được bỏ qua lỗi RLS, exposed table, missing FK index hoặc duplicate index.

9. Chạy smoke API hai process/instance cùng database, retry cùng idempotency key và xác nhận chỉ một booking.

10. Sau khi evidence trên pass mới xóa code gate `DURABLE_SERVICE_PERSISTENCE_REQUIRED` và chạy lại toàn bộ release suite.

### 6.4 Xử lý lỗi

Nếu migration lỗi: **dừng ngay**. Không `stamp head` thủ công. Không sửa trực tiếp bảng để "chạy tiếp". Không chạy lại bằng credential mạnh hơn. Lưu nguyên lỗi, revision, output và restore/rollback theo backup/runbook đã duyệt.

---

## 7. Security và RLS

### 7.1 Row-Level Security

Migration `9e9b6f420a9a` bật RLS cho toàn bộ bảng `public` và thu hồi quyền `anon`/`authenticated` nếu các role này tồn tại. Bảng có RLS bắt buộc:

```
users, auth_tokens, ride_sessions, bookings, trips, handoffs, calls,
conversation_events, policy_acceptances, auth_challenges, user_settings,
conversation_messages, pricing_catalog_versions, fare_quotes,
idempotency_records, outbox_events
```

Backend hiện dùng direct SQLAlchemy (không qua Supabase Data API), vì vậy:
- Không tạo policy giả dựa trên `auth.uid()` — dự án dùng custom auth.
- Nếu muốn dùng Supabase Data API/Auth sau này, phải thiết kế tenant/owner policies riêng và có security review.

### 7.2 Runtime role least-privilege

Trước production cần:

1. Tạo login role riêng cho app runtime (không phải `postgres`/owner).
2. Không cấp `BYPASSRLS`, `CREATEDB`, `CREATEROLE`, `ALTER`, `DROP`, `CREATE`.
3. Cấp đúng: `CONNECT`, `USAGE` schema, `SELECT/INSERT/UPDATE` cho runtime tables, `USAGE` trên sequences.
4. Giữ migration role (owner) riêng biệt, chỉ CI/DBA truy cập.

Verify:

```sql
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls
FROM pg_roles WHERE rolname = '<runtime_role>';
-- Tất cả cờ đặc quyền phải false.
```

### 7.3 Secret rotation

| Secret | Quy trình xoay | Rủi ro nếu sai |
|---|---|---|
| `QUOTE_SIGNING_KEY` | Đổi sau khi mọi quote đã hết TTL (5 phút), hoặc implement key ring/version | Quote hợp lệ bị reject |
| `FIELD_ENCRYPTION_KEY` | Migration batch: decrypt cũ → encrypt mới với checkpoint/rollback | TOTP ciphertext cũ không giải mã được, 2FA bị khóa |
| `DATABASE_URL` | Xoay password trong Supabase → cập nhật secret manager → restart | Mất kết nối runtime |
| `DATABASE_URL_MIGRATIONS` | Xoay riêng biệt; chỉ CI/DBA cần | Alembic upgrade fail |

Quy trình:

1. Tạo key mới trong secret manager, không gửi qua chat/log.
2. Triển khai canary trước, kiểm tra login/2FA/quote.
3. Rollout progressive, giữ key cũ trong grace period.
4. Thu hồi key cũ sau khi confirm toàn bộ instance đã chuyển.

---

## 8. Data types và conventions

| Convention | Quy tắc | Lý do |
|---|---|---|
| ID format | String `<prefix>_<uuid4.hex[:N]>` | Nhất quán với code hiện tại, tránh Postgres UUID type |
| Tiền | `BigInteger` (integer VND) | Tránh floating-point rounding; VND không có xu |
| Timestamp | `DateTime(timezone=True)`, `server_default=func.now()` | UTC everywhere; Postgres tự convert |
| JSON | `JSON().with_variant(JSONB(), "postgresql")` | JSONB cho production (indexable), JSON cho SQLite dev |
| BigInt PK | `BigInteger().with_variant(Integer(), "sqlite")` | SQLite không hỗ trợ BigInteger auto |
| Optimistic lock | `version` column trên `ride_sessions` | Tránh lost update khi concurrent session update |
| Soft delete | Không dùng; dùng status transitions | Rõ ràng hơn cho audit |
| Cascade | `CASCADE` chỉ trên auth (tokens, challenges → user) | Tránh cascade delete mất dữ liệu booking/trip |

---

## 9. Repositories và Service Layer

### 9.1 Repository architecture

| Repository | Module | Bảng phụ trách |
|---|---|---|
| `PersistenceRepository` | `src/backend/repositories/persistence_repository.py` | users, auth_tokens, auth_challenges, ride_sessions, bookings, trips, handoffs, calls, conversation_messages, policy_acceptances, user_settings, pricing_catalog_versions, fare_quotes, idempotency_records, outbox_events |
| `MapsRepository` | `src/backend/repositories/maps_repository.py` | places, route_snapshots |

### 9.2 Luồng service → repository

```
AgentToolExecutor → PlaceSearchService / QuoteService / BookingService
                         ↓                    ↓                ↓
                    MapsService          PricingService    TripService
                         ↓                    ↓                ↓
                  MapsRepository     PersistenceRepository
                         ↓                    ↓
                  places / route_snapshots   fare_quotes / bookings / ...
                         ↓─────────────────────↓
                              AsyncSession
                                   ↓
                            PostgreSQL (Supabase)
```

Tất cả repository nhận `AsyncSession` (inject qua `get_session_factory()`) và không tự quản lý transaction boundary — caller quản lý commit/rollback.

---

## 10. Monitoring và Alerting

### 10.1 Metrics cần thiết

| Metric | Nguồn | Alert threshold |
|---|---|---|
| DB latency p95 | Application-level timer | > 500ms |
| Transaction error rate | SQLAlchemy exception count | > 1% |
| Quote rejection rate | QuoteService verify failure | > 5% (anomaly) |
| Idempotency collision | IntegrityError on idempotency_records | Monitor (expected low) |
| Outbox lag | `outbox_events WHERE status='PENDING' AND created_at < now() - interval '5 min'` | > 0 sustained |
| Connection pool exhaustion | NullPool → không pool, nhưng monitor connection count | Supavisor dashboard |
| RLS violation attempts | PostgreSQL log grep | Any occurrence |
| Maps provider latency | MapsService timer | > 2s p95 |
| Maps provider error rate | MapsDomainError count | > 5% |

### 10.2 Supabase Dashboard checks

- **Database → Advisors → Security**: RLS status, exposed tables, auth config
- **Database → Advisors → Performance**: missing indexes, duplicate indexes, unused indexes
- **Database → Connections**: active connections, pool utilization
- **Logs → Postgres**: slow queries, errors, RLS violations

---

## 11. Backup, PITR và Disaster Recovery

### 11.1 Chiến lược backup

| Item | Yêu cầu |
|---|---|
| Automated backup | Supabase Pro plan có daily backup; Enterprise có PITR |
| Backup verification | Restore vào project cô lập, chạy Alembic current + FK checks + row counts |
| RTO target | Định nghĩa bởi owner (khuyến nghị < 1 giờ) |
| RPO target | Định nghĩa bởi owner (PITR: seconds; daily backup: 24h) |
| Restore drill | Ít nhất 1 lần trước go-live, ghi evidence |

### 11.2 Data retention

Owner phải phê duyệt retention cho từng loại dữ liệu:

| Loại dữ liệu | Cần Legal/Privacy approval |
|---|---|
| Account/token | Xóa sau deactivation + grace period |
| Session/transcript | Tuân theo privacy policy |
| Location (lat/lon/polyline) | Consent + retention limit |
| Quote/booking | Thuế/kế toán có thể yêu cầu giữ lâu |
| Call/handoff/audio | Recording consent + retention |
| Audit/outbox | Compliance retention |

---

## 12. Troubleshooting

### 12.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|---|---|---|
| `prepared statement "..." already exists` | Statement cache chưa tắt khi dùng transaction pooler | Kiểm tra `statement_cache_size=0` trong connect_args |
| `DURABLE_SERVICE_PERSISTENCE_REQUIRED` | Production gate chưa mở | Chạy migration + acceptance script (§6) |
| `QUOTE_INTEGRITY_INVALID` | Quote bị sửa hoặc key không khớp | Kiểm tra `QUOTE_SIGNING_KEY` nhất quán giữa instances |
| `IntegrityError` trên `idempotency_key` | Retry hợp lệ (expected) | Trả response đã cached từ `idempotency_records` |
| Migration conflict | Branch khác đã tạo migration | Merge revision, không stamp thủ công |
| `asyncpg.TooManyConnectionsError` | Quá nhiều connection qua pooler | Kiểm tra Supavisor limits; NullPool nên không giữ idle |
| RLS block trên query | Runtime role không được cấp policy | Kiểm tra role có SELECT/INSERT/UPDATE trên bảng cần thiết |

### 12.2 Debug checklist

```powershell
# 1. Kiểm tra revision
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads

# 2. Kiểm tra model sync
.\.venv\Scripts\python.exe -m alembic check

# 3. Test persistence offline
.\.venv\Scripts\python.exe -m pytest tests/test_backend/ -v

# 4. Test persistence online (PostgreSQL live, cần phê duyệt)
.\.venv\Scripts\python.exe scripts\verify_postgres_persistence.py

# 5. Kiểm tra connection
.\.venv\Scripts\python.exe -c "from src.backend.db.base import get_engine; print(get_engine().url)"
```

---

## 13. Definition of Done

Persistence/quote/maps chỉ đạt production gate khi **đồng thời** có:

- [ ] Migration live ở `fc877ccd583a` (head);
- [ ] Script PostgreSQL acceptance pass (5 dòng PASS);
- [ ] Restart và multi-instance duplicate booking bằng 0;
- [ ] Runtime role least-privilege, RLS/Advisors không còn lỗi P0;
- [ ] Backup/PITR và restore drill có bằng chứng (RTO/RPO thực tế);
- [ ] Key rotation, retention, deletion/export và audit được duyệt;
- [ ] Pricing/route/promotion catalog production có owner, version và approval;
- [ ] Metrics/alert cho DB latency, transaction error, quote rejection, idempotency collision và outbox lag;
- [ ] Maps provider (Nominatim/OSRM) health check pass trên `/health/ready`;
- [ ] Places resolve + route snapshot persistence E2E test pass.

Các việc cần owner/hạ tầng được hướng dẫn chi tiết ở `mustdo.md`; phần còn lại thuộc trách nhiệm code và không được chuyển sang mustdo.

---

## Appendix A. File reference

| File | Mục đích |
|---|---|
| `src/backend/db/base.py` | Engine/session factory, URL conversion, NullPool, statement cache off |
| `src/backend/db/models.py` | 19 ORM models |
| `src/backend/repositories/persistence_repository.py` | CRUD operations cho 15 bảng |
| `src/backend/repositories/maps_repository.py` | CRUD operations cho places + route_snapshots |
| `src/backend/services/quote_service.py` | Quote issuance, HMAC signing, verify |
| `src/backend/services/booking_service.py` | Booking from quote, idempotency, outbox |
| `src/backend/services/maps_service.py` | Maps orchestration (search, reverse, resolve, route) |
| `migrations/versions/*.py` | 5 migration files (chain ở §4) |
| `migrations/env.py` | Alembic config: psycopg2 sync driver, target_metadata |
| `scripts/verify_postgres_persistence.py` | Live PostgreSQL acceptance script |
| `docs/verification/database.md` | Evidence log cho acceptance runs |
| `.env.example` | Tất cả biến môi trường database + maps |
| `mustdo.md` | External blockers cho production |
