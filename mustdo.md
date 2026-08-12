# MUST DO

Việc dưới đây **không thể** hoàn thành chỉ bằng code trong repo này — cần quyết định
sản phẩm/kiến trúc từ team, hoặc credential/tài khoản bên ngoài. Đây là kết quả rà
soát toàn bộ Frontend ↔ Backend ngày 13/08/2026 (xem báo cáo đầy đủ trong hội thoại /
`capnhat.md`). Mọi phần **có thể** tự code được đã được code trực tiếp, không đưa vào
đây (xem danh sách "Đã implement/fix" trong báo cáo cuối).

---

## 1. Các trang UI "đa trang" chưa được route tới — cần quyết định sản phẩm

### Vì sao chưa thể tự làm

`react-router` (`src/frontend/src/app/router/index.tsx`) hiện chỉ mount 2 route:
`/login` và `/` (→ `AssistantPage`, trang chat/voice duy nhất). Toàn bộ các trang sau
**tồn tại trong code nhưng KHÔNG ai điều hướng tới được** (không có `<Route>` nào trỏ
tới, `AppLayout`/`Sidebar`/`Topbar`/`MobileNav` cũng không được mount ở đâu):

- `src/frontend/src/pages/Home/HomePage.tsx`
- `src/frontend/src/pages/Booking/BookingPage.tsx` (nút "Xác nhận đặt xe" hiện chỉ
  `setTimeout` giả lập, không gọi API thật)
- `src/frontend/src/pages/Tracking/TrackingPage.tsx` (tự ghi chú ngay trong UI:
  *"Đang chờ tích hợp GPS / WebSocket Backend API"*)
- `src/frontend/src/pages/Payment/PaymentPage.tsx` (thực chất là trang Cài đặt —
  thông báo/2FA/ngôn ngữ/giao diện — nút Lưu không gọi API nào)
- `src/frontend/src/pages/Profile/ProfilePage.tsx` (toàn bộ dữ liệu hardcode: tên,
  email, ngày sinh, số dư ví, thẻ Visa, ưu đãi)
- `src/frontend/src/pages/Activity/ActivityPage.tsx` + `features/activity/mockData.ts`
  (lịch sử chuyến đi hardcode 3 chuyến giả)

**Đây không phải bug — đây là code mồ côi (orphaned) từ lần scaffold đầu tiên**
(`e9115ca feat: scaffold initial frontend project structure`), bị bỏ lại khi flow
thật của sản phẩm chuyển sang mô hình chat/voice một trang (`AssistantPage` +
`/api/v1/sessions`, đã hoạt động đầy đủ — xem báo cáo).

Việc dựng Backend thật cho các trang này (ví, thanh toán, GPS tracking, coupon/loyalty,
lịch sử chuyến đi) là một khối lượng công việc lớn, đa domain, và **có rủi ro trùng
lặp/xung đột trực tiếp** với công việc khác của team: repo đang có nhánh remote
`feature/customer-call-ui` (`frontend/` — package.json riêng, `CustomerUI.tsx`,
`OperatorUI.tsx`) — rất có thể đây chính là câu trả lời của team cho "trải nghiệm đa
trang" này, làm theo hướng khác hẳn (React app riêng, không phải `src/frontend/`).

### Cần làm (quyết định của team, không phải của code)

1. Họp nhanh với người phụ trách `feature/customer-call-ui` / `feature/frontend-mvp`
   để thống nhất: sản phẩm cuối cùng là **chat/voice một trang** (hiện tại), **đa
   trang kiểu truyền thống** (Home/Booking/Tracking/Profile...), hay **cả hai** (dùng
   `feature/customer-call-ui` làm Operator/Customer UI riêng)?
2. Nếu quyết định giữ các trang `Booking/Tracking/Payment/Profile/Activity`:
   - Thêm route cho chúng vào `app/router/index.tsx`.
   - Backend cần thêm (theo đúng pattern in-memory MVP hiện có, KHÔNG cần DB thật
     ngay): `GET /api/v1/bookings` (lịch sử), `GET /api/v1/users/me/settings` +
     `PUT` (thông báo/ngôn ngữ/giao diện), mở rộng `TripService`/`BookingService` để
     trạng thái chuyến đi nhất quán theo `booking_id` thay vì random mỗi lần gọi.
   - Ví/thẻ thanh toán/coupon: xem mục 3 bên dưới (cần quyết định nghiệp vụ + có thể
     cần credential thật).
