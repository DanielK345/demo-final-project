# MUST DO

Việc dưới đây **không thể** hoàn thành chỉ bằng code trong repo này — cần quyết định
sản phẩm/kiến trúc từ team, hoặc credential/tài khoản bên ngoài. Đây là kết quả rà
soát toàn bộ Frontend ↔ Backend ngày 13/08/2026 (xem báo cáo đầy đủ trong hội thoại /
`capnhat.md`). Mọi phần **có thể** tự code được đã được code trực tiếp, không đưa vào
đây (xem danh sách "Đã implement/fix" trong báo cáo cuối).

---

## 1. ~~Các trang UI "đa trang" chưa được route tới~~ — ĐÃ GIẢI QUYẾT (13/08/2026)

**Cập nhật:** Theo yêu cầu trực tiếp của user ("lấy lại code tất cả các trang của
frontend các màn bị cho là rác và tự động hoàn thiện toàn bộ cả fe và be tương ứng"),
6 trang này đã được route lại vào `app/router/index.tsx` (lồng trong `AppLayout` —
Sidebar/Topbar/MobileNav, vốn đã được build sẵn cho đúng việc này) và nối vào dữ liệu
BE thật (không còn `MOCK_*`/`setTimeout` giả):

- **HomePage** — tên chào thật + 2 chuyến gần đây thật.
- **BookingPage** — "Xác nhận đặt xe" đi qua đúng dialogue engine thật (Core Agent) đã
  test kỹ, không xây đường đặt xe riêng.
- **TrackingPage** — poll `GET /api/v1/trips/status` mỗi 4s, tài xế/trạng thái mô
  phỏng ổn định (seed theo booking_id, không random mỗi lần gọi như code cũ).
- **ActivityPage** — `GET /api/v1/bookings` thật, đã xoá `mockData.ts`.
- **ProfilePage** — tên/SĐT/role thật từ `/auth/me`.
- **PaymentPage (Cài đặt)** — `GET/PUT /api/v1/users/me/settings` thật, đổi mật khẩu
  thật qua `POST /api/v1/auth/change-password`.

`/login` giữ nguyên đứng riêng. **Cập nhật 14/08/2026:** `/assistant` không còn là
trang riêng nữa — đã thay bằng nút nổi + popup (`VoiceAIButton`/`VoiceAssistantPopup`)
khả dụng ở mọi trang, xem mục 7 bên dưới. `feature/customer-call-ui`
(nhánh remote riêng, `frontend/` — `CustomerUI.tsx`/`OperatorUI.tsx`) **không bị đụng
tới** — vẫn là hướng đi độc lập của team, không liên quan tới `src/frontend/`.

### Còn lại — cần quyết định/thao tác thủ công (không tự code được)

1. **Ví AloSM Pay / thẻ thanh toán** (`ProfilePage`) — chưa có khái niệm ví/thanh toán
   nào ở Backend. Hiện hiển thị trạng thái rỗng trung thực ("Chưa liên kết phương thức
   thanh toán nào") thay vì số dư/thẻ giả. Cần Payment Gateway thật — xem mục 2 bên
   dưới.
2. **Ưu đãi/coupon** (`ProfilePage`) — tương tự, chưa có hệ thống coupon/loyalty nào.
   Hiện hiển thị trạng thái rỗng trung thực. Cần quyết định nghiệp vụ (loại ưu đãi,
   điều kiện áp dụng) trước khi code được.
3. **2FA thật** (`PaymentPage`) — toggle đã persist lựa chọn thật qua API, nhưng
   **CHƯA enforce** ở bước đăng nhập (cần TOTP hoặc SMS OTP — xem mục 4 bên dưới). UI
   đã ghi rõ "sắp ra mắt", không giả vờ đã bảo mật hơn.

### Cách kiểm tra

Đã verify: đăng nhập → vào từng trang (Home/Booking/Tracking/Activity/Payment/
Profile) qua Sidebar, xác nhận dữ liệu hiển thị đến từ API thật (đã test trực tiếp
qua curl với server đang chạy thật, không phải chỉ unit test). Muốn tự kiểm tra lại:
mở Network tab khi dùng các trang này, xác nhận có request thật tới `/api/v1/bookings`,
`/api/v1/trips/status`, `/api/v1/users/me/settings` — không còn `MOCK_*`/`mockData.ts`.

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

## 7. Voice AI popup (14/08/2026): field/luồng chưa có trong hợp đồng backend thật

### Bối cảnh

Đã refactor Voice AI từ trang riêng `/assistant` thành nút nổi + popup
(`VoiceAIButton`/`VoiceAssistantPopup`, mounted trong `AppLayout`) khả dụng ở mọi
trang, gồm Mode A (chat/text), Mode B (gọi thoại thu nhỏ), `BookingConfirmationModal`
(xác nhận trước khi đặt — đúng `BookingStep.CONFIRM` thật, đã verify qua server thật:
gửi "Xác nhận đặt xe" tạo booking thật, trả về `booking_lifecycle_status: SUCCESS`),
`BookingSuccessModal`. Trong lúc làm, phát hiện vài chỗ **spec đề bài yêu cầu nhưng
backend thật chưa có dữ liệu/luồng tương ứng** — liệt kê ở đây thay vì tự bịa field
rỗng hay giả lập hành vi không thật.

### Vì sao chưa thể tự làm

1. **`passenger_count`/loại dịch vụ (service tier)/`pickup_time`/ghi chú** — đề bài
   yêu cầu thẻ xác nhận hiển thị đủ các field này, nhưng `BookingProgress` thật (xem
   `SessionService._booking_progress()`) chỉ có `pickup`/`destination`/`vehicle_type`/
   `fare_amount`/`currency`. `BookingConfirmationModal` hiện chỉ hiển thị đúng những
   field có thật, không vẽ thêm field trống/giả. Core Agent hiện cũng không có khái
   niệm "service tier" tách khỏi `vehicle_type` (`VehicleType` đã gộp luôn: xe máy/ô
   tô 4 chỗ/ô tô 7 chỗ), và `AgentState`/`BookingData` chưa có field số hành khách,
   giờ đón hay ghi chú tự do.
2. **Nút "Hủy" ở thẻ xác nhận** — cố tình bỏ (đề bài ghi "có thể thêm", không bắt
   buộc). Đã đọc `src/agents/workflows/booking.py` bước `CONFIRM`: chưa có nhánh từ
   chối/hủy rõ ràng — bất kỳ câu trả lời nào không khớp mẫu xác nhận đều chỉ nhận lại
   "Bạn vui lòng xác nhận đồng ý hoặc nói thông tin cần sửa." Thêm nút "Hủy" gửi 1 câu
   lệnh mà agent không thật sự hiểu như một lệnh hủy sẽ là giả vờ có tính năng không
   có thật.
3. **Transcript trong Voice Call Mode cập nhật theo từng lượt, không phải theo từng
   chữ khi đang nói** — `/api/v1/voice/turn` là REST 1-lần-1-lượt (ghi âm xong mới gửi
   cả đoạn), không phải WebSocket streaming. Đây là hành vi thật vốn có của
   `sendVoiceTurn`/`useVoiceRecorder` (không phải lỗi mới), giữ nguyên — không giả lập
   caption thời gian thực khi backend không thật sự trả về theo thời gian thực.

### Cần làm (nếu muốn có đủ field/luồng như đề bài mô tả)

1. Bổ sung `passenger_count`/ghi chú/giờ đón vào `AgentState.collected_data["booking"]`
   + `BookingProgress` ở backend (`src/agents/workflows/booking.py`,
   `session_service.py`) trước khi frontend có thể hiển thị thật.
2. Nếu cần "Hủy" tường minh ở bước CONFIRM: thêm 1 nhánh REJECT rõ ràng trong
   `booking.py` (hiện `_REJECT_TERMS` có tồn tại ở `understanding/rules.py` nhưng
   không được dùng riêng ở bước CONFIRM).
3. Nếu cần caption thời gian thực khi đang nói: cần đổi `/api/v1/voice/turn` sang
   streaming (WebSocket/SSE) — thay đổi kiến trúc lớn hơn nhiều so với phạm vi UI.

### Cách kiểm tra

Đã verify qua server thật (không chỉ đọc code): đăng ký user mới → tạo phiên → gửi
"Tôi muốn đặt xe từ Vincom Đồng Khởi đến Landmark 81" → "Xe máy" → nhận đúng
`current_workflow: RIDE_BOOKING`, `current_step: CONFIRM`, `fare_amount: 47200` → gửi
"Xác nhận đặt xe" → nhận `booking_lifecycle_status: SUCCESS` + `booking_id` thật.

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
| 7 | Field/luồng còn thiếu ở popup Voice AI | Không — popup hiển thị đúng field thật hiện có, đủ chạy demo |
