# Tiến trình dự án — AloSM Voice

Tài liệu sống, cập nhật theo phiên làm việc. Lịch sử Voice AI trước 13/08/2026 xem
[`docs/reports/2026-08-13-voice-ai-progress.md`](docs/reports/2026-08-13-voice-ai-progress.md)
(đã archive). File này bắt đầu từ phần Database/Supabase trở đi, cùng ngày.

**Branch làm việc:** `feature/voice-ai` (toàn bộ, không đụng branch khác, không merge).

---

## 1. Database Supabase — thiết kế + hạ tầng

- Thiết kế schema 8 bảng (`users`, `auth_tokens`, `ride_sessions`, `bookings`,
  `trips`, `handoffs`, `calls`, `conversation_events`) — ERD + lý do thiết kế đầy đủ
  tại [`docs/database_supabase.md`](docs/database_supabase.md).
- `src/backend/db/base.py` + `models.py`: engine async, tuned cho Supabase
  Transaction Pooler (tắt prepared statement cache — tránh lỗi kinh điển
  asyncpg+Supavisor).
- `alembic.ini` + `migrations/`: đã verify thật (`alembic upgrade head` +
  `alembic check` khớp 100%, round-trip qua async engine thật trên SQLite local).
- **Còn lại (cần bạn):** tạo project Supabase thật, dán connection string vào `.env`
  — xem hướng dẫn 5 bước trong `docs/database_supabase.md`.
- **Chưa làm (việc tiếp theo, không phải lỗi):** `AuthService`/`SessionService`/
  `BookingService` vẫn lưu bằng dict RAM, chưa nối vào DB thật.

## 2. Xung đột Voice AI — 2 hệ thống song song

Phát hiện: 1 commit khác (`test_speech_model`, DanielK345) ghi đè hoàn toàn route
Voice AI cũ, làm app không boot được. Khôi phục xong thì phát hiện tiếp: Frontend đã
nối thật vào route bị gỡ đó (`AssistantPage.tsx` → `features/voice/api.ts` →
`POST /voice/turn`). Giải pháp cuối: **cả 2 hệ thống cùng tồn tại** trong
`src/backend/api/routes/voice.py` (khác path, không đè nhau) — xem
[`docs/voice-ai/architecture-note-2-voice-systems.md`](docs/voice-ai/architecture-note-2-voice-systems.md).
Team cần chọn 1 để giữ lâu dài (mustdo.md không liệt kê vì không chặn hoạt động hiện
tại, nhưng nên dọn sau).

## 3. Tổ chức lại project

Root sạch hơn (bỏ file rác `=0.5.0`, viết lại `README.md` — trước đó rỗng từ lúc tạo),
gom docs Voice AI vào `docs/voice-ai/`, báo cáo tiến độ cũ vào `docs/reports/`, xoá
code chết đã verify kỹ (`src/agents/nodes/`, `src/agents/policies/` — scaffold khoá
học chưa từng hoàn thiện; cụm chat UI cũ `ChatWindow`/`ChatInput`/`MessageBubble`/
`VoiceVisualizer`/`hooks.ts`/`types.ts` — đã bị thay bởi UI mới trong
`AssistantPage.tsx`). Phát hiện thêm bug thật: `data/gazetteer/place_names.json`
(dữ liệu Voice AI) bị `.gitignore` nuốt mất, chưa từng được commit — mọi clone khác
đều có gazetteer rỗng, lỗi âm thầm. Đã sửa.

## 4. Hoàn thiện 6 trang Frontend "mồ côi" + Backend tương ứng

6 trang tồn tại trong code nhưng không route nào trỏ tới (Home/Booking/Tracking/
Activity/Payment/Profile) — theo yêu cầu trực tiếp, đã route lại (lồng trong
`AppLayout` — Sidebar/Topbar/MobileNav vốn build sẵn cho việc này) và nối vào Backend
thật, không còn `MOCK_*`/`setTimeout` giả:

**Backend mới:** `GET /api/v1/bookings` (lịch sử theo user — mới hoàn toàn),
`GET/PUT /api/v1/users/me/settings` (mới), `POST /api/v1/auth/change-password` (nối
vào `AuthService.change_password` đã viết từ trước nhưng chưa dùng). Sửa bug thật:
`TripService.get_status()` trước trả `trip_id` random mỗi lần gọi — giờ mô phỏng ổn
định theo `booking_id` (tài xế/xe/biển số/trạng thái tiến triển theo thời gian). Phát
hiện thêm: `trips_router` định nghĩa sẵn nhưng **chưa từng được mount** — route đó
trước đây hoàn toàn không truy cập được.

