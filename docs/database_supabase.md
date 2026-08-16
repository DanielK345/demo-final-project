# Database cho Deploy — Supabase (Postgres)

Tài liệu này gồm: (1) thiết kế schema, (2) kiến trúc kết nối (vì sao 2 loại connection
string khác nhau), (3) hướng dẫn từng bước tạo project Supabase thật, (4) cách chạy
migration, (5) trạng thái code hiện tại.

## 1. Vì sao Supabase Postgres, và nối bằng cách nào

Stack đã có sẵn `sqlalchemy`, `alembic`, `psycopg2-binary` trong `requirements.txt`
trước khi tài liệu này được viết — Postgres rõ ràng là lựa chọn thiết kế từ đầu, chỉ
chưa được nối dây. Supabase là Postgres managed, free tier đủ dùng cho giai đoạn
capstone.

**Chi tiết Free Tier (08/2026):** 500 MB database, 5 GB egress, 2 project, tự **pause
sau 7 ngày không có query nào chạm DB thật** (không tính việc mở dashboard) — khi bị
pause, lần gọi API đầu tiên sau đó sẽ chờ ~60s để Supabase khởi động lại compute.
([nguồn](https://www.itpathsolutions.com/supabase-free-tier-limits)) — cân nhắc nếu
demo cho giảng viên sau một kỳ nghỉ dài, nên "đánh thức" DB trước (mở dashboard rồi
gọi thử 1 API) chứ đừng demo trực tiếp ngay.

### Hai loại connection string — dùng đúng chỗ, nếu không sẽ lỗi ngẫu nhiên

Supabase không cho app nối thẳng vào Postgres — mọi kết nối đi qua **Supavisor**
(pooler), có 2 chế độ:

|            | Transaction Pooler (cổng 6543)                                                                                                                                                                      | Direct / Session (cổng 5432)                         |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Dùng cho  | App runtime (FastAPI, nhiều request ngắn/đồng thời)                                                                                                                                             | Alembic migration (DDL, chạy không thường xuyên) |
| Ưu điểm | Chia sẻ connection giữa nhiều client, hiệu quả cao                                                                                                                                              | Giữ 1 connection riêng, ổn định cho DDL          |
| Hạn chế  | **Không hỗ trợ prepared statement** — nếu không tắt statement cache ở driver, sẽ gặp lỗi `prepared statement "..." already exists` ngẫu nhiên khi có nhiều request cùng lúc | Không phù hợp cho traffic lớn/đồng thời        |

Đây không phải lý thuyết suông — là lỗi thật nhiều người gặp khi ghép SQLAlchemy +
asyncpg + Supavisor transaction mode
([nguồn 1](https://supabase.com/docs/guides/troubleshooting/supavisor-and-connection-terminology-explained-9pr_ZO),
[nguồn 2](https://github.com/supabase/supabase/issues/39227)). Code trong
`src/backend/db/base.py` đã xử lý đúng: `statement_cache_size=0` +
`prepared_statement_cache_size=0` trong `connect_args`, và `NullPool` (để Supavisor tự
quản lý pool, app không chồng thêm 1 lớp pool nữa).

→ **App dùng `DATABASE_URL` = Transaction Pooler URL (cổng 6543).**
→ **Alembic dùng `DATABASE_URL_MIGRATIONS` = Direct Connection URL (cổng 5432).**
Để trống `DATABASE_URL_MIGRATIONS` thì Alembic tự dùng lại `DATABASE_URL` (đủ cho
local dev SQLite, không đủ tối ưu cho Postgres — nên set khi deploy thật).

## 2. Schema (ERD)

```mermaid
erDiagram
    users ||--o{ auth_tokens : "có nhiều token"
    users ||--o{ ride_sessions : "có nhiều phiên"
    ride_sessions ||--o{ bookings : "có thể tạo nhiều lần đặt"
    bookings ||--o| trips : "1 booking = 1 trip mô phỏng"
    ride_sessions ||--o{ handoffs : ""
    ride_sessions ||--o{ calls : ""
    ride_sessions ||--o{ conversation_events : ""

    users {
        string id PK
        string full_name
        string phone UK
        string password_hash
        string role
        timestamptz created_at
    }
    auth_tokens {
        string token PK
        string user_id FK
        string session_id "nullable, gắn sau khi tạo ride_session"
        timestamptz issued_at
        timestamptz expires_at
    }
    ride_sessions {
        string id PK
        string call_id
        string user_id FK
        string status
        string channel
        json pickup
        json destination
        string vehicle_type
        string confirmation_status
        int failed_count
        string booking_id "soft-ref, không FK cứng — xem mục 3"
        bool handoff_triggered
        string current_step
        timestamptz created_at
        timestamptz ended_at
    }
    bookings {
        string id PK
        string session_id FK
        string idempotency_key UK
        json pickup
        json destination
        string status
        int estimated_fare
        string currency
        int eta_minutes
        timestamptz created_at
    }
    trips {
        string id PK
        string booking_id FK, UK
        string status
        int eta_minutes
        timestamptz updated_at
    }
    handoffs {
        string id PK
        string session_id FK
        string reason
        string summary
        string status
    }
    calls {
        string id PK
        string session_id FK
        string customer_phone_hash
        string status
    }
    conversation_events {
        int id PK
        string session_id FK
        string event_type
        json event_metadata
        timestamptz created_at
    }
```

**Quyết định thiết kế đáng chú ý:**

- **ID vẫn là string tự sinh** (`usr_xxxxxxxx`, `sess_xxxxxxxx`...) thay vì Postgres
  `UUID` type — khớp 100% với format `uuid4().hex[:N]` toàn bộ service hiện tại đang
  dùng, để API response không đổi field/format khi nối DB thật vào sau này.
- **`ride_sessions.booking_id` KHÔNG có foreign key cứng** (chỉ là string thường) —
  vì 2 bảng phụ thuộc vòng lẫn nhau (`ride_sessions.booking_id` ↔
  `bookings.session_id`): session tạo trước (chưa có booking), booking tạo sau (khi
  khách xác nhận, luôn tham chiếu 1 session đã tồn tại), rồi mới quay lại set
  `booking_id` lên session. Ràng buộc FK 2 chiều ở đây tốn công migrate hơn lợi ích
  thực tế đem lại.
- **`trips` tách khỏi `bookings`** dù hiện là quan hệ 1-1 — vì `TripStatusDTO` hiện
  có field khác `BookingResponseDTO` (không có `currency`/`estimated_fare`) và về mặt
  nghiệp vụ, trip là quá trình *sau* khi có booking, tách bảng giúp mở rộng sau này
  (nhiều trip thất bại/retry cho 1 booking) không cần migrate lại.
- **`conversation_events`** — chưa service nào ghi vào (schema có nhưng logic chưa
  dùng), thêm sẵn để khi cần audit/debug hội thoại thì chỉ cần viết code ghi log, không
  phải chạy thêm 1 migration nữa.

## 3. Code đã có sẵn (verify được ngay, không cần Supabase)

| File                                                                                     | Vai trò                                                                                                                                                               |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/backend/db/base.py`                                                               | Engine/session async,`to_async_url`/`to_sync_url` (tự chuyển `postgresql://` ↔ `postgresql+asyncpg://`/`+psycopg2://`), `get_db()` (FastAPI dependency) |
| `src/backend/db/models.py`                                                             | 8 ORM model khớp schema ở mục 2                                                                                                                                     |
| `alembic.ini` + `migrations/env.py` + `migrations/versions/0001_initial_schema.py` | Migration đầu tiên, tạo đủ 8 bảng                                                                                                                               |

**Đã verify thật** (không phải suy đoán):

- `alembic upgrade head` chạy thành công, tạo đủ bảng trên SQLite local.
- `alembic check` — **"No new upgrade operations detected"**: `models.py` và migration khớp tuyệt đối, không lệch schema.
- Insert + query round-trip qua async engine thật (`AsyncSession`, không mock) cho `User`/`RideSession`/`AuthToken` — chạy đúng, default field (`current_step="START"`, `vehicle_type="4_SEAT"`...) áp dụng đúng.

Toàn bộ verify trên dùng SQLite (`aiosqlite`) — không cần tài khoản Supabase để chạy
`pytest`/dev local, giữ đúng nguyên tắc "test không gọi network thật" đã áp dụng cho
Voice AI (`tests/test_voice/fake_providers.py`). Khi deploy, chỉ cần đổi `DATABASE_URL`
sang connection string Supabase thật — không cần sửa code.

**Chưa làm (việc tiếp theo, không nằm trong phần "database" mà là "nối service vào
DB"):** `AuthService`/`SessionService`/`BookingService`/... hiện vẫn đang lưu bằng
dict RAM, CHƯA gọi tới `src/backend/db/*`. Lý do tạm dừng ở đây: `src/backend/services/ auth_service.py` và `src/backend/api/routes/sessions.py` đang có thay đổi khác diễn ra
đồng thời (thêm token-session binding) — nối DB vào ngay lúc này dễ đụng/ghi đè công
việc đó. Sẽ làm ngay sau khi việc kia ổn định — xem phần hỏi riêng ở cuối tin nhắn.

## 4. Hướng dẫn tạo Supabase project — từng bước

### Bước 1 — Tạo tài khoản & project

1. Vào https://supabase.com → **Start your project** → đăng nhập bằng GitHub (khuyên
   dùng, để sau này quản lý theo tổ chức team dễ hơn nếu cần).
2. **New organization** (nếu chưa có) → đặt tên bất kỳ, chọn **Free** plan.
3. **New project**:
   - **Name**: `alosm-voice` (hoặc tên bạn muốn).
   - **Database Password**: bấm **Generate a password** → **lưu lại ngay** (chỉ hiện 1
     lần, mất thì phải reset). Đây chính là phần điền vào `[PASSWORD]` ở connection
     string bước sau.
   - **Region**: chọn gần người dùng thật nhất — dự án này target VN nên chọn
     `Southeast Asia (Singapore)`.
   - **Pricing Plan**: Free.
4. Bấm **Create new project** — chờ ~2 phút để Supabase khởi tạo.

### Bước 2 — Lấy 2 connection string

1. Trong project vừa tạo, bấm nút **Connect** (góc trên, cạnh tên project).
2. Tab **App Frameworks** hoặc mục **Connection String** — sẽ thấy các lựa chọn:
   - **Transaction pooler** (cổng `6543`) → copy string này cho `DATABASE_URL`.
   - **Direct connection** hoặc **Session pooler** (cổng `5432`) → copy cho
     `DATABASE_URL_MIGRATIONS`.
3. Cả 2 string có dạng:
   ```
   postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```

   Thay `[YOUR-PASSWORD]` bằng mật khẩu đã lưu ở Bước 1.

### Bước 3 — Điền vào `.env`

Thêm 2 dòng sau vào `.env` (file thật, không commit — đã có trong `.gitignore`):

```env
DATABASE_URL=postgresql://postgres.xxxx:MẬT_KHẨU@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
DATABASE_URL_MIGRATIONS=postgresql://postgres.xxxx:MẬT_KHẨU@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
```

(2 dòng mẫu tương ứng đã thêm vào `.env.example` — không có mật khẩu thật, an toàn để
commit.)

### Bước 4 — Chạy migration lên Supabase thật

```bash
python -m alembic upgrade head
```

Vào tab **Table Editor** trên dashboard Supabase, xác nhận thấy đủ 8 bảng: `users`,
`auth_tokens`, `ride_sessions`, `bookings`, `trips`, `handoffs`, `calls`,
`conversation_events`.

### Bước 5 — Kiểm tra kết nối từ app

```bash
python -c "
import asyncio
from src.backend.db.base import get_session_factory
from sqlalchemy import text

async def check():
    async with get_session_factory()() as db:
        result = await db.execute(text('SELECT 1'))
        print('Kết nối Supabase OK:', result.scalar())

asyncio.run(check())
"
```

In ra `Kết nối Supabase OK: 1` nghĩa là app đã nối được tới Supabase thật qua
Transaction Pooler.

### (Tuỳ chọn) Row Level Security

Supabase bật RLS mặc định cho bảng tạo qua dashboard, nhưng bảng tạo qua Alembic (như
ở đây) **không tự động bật RLS**. Vì app luôn nối bằng 1 connection string chung (dùng
chung 1 "service" identity, không phải qua Supabase Auth JWT của từng end-user), RLS
không áp dụng được theo đúng mô hình Supabase thiết kế (RLS dựa vào `auth.uid()` từ
JWT của Supabase Auth, mà project này tự làm auth riêng — xem `auth_service.py`) — có
thể bỏ qua an toàn ở giai đoạn này. Nếu sau này chuyển sang dùng Supabase Auth thay vì
tự viết `AuthService`, RLS mới thực sự cần thiết.

## 5. Sources

- [Connect to your database | Supabase Docs](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supavisor and Connection Terminology Explained](https://supabase.com/docs/guides/troubleshooting/supavisor-and-connection-terminology-explained-9pr_ZO)
- [asyncpg prepared statement errors with Supabase poolers (GitHub issue)](https://github.com/supabase/supabase/issues/39227)
- [Supabase Free Tier Limits 2026 — Hidden Pauses &amp; Caps](https://www.itpathsolutions.com/supabase-free-tier-limits)