3. Nếu quyết định **xoá** các trang mồ côi này (không dùng nữa): xoá hẳn để tránh gây
   nhầm lẫn cho người sau — không nằm trong phạm vi tôi tự quyết vì đây là code người
   khác viết và có thể đang được dùng làm tham khảo thiết kế.

### Cách kiểm tra sau khi quyết định

Sau khi thêm route thật, vào từng trang, xác nhận dữ liệu hiển thị đến từ API (Network
tab có request thật, không còn `MOCK_*`/`mockData.ts`).

---

## 2. Payment Gateway thật (VNPay / MoMo / Stripe...)

### Vì sao chưa thể tự làm

Chỉ cần thiết **nếu** team chọn hồi sinh `PaymentPage`/ví AloSM Pay ở mục 1. Cần tài
khoản merchant thật (VNPay/MoMo cho thị trường VN, hoặc Stripe quốc tế) — không thể
tạo bằng code.

### Cần làm

1. Đăng ký tài khoản merchant (VNPay: https://sandbox.vnpayment.vn/devreg/ để lấy
   sandbox trước; MoMo: https://business.momo.vn/).
2. Lấy `Merchant ID`/`Secret Key` (VNPay) hoặc `Partner Code`/`Access Key`/`Secret Key`
   (MoMo) ở chế độ **sandbox** trước khi lên production.
3. Thêm vào `.env`:
   ```
   VNPAY_MERCHANT_ID=
   VNPAY_SECRET_KEY=
   VNPAY_RETURN_URL=http://localhost:5173/payment/callback
   ```
4. Code liên quan (sẽ cần tạo mới): `src/backend/services/payment_service.py`,
   `src/backend/api/routes/payments.py`.

### Cách kiểm tra

Thực hiện 1 giao dịch sandbox, xác nhận callback cập nhật đúng trạng thái booking.

---

## 3. GPS / Maps Provider thật cho Tracking

### Vì sao chưa thể tự làm

`TrackingPage` cần vị trí tài xế theo thời gian thực. Không có tài xế/app tài xế thật
trong phạm vi capstone này → cần quyết định: **mô phỏng nâng cao** (code được, không
cần key ngoài — có thể tự làm nếu team yêu cầu) hay **tích hợp Maps provider thật**
(Google Maps Platform / Mapbox — cần API key + billing).

### Cần làm (nếu chọn tích hợp thật)

1. Tạo project tại https://console.cloud.google.com/, bật **Maps JavaScript API** +
   **Directions API**, tạo API key, giới hạn theo domain.
2. Thêm vào `.env`: `GOOGLE_MAPS_API_KEY=`
3. Thêm vào `.env.example` tương ứng (không commit key thật).

### Cách kiểm tra

Mở `TrackingPage`, xác nhận marker tài xế di chuyển theo dữ liệu thật/API thật, không
còn `top-1/2 left-1/3` cố định như hiện tại.

---

## 4. SMS/Email Provider cho 2FA & thông báo thật

### Vì sao chưa thể tự làm

`PaymentPage` có toggle "Xác thực 2 yếu tố (2FA)" và "Email/SMS Notifications" — hiện
chỉ là state React cục bộ. Bật 2FA/thông báo thật qua SMS cần nhà cung cấp (Twilio/
eSMS/Speed SMS cho VN); qua Email cần SMTP hoặc SendGrid/Mailgun.

### Cần làm

1. Đăng ký 1 trong các dịch vụ trên, lấy API key.
2. Thêm vào `.env`:
   ```
   SMS_PROVIDER_API_KEY=
   SMTP_HOST=
   SMTP_PORT=
   SMTP_USER=
   SMTP_PASSWORD=
   ```
3. (2FA dạng TOTP — vd Google Authenticator — **không cần dịch vụ ngoài**, có thể tự
   code bằng thư viện `pyotp` nếu team muốn ưu tiên việc này trước SMS/Email thật —
   nói rõ nếu muốn tôi làm tiếp phần này.)

### Cách kiểm tra

Bật 2FA/thông báo, xác nhận nhận được mã/thông báo thật qua kênh đã cấu hình.

---

## 5. Database thật — ĐÃ CHỌN Supabase, hạ tầng đã xong, còn 2 việc cần bạn

### Đã tự làm (code + verify thật, xem `docs/database_supabase.md` để có thiết kế đầy đủ + ERD)

- `src/backend/db/base.py`, `src/backend/db/models.py` — engine async + 8 ORM model
  (`users`, `auth_tokens`, `ride_sessions`, `bookings`, `trips`, `handoffs`, `calls`,
  `conversation_events`), tuned sẵn cho Supabase Transaction Pooler (tắt prepared
  statement cache — tránh lỗi kinh điển asyncpg + Supavisor).
- `alembic.ini` + `migrations/` — migration đầu tiên. Đã verify thật: `alembic upgrade
  head` chạy được, `alembic check` báo khớp 100% với models, insert/query round-trip
  qua async engine thật chạy đúng (tất cả trên SQLite local, không cần Supabase để
  verify hạ tầng).
- `requirements.txt`: thêm `asyncpg`, `aiosqlite`.
- `.env.example`: thêm `DATABASE_URL`/`DATABASE_URL_MIGRATIONS` mẫu cho Supabase.

### Còn lại — cần bạn (không thể tự làm)

1. **Tạo project Supabase thật** (cần tài khoản) — làm theo đúng 5 bước ở
   `docs/database_supabase.md` mục 4: đăng ký → tạo project → lấy 2 connection string
   (Transaction pooler cổng 6543 + Direct connection cổng 5432) → điền vào `.env` →
   chạy `python -m alembic upgrade head`.

### Việc tiếp theo (tôi sẽ làm, không phải việc của bạn) — nối service vào DB

`AuthService`/`SessionService`/`BookingService`/`TripService` hiện **vẫn** lưu bằng
dict RAM, chưa gọi tới `src/backend/db/*` — hạ tầng đã sẵn sàng nhưng chưa "nối dây".
Tạm hoãn bước này vì đúng lúc rà soát thì phát hiện các file service đó (đặc biệt
`auth_service.py`, `api/routes/sessions.py`, `api/routes/voice.py`) đang có thay đổi
khác diễn ra song song từ nhánh `test_speech_model` — nối DB ngay lúc này dễ đụng
việc đang dở của người khác. Sẽ làm ngay khi việc đó ổn định.

### Cách kiểm tra

Sau khi có Supabase + chạy migration: vào tab **Table Editor** trên dashboard Supabase,
xác nhận thấy đủ 8 bảng. Sau khi service được nối dây (bước tiếp theo): restart server,
xác nhận user/session/booking vẫn còn sau khi restart (thay vì mất sạch như hiện tại).

---

## 6. OPENAI_API_KEY thật (bật LLM hiểu ngôn ngữ tự nhiên cho Agentic Core)

### Vì sao chưa thể tự làm

`AGENT_LLM_ENABLED=false` mặc định — khi tắt, hệ thống dùng `RuleBasedUnderstanding`
(rule-based, không cần key, đã hoạt động). Bật `AGENT_LLM_ENABLED=true` để dùng
`OpenAIUnderstandingAdapter` (`src/agents/understanding/openai.py`) cần
`OPENAI_API_KEY` thật của team — không thể tạo hộ.

### Cần làm

1. Lấy key tại https://platform.openai.com/api-keys.
2. Điền vào `.env`: `OPENAI_API_KEY=sk-...` và `AGENT_LLM_ENABLED=true`.

### Cách kiểm tra

Gửi 1 câu hỏi lệch chuẩn (vd nói ngọng/thiếu chữ) qua `AssistantPage`, xác nhận log
backend cho thấy `OpenAIUnderstandingAdapter` được gọi (không rơi vào fallback rule).

---

## Tổng kết mức ưu tiên

| # | Việc | Có bắt buộc để demo hiện tại chạy được không? |
|---|------|------------------------------------------------|
| 1 | Quyết định số phận trang đa-trang | Không — flow chat/voice hiện tại đã chạy đủ, không phụ thuộc |
| 2 | Payment Gateway thật | Không — chỉ cần nếu hồi sinh mục 1 |
| 3 | Maps Provider thật | Không — như trên |
| 4 | SMS/Email/2FA thật | Không — toggle demo, không chặn luồng chính |
| 5 | Database thật | Không cho demo/capstone — **có** trước khi lên production thật |
| 6 | OPENAI_API_KEY thật | Không — rule-based fallback đã hoạt động tốt |