**Frontend:** BookingPage đặt xe qua đúng dialogue engine thật (Core Agent) thay vì
xây đường riêng; TrackingPage poll trạng thái thật; ActivityPage lịch sử thật;
Profile/Home dữ liệu người dùng thật; Payment (Cài đặt) lưu thật + đổi mật khẩu thật.
Ví/coupon: chưa có backend nào cho việc này — hiện trạng thái rỗng trung thực thay vì
số dư/thẻ giả.

Verify thật qua server đang chạy (không chỉ unit test): đăng nhập → tạo session →
nhắn tin đặt xe → agent resolve địa điểm → xác nhận → booking tạo thật → xuất hiện ở
`/bookings` → `/trips/status` trả tài xế ổn định → đổi mật khẩu → đăng nhập lại bằng
mật khẩu mới. Tất cả đúng status code kỳ vọng.

## 5. QA toàn bộ chuyển màn/button (phiên này)

Rà soát có hệ thống mọi nút bấm và logic điều hướng của Frontend (không chỉ page,
cả `Sidebar`/`Topbar`/`MobileNav`/`AssistantPage` và các component con) — tìm được
**8 lỗi thật**, đã sửa hết:

| # | Lỗi | File | Sửa |
|---|---|---|---|
| 1 | Nav "Home" luôn sáng highlight bất kể đang ở trang nào (thiếu prop `end` của `NavLink` — path `"/"` match mọi path trong React Router v6/v7) | `Sidebar.tsx`, `MobileNav.tsx` | Thêm `end` |
| 2 | `NotFoundPage` (404) chữ gần như vô hình — dùng `text-slate-100`/`text-slate-400` (gần trắng) trong khi nền thật `#F8F9FB` (sáng) | `NotFoundPage.tsx` | Đổi màu chữ tối |
| 3 | Dropdown tài khoản: "Ví AloSM Pay" trỏ tới `/payment` (thực chất là trang Cài đặt), không phải chỗ có "Phương thức thanh toán" thật (`/profile`) | `Topbar.tsx` | Sửa `to="/profile"` |
| 4 | Nút chuông Thông báo bấm không có phản ứng gì (không có `onClick`) | `Topbar.tsx` | Thêm dropdown "Chưa có thông báo mới" |
| 5 | Nút Đăng xuất cũ **không xoá session** — token cũ vẫn hợp lệ sau khi "đăng xuất" | `Topbar.tsx` | Gọi `clearAuthSession()` |
| 6 | Filter "Tháng trước" ở Activity không lọc được gì — không có nhánh xử lý, rơi xuống `return true` giống "Tất cả" | `ActivityList.tsx` | Thêm lọc theo `created_at` (30 ngày) |
| 7 | Vào `/assistant` không có đường quay lại Home/Booking/... — chỉ có Đăng xuất (mất hết phiên) | `AssistantPage.tsx` | Thêm link "Trang chủ" (tạm thời — xem mục 6: sau đó thay hẳn bằng taskbar thật theo yêu cầu tiếp theo) |
| 8 | Khi hội thoại tự kết thúc (agent trả `END_SESSION`, vd khách nói "hủy"), code **đăng xuất khỏi cả tài khoản** — trong khi nút "Kết thúc phiên" tường minh chỉ reset hội thoại, không đăng xuất. 2 đường xử lý cùng 1 tình huống khác hẳn nhau | `AssistantPage.tsx` (2 chỗ) | Đồng bộ theo `handleEndSession` |

Cũng dọn thêm code chết phát hiện trong lúc audit (không dùng ở đâu, gây lỗi lint
thật `rules-of-hooks`): `features/booking/components/{LocationPicker,ServiceSelector,
BookingPanel}.tsx`, `features/booking/types.ts`, `components/ui/Input.tsx` — cụm UI
"chọn địa điểm" cũ, bị thay bởi input thường trong `BookingPage.tsx` hiện tại.

Bổ sung 1 việc hoàn thiện nhỏ: nút "Đặt lại chuyến này" (Activity/Home) giờ mở thẳng
modal xác nhận đặt xe (`openModal: true`) thay vì chỉ điền sẵn địa chỉ rồi phải bấm
thêm 1 lần — đúng với thiết kế `openModal` đã có sẵn trong `BookingPage.tsx`.

Và 1 lớp bảo vệ logic: `createBookingViaForm` (BookingPage) giờ chỉ gửi "Đúng" khi
agent thật sự đang ở bước `CONFIRM` — tránh gửi xác nhận mù quáng nếu agent hỏi lại
điều gì khác (địa điểm chưa rõ, loại xe chưa nhận diện được).

## 6. AssistantPage: taskbar thật, giao diện tối, lịch sử trò chuyện

Theo yêu cầu trực tiếp: trước đây `/assistant` đứng riêng ngoài `AppLayout`, chỉ có
1 link "Trang chủ" tự chế để quay lại — không phải taskbar thật. Đã sửa tận gốc:

- **Router**: `/assistant` giờ lồng trong `AppLayout` như mọi trang khác — có đầy đủ
  Sidebar/Topbar/MobileNav để chuyển màn, không còn đường cụt.
- **Giao diện tối**: khu vực trò chuyện (panel chính + `BookingProgressSidebar`) vẽ
  lại theo tông tối (`#0B0E11`, chữ trắng/slate sáng, nhấn `#00D1C1`) — nổi bật như 1
  "phòng trò chuyện" giữa dashboard sáng. Sidebar/Topbar/MobileNav giữ nguyên sáng
  (đồng bộ với mọi trang khác — đổi cả bộ khung sang tối là việc khác, lớn hơn nhiều,
  ngoài phạm vi yêu cầu lần này).
- **Voice-first**: nút mic đặt đầu tiên, to, nổi bật (gradient tối, phóng to khi đang
  ghi âm). Chat text gấp gọn phía sau nút "Hoặc nhắn tin" — vẫn dùng được đầy đủ,
  không phải bắt buộc nhìn thấy ngay như trước. (Lưu ý: trình duyệt bắt buộc phải có
  thao tác bấm của người dùng mới được xin quyền micro — không thể "tự chạy" mic mà
  không cần bấm gì, đây là giới hạn bảo mật trình duyệt, không phải thiếu sót.)
- **Lịch sử trò chuyện (tính năng mới)**: nút "Lịch sử trò chuyện" mở panel liệt kê
  toàn bộ session cũ của user (mới nhất trước, có preview + số tin nhắn), bấm vào 1
  session hiện popup toàn bộ nội dung dạng bong bóng chat dễ đọc.
  - Backend: `GET /api/v1/sessions/history` (list) + `GET /api/v1/sessions/history/
    {session_id}` (transcript) — đọc trực tiếp từ `logs/*.json`, nơi
    `ConversationLogger` (đã có sẵn từ trước, chưa từng được khai thác) ghi lại từng
    lượt hội thoại. Verify quyền sở hữu (user A không xem được lịch sử user B).
  - Phát hiện + sửa tác dụng phụ: mỗi lần `pytest` chạy, `SessionService.
    _conversation_logger` (class attribute dùng chung) ghi file log THẬT vào `logs/`
    — trước khi có tính năng này chỉ là rác vô hại, giờ sẽ LẪN VÀO lịch sử trò chuyện
    thật nếu ai chạy `pytest` trên máy đang chạy server thật. Thêm fixture
    `autouse` trong `tests/conftest.py` trỏ logger sang thư mục tạm (`tmp_path`) cho
    mọi test — không đụng `tests/test_backend/test_conversation_logger.py` (tự inject
    logger riêng, không phụ thuộc mặc định).

## 7. Trạng thái hiện tại (đã verify, tính đến mục 6)

- `pytest`: 262 passed / 4 skipped / 0 failed
- `tsc -b`: sạch
- `npm run build`: sạch
- `oxlint`: **sạch hoàn toàn** (2 warning tồn đọng từ trước — thuộc cụm code chết vừa
  xoá ở mục 5 — đã biến mất theo)
- Boot server thật: `/health`, `/api/v1/voice/health` đều 200
- `GET /api/v1/sessions/history` + `GET /api/v1/sessions/history/{id}`: verify thật —
  đăng nhập → gửi tin nhắn → xuất hiện trong list → xem transcript đúng nội dung →
  session không phải của mình trả 404 (không rò rỉ dữ liệu chéo user)

## 8. Việc còn lại (`mustdo.md` — cần người/credential thật)

1. Tạo project Supabase thật (database production).
2. Chọn 1 trong 2 hệ thống Voice AI để giữ lâu dài (không chặn, chỉ nên dọn sau).
3. Payment Gateway thật (VNPay/MoMo/Stripe) — nếu muốn Ví AloSM Pay hoạt động thật.
4. Coupon/loyalty — cần quyết định nghiệp vụ trước khi code.
5. 2FA thật (TOTP/SMS) — hiện chỉ persist lựa chọn, chưa enforce lúc đăng nhập.
6. `OPENAI_API_KEY` thật nếu muốn bật LLM hiểu ngôn ngữ tự nhiên đầy đủ.

## 9. Lệnh kiểm tra nhanh

```bash
# Backend
python -m pytest -q
uvicorn src.main:app --reload --port 8000

# Frontend
cd src/frontend
npx tsc -b && npm run build && npm run lint
npm run dev
```
