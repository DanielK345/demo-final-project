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

> **Cập nhật (mục 7):** `createBookingViaForm` và modal xác nhận riêng của
> BookingPage đã bị **gỡ bỏ hoàn toàn** — mọi nút đặt xe giờ nối thẳng vào AI
> Assistant thay vì có luồng đặt xe riêng. Đoạn trên giữ lại để biết lý do thiết kế
> ban đầu.

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

## 7. "AI đặt xe ngay" + Giao diện tối toàn site

Theo yêu cầu trực tiếp: (1) mọi nút "Đặt ngay"/"Đặt xe ngay"/"Chọn dịch vụ" phải đổi
tên và nối THẲNG vào Agentic AI Assistant thay vì tự bấm chọn/điền form; (2)
AssistantPage đang tối là sai — quay lại giao diện sáng như mọi trang; (3) xây giao
diện tối cho TOÀN BỘ website, bật/tắt qua Settings.

- **1 đường đặt xe duy nhất — qua AI Assistant**: gỡ bỏ hoàn toàn modal "Confirm
  Booking" tự điền pickup/dropoff của BookingPage (và `createBookingViaForm`, xem
  ghi chú ở mục 5). Mọi nút đặt xe trong app — hero "Đặt xe ngay" + 3 card dịch vụ ở
  HomePage, 3 card dịch vụ ở BookingPage, "Đặt lại chuyến này" ở ActivityList/
  HomePage, "Đặt xe ngay" ở trạng thái rỗng của TrackingPage — đổi nhãn thành
  **"AI đặt xe ngay"** / **"AI đặt lại chuyến này"** và điều hướng sang `/assistant`
  kèm `state.prefill` (câu mô tả chuyến đi bằng ngôn ngữ tự nhiên, vd `"Tôi muốn đặt
  xe AloSM Premium loại hạng sang."`). `AssistantPage` tự gửi câu này ngay khi có
  session — dùng đúng cơ chế quick-chip có sẵn (`send()`), không phải luồng riêng.
  Đã verify qua server thật: các câu prefill (cả có dấu và tên thương hiệu "AloSM
  Taxi/Premium") được Core Agent hiểu và khởi động đúng `RideBookingWorkflow`.
- **AssistantPage quay lại giao diện sáng**: panel trò chuyện + `BookingProgressSidebar`
  vẽ lại nền trắng/viền xám nhạt như mọi trang khác — không còn tự ý tối riêng 1
  trang. Taskbar thật, voice-first, lịch sử trò chuyện (mục 6) giữ nguyên logic,
  chỉ đổi màu.
- **Giao diện tối cho TOÀN BỘ site (mới)**: `ThemeProvider` (`app/providers/
  ThemeProvider.tsx` + `theme-context.ts` + `useTheme.ts`) áp class `dark` lên
  `<html>`, kết hợp biến thể `dark:` của Tailwind v4 (`@custom-variant dark` trong
  `index.css`). Nguồn sự thật kép: `localStorage` (`alosm_theme`, áp ngay cả trước
  khi đăng nhập, đọc đồng bộ trong `index.html` để tránh nháy sáng→tối lúc tải
  trang) + backend (`GET/PUT /users/me/settings`, field `theme` — đã có sẵn từ
  trước nhưng CHƯA từng thật sự đổi giao diện, chỉ lưu vô tri). Bật/tắt tại
  Cài đặt (Settings) → mục "Giao diện" → bấm "Sáng"/"Tối": đổi ngay lập tức + lưu
  backend để đồng bộ khi đăng nhập trên thiết bị khác.
  - Thêm biến thể `dark:` cho TOÀN BỘ trang/khung dùng chung: `AppLayout`,
    `Sidebar`, `Topbar`, `MobileNav`, `HomePage`, `BookingPage`, `ActivityPage` +
    `ActivityList`, `ProfilePage`, `TrackingPage` + `TrackingCard`, `PaymentPage`
    (Cài đặt), `NotFoundPage`, `LoginPage` + `LoginForm`, và các modal/panel của
    AssistantPage (`HistoryPanel`, `TranscriptModal`, `BookingSuccessPanel`,
    `LlmStatusNote`) — trước đó 2 modal lịch sử trò chuyện bị hard-code tối cứng,
    giờ theo đúng theme chung.
  - Tách `useTheme` ra khỏi `ThemeProvider.tsx` (file riêng `useTheme.ts` +
    `theme-context.ts`) — gộp chung sẽ vi phạm quy tắc Fast Refresh của Vite
    (oxlint `react(only-export-components)`), tránh dùng eslint-disable để che.
  - Verify qua server thật: `PUT /users/me/settings {"theme":"dark"}` → `GET` trả
    đúng `"theme":"dark"`, round-trip chính xác.

## 8. Trạng thái hiện tại (đã verify, tính đến mục 7)

- `pytest`: 262 passed / 4 skipped / 0 failed (backend không đổi ở mục 7)
- `tsc -b`: sạch
- `npm run build`: sạch
- `oxlint`: **sạch hoàn toàn**, 0 warning
- Boot server thật: `/health`, `/api/v1/voice/health` đều 200
- `GET /api/v1/sessions/history` + `GET /api/v1/sessions/history/{id}`: verify thật —
  đăng nhập → gửi tin nhắn → xuất hiện trong list → xem transcript đúng nội dung →
  session không phải của mình trả 404 (không rò rỉ dữ liệu chéo user)
- Settings theme round-trip: `PUT`/`GET /users/me/settings` verify thật qua server
- Câu "AI đặt xe ngay" prefill: verify thật qua server — Core Agent nhận đúng, khởi
  động `RideBookingWorkflow`

## 9. Nhập Core Agent + RAG thật từ nhánh `feature/agentic-ai`

Yêu cầu: phân tích toàn bộ phần agentic agent/RAG trên `origin/feature/agentic-ai` và
đưa vào `feature/voice-ai`, không đụng branch nào khác, không xung đột với logic hiện
có. Đây là công việc lớn nhất session này — thay cả bộ `src/agents/` MVP đơn giản đã
xây từ đầu bằng bản đầy đủ, có guardrail/history/repair/understanding thật của nhánh
kia — không phải chỉ copy file.

**Đã kiểm tra kỹ trước khi động vào gì:**
- `git merge-base feature/voice-ai origin/feature/agentic-ai` — 2 nhánh tách từ 1 gốc
  chung, `feature/agentic-ai` có 12 commit riêng chỉ động vào `src/agents/`,
  `tests/test_agents/`, `examples/` — phạm vi cô lập rõ ràng, không đụng
  frontend/voice/database.
- `src/agents/rag/` **giống hệt** giữa 2 nhánh (đã có sẵn từ gốc chung, không đổi) —
  không phải nhập mới, chỉ cần nối vào backend thật (xem bên dưới).
- Đọc kỹ `src/agents/docs/BACKEND_INTEGRATION.md` (tài liệu contract chính thức của
  nhánh kia) để biết chính xác backend phải làm gì — không đoán.

**2 xung đột hành vi thật sự (đã hỏi ý kiến trước khi làm, xem hội thoại):**
- Core Agent thật **bắt buộc số điện thoại** khi tạo booking (để tài xế liên hệ) —
  nhưng app đang hứa "không hỏi số điện thoại, email hay thông tin riêng tư". Giải
  quyết: SĐT lấy tự động từ tài khoản (đã có từ lúc đăng ký), seed thẳng vào
  `AgentState.collected_data["booking"]["phone_number"]` lúc tạo session — agent thấy
  đã có sẵn nên tự bỏ qua bước hỏi, không sửa gì trong code của nhánh kia.
- Core Agent thật đổi hẳn danh mục xe: bỏ `4_SEAT/7_SEAT/PREMIUM`, thay bằng
  `MOTORBIKE/CAR_4/CAR_7` (xe máy/ô tô 4 chỗ/ô tô 7 chỗ — không còn "hạng sang"). Cập
  nhật toàn bộ danh mục dịch vụ + câu chào + prefill "AI đặt xe ngay" theo đúng 3 loại
  xe thật này.

**Đưa vào (`git checkout origin/feature/agentic-ai -- <path>`, thay thế sạch):**
`src/agents/` (agent.py, schemas.py, state.py, guardrails.py, router.py, +
`context.py`/`history.py`/`repair.py` (sửa lỗi hội thoại, ngắt lời), +
`understanding/rewrite_*` (viết lại câu người dùng theo ngữ cảnh trước khi hiểu ý
định), `vehicle_recommendation.py`, `booking_types.py`, `location_policy.py`,
`phone_policy.py`, `docs/`), `tests/test_agents/` (326 test, tất cả pass ngay khi vừa
nhập, chưa đụng gì tới backend), `tests/integration/`, `tests/test_examples/`,
`examples/`. Xoá 3 file scaffold chết còn sót từ template khoá học
(`tools/example_tool.py`, `tools/geocode.py`, `tools/trip_status.py` — hardcode
`lat:0.0`, không ai import).

**Viết lại tầng tích hợp backend (KHÔNG mock, nối service thật):**
- `AgentToolExecutor` — thêm 3 tool mới (`get_vehicle_options`, `estimate_fare`,
  `cancel_booking`), viết lại cả các tool cũ:
  - `PlaceSearchService` (mới) — `search_place` tra thật trên gazetteer địa danh có
    sẵn (`data/gazetteer/place_names.json`, vốn chỉ dùng cho Voice ASR biasing trước
    đây), thay vì echo nguyên câu nhập thành 1 candidate giả.
  - `PricingService` (mới) — giá cước/ETA tính theo công thức khoảng cách × đơn giá
    từng loại xe, khoảng cách suy deterministic từ hash cặp điểm đón/đến (chưa có
    Maps API thật — cùng nguyên tắc mô phỏng ổn định đã dùng ở `TripService`), thay
    cho số cố định 85.000đ mọi chuyến.
  - `KnowledgeService` (mới) — retriever thật cắm vào `src/agents/rag/` (interface có
    sẵn từ nhánh kia nhưng chưa có nội dung/retriever cụ thể): bộ 6 tài liệu FAQ thật
    khớp đúng chính sách đã hiển thị nơi khác trong app + so khớp từ khoá (đã lọc từ
    dừng tiếng Việt) thay vì luôn trả 2 câu cố định. `FAQWorkflow` của nhánh kia yêu
    cầu `score >= 0.75` mới chấp nhận (chống trả lời bừa) — giữ nguyên ngưỡng đó, viết
    nội dung theo đúng khuôn FAQ thật (câu hỏi + câu trả lời) để khớp từ khoá tự nhiên
    hơn thay vì hạ ngưỡng.
  - `BookingService.cancel_booking` (mới, idempotent) + lưu thêm `phone_number` mỗi
    booking để `lookup_trip` tra được theo số điện thoại.
- `SessionService` — sinh `turn_id` mỗi lượt gọi Agent (bắt buộc theo contract mới),
  seed SĐT tài khoản vào state phiên mới, viết lại cách suy tín hiệu SUCCESS/FAILED
  cho UI (nhánh kia bỏ hẳn field `lifecycle_status` khỏi `BookingData` — ưu tiên
  HANDOFF cho người thật xử lý khi tool lỗi thay vì tự báo lỗi cứng).
- `routes/__init__.py` (chat route legacy) + `models/schemas.py` — thêm `turn_id` bắt
  buộc theo `AgentInput` mới.
- `.env.example` + `src/backend/config.py` — thêm `AGENT_REWRITE_*` (tính năng viết
  lại câu theo ngữ cảnh, tắt mặc định) — **không** dùng `src/config.py` độc lập của
  nhánh kia (project này đã tổ chức lại settings về `src/backend/config.py` từ trước).

**Frontend:** danh mục dịch vụ (Home/Booking), câu chào `AssistantPage`, và
`BookingProgressSidebar` (thêm hiển thị giá cước ước tính) cập nhật theo đúng 3 loại
xe thật + giữ nguyên toàn bộ luồng "AI đặt xe ngay" đã xây ở mục 7.

**Verify (không chỉ đọc code):**
- `pytest` toàn bộ: 485 passed / 6 skipped / 0 failed (từ 262 lên 485 — thêm 326 test
  của `tests/test_agents/` từ nhánh kia, tất cả pass nguyên trong project này).
- `ruff check` trên toàn bộ file mới/sửa: sạch (đã đối chiếu 62 lỗi ruff còn lại trên
  toàn repo — toàn bộ đều ở file KHÔNG liên quan tới việc này, có từ trước).
- Live-boot server thật, đi hết 1 lượt đặt xe hoàn chỉnh qua API thật (không phải
  test giả lập): đăng ký tài khoản → "Tôi muốn đặt xe" → "Chợ Bến Thành" (search_place
  thật khớp gazetteer) → "Sân bay Tân Sơn Nhất" → "ô tô 4 chỗ" → agent tự tính giá
  31.800đ và hỏi xác nhận (**không hỏi số điện thoại** — verify đúng ý muốn) → "Đúng"
  → booking thật được tạo, `GET /api/v1/bookings` thấy đúng chuyến với dữ liệu thật.
  Test thêm FAQ/RAG thật (2 câu khớp ngưỡng 0.75, trả lời đúng nội dung) và tra cứu
  chuyến theo mã/SĐT.
- Xác nhận không đụng branch nào khác: chỉ làm việc bằng `git show`/
  `git checkout origin/feature/agentic-ai -- <path>` (không `checkout`/switch sang
  nhánh đó), `git branch --show-current` luôn là `feature/voice-ai`,
  `origin/feature/agentic-ai` không đổi ref sau khi xong.

## 10. Fix nhỏ + Sidebar tự thu/phóng theo hover

Vài việc nhỏ xen giữa các mục lớn ở trên, gộp lại cho gọn:

- **`tsconfig.app.json`**: IDE báo đỏ dòng `"ignoreDeprecations": "6.0"` — không phải
  lỗi thật (TS 6.0.3 đang cài chấp nhận giá trị này, `tsc` sạch), chỉ do schema JSON
  của VS Code chưa cập nhật kịp bản TS mới. Sửa tận gốc thay vì để nguyên: gỡ hẳn
  `baseUrl` (đã deprecated, TS 7.0 sẽ bỏ hẳn) — `paths` tự chạy được dưới
  `moduleResolution: "bundler"` không cần `baseUrl`, alias `@/` lúc chạy thực tế do
  `vite.config.ts` tự resolve riêng. Verify: gỡ `baseUrl` mà không thêm lại
  `ignoreDeprecations` thì `tsc` báo đúng lỗi thật `TS5101` (xác nhận đây không phải
  no-op), thêm `paths`-only vào thì sạch.
- **`.gitignore`**: bổ sung `.env.*` + `!.env.example` (trước chỉ liệt kê tay
  `.env.local`/`.env.production`, thiếu biến thể nào là lọt), `.pytest_cache/`/
  `.ruff_cache/`/`.mypy_cache/` tường minh (trước chỉ ẩn được nhờ tool tự sinh
  `.gitignore` con), `.vite/`, `*.tsbuildinfo`, và chuyển các file runtime của Claude
  Code (`scheduled_tasks.lock`, `worktrees/`, `checkpoints/`...) từ
  `.git/info/exclude` (cục bộ theo máy, không đi theo repo khi clone mới) vào
  `.gitignore` thật. Verify bằng `git check-ignore -v` thật, không chỉ đọc file.
- **`src/models/voice_schemas.py` → `src/voice/schemas.py`**: dọn lại vị trí (schema
  riêng cho Voice nên nằm trong package `voice`, không phải package `models` chung
  chung không còn gì khác) — đổi import ở 9 chỗ gọi, không đổi hành vi.
- **Sidebar tự thu/phóng theo hover (thay cho nút bấm thủ công)**: làm qua 3 lượt —
  (1) thêm nút ghim mở/thu thủ công trước; (2) theo yêu cầu tiếp theo, đổi sang tự
  động hoàn toàn: mặc định thu hẹp còn dải icon, rê chuột qua tự mở ra mượt
  (`group-hover`/`group-focus-within` thuần CSS, không qua state React nên không có
  độ trễ round-trip), rê ra tự thu; sidebar nổi `fixed` đè lên nội dung thay vì đẩy
  layout giật mỗi lần hover; (3) nút ghim thủ công bị báo lỗi → gỡ hẳn, chỉ còn đúng
  1 cơ chế tự động. Bug thật bắt được giữa chừng: gỡ nút ở bước (3) để sót lại class
  `relative` (cần cho nút `absolute` cũ) cùng lúc với `fixed` mới — 2 class cùng set
  `position` khiến `relative` thắng do đứng sau trong CSS build ra, sidebar thật ra
  không hề "nổi" mà nằm lẫn trong layout thường, đúng y hệt khoảng trống xám bên trái
  người dùng chụp màn hình gửi. Verify bằng cách grep trực tiếp CSS/JS build ra, không
  chỉ đọc source.

## 11. Thay thế 8 nhánh GitHub bằng nội dung `feature/voice-ai`

Theo yêu cầu trực tiếp: "trừ nhánh main với nhánh G1, thay thế tất cả các nhánh khác
bằng project hiện tại này." Đây là thao tác **ghi đè lịch sử thật trên GitHub dùng
chung của cả nhóm**, ngược hẳn với nguyên tắc "chỉ động vào feature/voice-ai" đã giữ
xuyên suốt trước đó — đã dừng lại hỏi rõ 2 điều trước khi làm (không tự suy đoán):
ghi đè cục bộ hay đẩy thật lên origin, và đúng danh sách 8 nhánh nào. Người dùng xác
nhận: đẩy thật lên origin, đúng 8 nhánh `develop`, `feat/agent-core-routing`,
`feat/human-handoff`, `feature/agentic-ai`, `feature/backend-data`,
`feature/customer-call-ui`, `feature/frontend-mvp`, `test_speech_model`.

Trước khi ghi đè, tự thêm 1 lớp an toàn không nằm ngoài yêu cầu: tag lại đúng commit
cũ của cả 8 nhánh (`backup/develop`, `backup/feature-agentic-ai`,...) và đẩy tag đó
lên origin luôn — nội dung cũ của các nhánh (vd code trên `feature/customer-call-ui`,
`feature/frontend-mvp`) không mất, chỉ là nhánh không còn trỏ tới đó nữa, vẫn khôi
phục được qua tag nếu cần.

Thực hiện bằng `git push origin feature/voice-ai:refs/heads/<nhánh> --force-with-lease`
cho từng nhánh (không `checkout` sang nhánh nào, máy local luôn ở `feature/voice-ai`).
Phát hiện thêm: `origin/feature/voice-ai` chính nó cũng chưa từng được đẩy lên suốt
session (chỉ có commit local) — đẩy nốt bằng push thường (fast-forward, không cần
force vì là nhánh của chính mình).

Verify cuối: `main` và `G1` giữ nguyên SHA gốc; 9 nhánh còn lại (8 nhánh + chính
`feature/voice-ai`) trên origin đều trỏ đúng 1 commit; máy local vẫn ở
`feature/voice-ai`, working tree sạch.

## 12. AssistantPage: lời chào thân thiện hơn

Câu chào đầu tiên trước đây mở màn bằng liệt kê yêu cầu kỹ thuật (loại xe hỗ trợ,
"không hỏi số điện thoại/email") — đọc như thông báo hệ thống hơn là lời chào, và là
thứ ĐẦU TIÊN mọi người dùng thấy khi vào trang. Theo yêu cầu, đổi thứ tự: chào thân
thiện, gọi đúng tên khách trước, rồi mới hỏi mở "cần hỗ trợ gì" (không giới hạn riêng
đặt xe). Thông tin kỹ thuật không mất đi — chuyển thành dòng phụ nhỏ dưới tiêu đề
trang thay vì là ấn tượng đầu tiên. `WELCOME_MESSAGE` (hằng số tĩnh) đổi thành
`buildWelcomeMessage(userName)` để cá nhân hoá được.

## 13. Voice AI: nút nổi + popup thay cho trang riêng

Refactor lớn theo yêu cầu "hoàn thiện lại Frontend cho Voice AI" — tham khảo tinh
thần bố cục/tương tác của Green SM (không copy asset/logo/thương hiệu), KHÔNG rewrite
toàn bộ frontend. Trước khi sửa, đã kiểm tra `git branch --show-current` = đúng
`feature/voice-ai` theo ràng buộc bắt buộc của yêu cầu.

**Đổi kiến trúc:** `/assistant` (trang riêng, chiếm cả `<Outlet/>`) → nút nổi
`VoiceAIButton` + popup `VoiceAssistantPopup`, mounted 1 lần trong `AppLayout.tsx`
(khả dụng ở MỌI trang sau đăng nhập, không phải điều hướng sang trang khác). Toàn bộ
state hội thoại (session/messages/booking progress/…) từng nằm trong
`AssistantPage.tsx` được hoist lên `VoiceAssistantProvider`
(`features/ai-assistant/context/`) — đóng/mở popup hay chuyển trang không làm mất
hội thoại đang dở.

- **State machine 1 chỗ** (`AssistantStatus`): `connecting/idle/listening/processing/
  speaking/error` — thay cho các cờ `isSending`/`isListening` rời rạc cũ.
- **Mode A (chat/text)** — `VoiceChatPanel`: bong bóng tin nhắn, tự cuộn, quick chip,
  KHÔNG tự đọc to câu trả lời (khác Mode B có chủ đích — chat im lặng như app nhắn
  tin bình thường).
- **Mode B (gọi thoại)** — `VoiceCallPanel`: orb + waveform CSS thuần theo trạng thái,
  đồng hồ đếm giờ gọi, nút mic/loa/kết thúc cuộc gọi, `VoiceTranscript` gập gọn. Chỉ
  Mode B mới phát audio thật (`playBase64Audio`/OpenAI TTS, fallback
  `speechSynthesis` trình duyệt — đổi `speakWithBrowser()` trả về `Promise` để biết
  chính xác lúc nào hết "đang nói").
- **`BookingConfirmationModal`** — bám đúng tín hiệu THẬT `state.current_workflow ===
  "RIDE_BOOKING" && state.current_step === "CONFIRM"` (thêm 2 field này vào
  `RideTurn.state`/`VoiceTurnResponse.state`, đọc từ `BookingStep.CONFIRM` thật của
  Core Agent — đáng tin hơn suy luận gián tiếp từ `missing_field`). Nút "Xác nhận đặt
  xe" gửi đúng 1 lượt hội thoại thật `"Xác nhận đặt xe"` (khớp `_CONFIRM_TERMS`) —
  KHÔNG có endpoint tạo booking riêng ở frontend, đặt xe luôn qua agent thật. Chỉ hiển
  thị field có thật từ `BookingProgress` (pickup/destination/vehicle/giá) — không vẽ
  passenger_count/service tier/giờ đón/ghi chú vì backend chưa có (ghi vào `mustdo.md`
  mục 7, không tự bịa).
- **`BookingSuccessModal`** — tái dùng nguyên `BookingSuccessPanel` có sẵn (chỉ bọc
  khung modal), không viết lại logic thành công/thất bại.
- 6 điểm gọi `navigate("/assistant", {state:{prefill}})` cũ (Home ×2, Booking, Activity
  ×2, Tracking) đổi thành `useVoiceAssistant().openWithPrefill()`/`.open()` — mở popup
  tại chỗ thay vì điều hướng trang.
- Route `/assistant` giữ lại dạng redirect (`AssistantRedirect`): mở popup rồi về `/`,
  tránh 404 cho link cũ.
- `Sidebar.tsx` bỏ mục điều hướng "AI Assistant" (không còn là trang để trỏ tới).

**Fast Refresh split:** `oxlint` báo `react(only-export-components)` vì
`VoiceAssistantContext.tsx` từng export cả component lẫn hook/type — tách theo đúng
pattern đã dùng cho `ThemeProvider` (`theme-context.ts`/`useTheme.ts`): tạo
`voice-assistant-context.ts` (types + `createContext`) và `useVoiceAssistant.ts` (hook
riêng), file component chỉ còn export `VoiceAssistantProvider`. Không dùng
eslint-disable — sửa tận gốc.

**Verify thật** (không chỉ đọc code): build `npx tsc -b && npx oxlint && npm run
build` sạch; và chạy `uvicorn` thật + script Python đăng ký user mới → tạo phiên →
"Tôi muốn đặt xe từ Vincom Đồng Khởi đến Landmark 81" → "Xe máy" → xác nhận đúng
`current_step: CONFIRM`, `fare_amount: 47200` → gửi "Xác nhận đặt xe" → nhận
`booking_lifecycle_status: SUCCESS` + `booking_id` thật. Xác nhận thêm: lỗi 401 trả về
message tiếng Việt thân thiện (`"Vui lòng đăng nhập..."`), không phải stack trace.

Chi tiết các field/luồng backend chưa có (passenger_count, nút Hủy ở bước CONFIRM,
caption thời gian thực khi gọi) — xem `mustdo.md` mục 7.

## 14. Tự hoàn thiện các mục `mustdo.md` làm được không cần credential ngoài

Theo yêu cầu trực tiếp ("những cái nào trong mustdo mà tự cải thiện tự làm được thì
bạn cứ hoàn thiện"), rà lại toàn bộ `mustdo.md` và hoàn thiện đúng những phần không
cần tài khoản/API key bên ngoài, không cần quyết định nghiệp vụ:

- **2FA thật (TOTP)** — trước chỉ là toggle trang trí ("sắp ra mắt"). Giờ enforce thật
  ở bước đăng nhập: `AuthService` sinh secret TOTP thật (`pyotp`, thuần Python, không
  cần dịch vụ ngoài), chỉ bật sau khi xác nhận đúng 1 mã thật (tránh tự khoá tài khoản
  bằng secret chưa verify), `login()` trả `pending_token` tạm thay vì access token
  ngay nếu tài khoản đã bật 2FA, phải xác thực đúng mã ở
  `/auth/2fa/verify-login` mới lấy được access token thật. `/auth/login` giữ nguyên
  hành vi cũ cho tài khoản chưa bật (không phá flow demo). Frontend: `LoginForm.tsx`
  có bước nhập mã 6 số; `PaymentPage.tsx` có luồng bật/tắt thật (hiện secret + otpauth
  URL để thêm vào Google Authenticator, xác nhận bằng mã thật). Không làm QR ảnh (cần
  thêm dependency `qrcode`/`Pillow`) — chỉ text/otpauth URL, nhập tay vẫn hoạt động
  đầy đủ, giữ đúng tinh thần hạn chế dependency mới đã có sẵn trong `auth_service.py`.
  Test mới: `tests/test_api/test_two_factor_auth.py` (4 test, dùng `pyotp` sinh mã
  thật, không mock).
- **TrackingPage — mô phỏng nâng cao (không cần Maps API key)** — marker tài xế trước
  đứng yên 1 chỗ cố định suốt chuyến; giờ di chuyển thật theo đúng trạng thái thật
  (searching/accepted/arriving/in_transit/completed) mỗi lần poll, kèm CSS transition
  mượt và thêm pin điểm đến (trước chỉ có điểm đón). Vẫn là toạ độ % minh hoạ trên ảnh
  tĩnh, không phải GPS thật — phần GPS thật vẫn cần Google Maps API key (giữ nguyên
  trong mustdo.md).
- **Xác nhận `OPENAI_API_KEY` đã hoạt động** — `mustdo.md` mục 6 trước ghi
  "AGENT_LLM_ENABLED=false mặc định" (đã lỗi thời — code default là `true`, xem
  `src/backend/config.py`). Verify qua server thật: `GET /api/v1/status` trả
  `"understanding_mode": "openai"` — LLM thật đã hoạt động, đánh dấu mục này xong.

**Phát hiện quan trọng không thuộc phạm vi trên (đã ghi rõ vào `mustdo.md` mục 8, KHÔNG
tự sửa):** trong lúc verify, phát hiện nhánh đã được merge thêm 1 refactor lớn từ
`feature/agentic-ai` (tái cấu trúc `src/agents/` — không phải do tôi làm, xảy ra song
song khi tôi đang code, tác giả chính là bạn). Sau merge đó, chạy lại đúng kịch bản đặt
xe từng verify thành công (mục 13) không còn tới được `current_step: CONFIRM` nữa — mọi
lượt đều báo "Hệ thống đang phản hồi chậm" rồi rơi vào `HANDOFF`. Không động vào
`src/agents/` (công việc đang dở của bạn, ngoài phạm vi 2FA/tracking) — chỉ ghi nhận
trung thực để bạn biết và tự xác nhận/sửa.

## 15. Voice AI: popup chỉ còn gọi thoại, bỏ hẳn chế độ nhắn tin

Theo yêu cầu trực tiếp: nút nổi đổi từ icon mic sang icon ống nghe điện thoại
(`Phone`/`PhoneOff` tuỳ trạng thái đóng/mở), bấm vào mở THẲNG màn hình cuộc gọi kiểu
Messenger — không còn popup chat với ô nhập tin nhắn, không còn nút chuyển đổi
chat/gọi. Chỉ còn đúng 1 giao diện: `VoiceCallPanel` (orb, waveform, đồng hồ đếm giờ,
nút mic/loa/kết thúc cuộc gọi) + `VoiceTranscript` — "cửa sổ nhỏ" ghi lại lời qua lại
giữa khách và AI, giờ **mặc định mở sẵn** (trước thu gọn vì chỉ là phụ trợ cho khung
chat, giờ là nơi DUY NHẤT xem lại hội thoại) và **gồm cả câu chào mở đầu** (trước lọc
bỏ vì đã hiện sẵn trong bong bóng chat — bong bóng chat không còn nữa).

- `VoiceChatPanel.tsx` xoá hẳn (không còn dùng ở đâu); `AssistantMode`/`mode`/
  `setMode` xoá khỏi context — popup không còn khái niệm "chế độ" nữa.
- **"Kết thúc cuộc gọi"** trước đây chỉ chuyển về chat (`setMode("chat")`), giờ đóng
  hẳn popup (`close()`) — đúng nghĩa dập máy. Khi agent tự kết thúc phiên (khách nói
  "hủy"), nút hành động đổi thành **"Gọi lại"** (`newSession()`) thay vì "Quay lại trò
  chuyện" (không còn chỗ nào để "quay lại").
- **Mọi lượt hội thoại giờ đều được đọc to (TTS)**, kể cả lượt gõ chữ ngầm từ
  `openWithPrefill()` (các nút "AI đặt xe ngay") và `confirmBooking()` — trước đây chỉ
  Voice Call Mode mới đọc to, Chat Mode im lặng như app nhắn tin; giờ không còn khái
  niệm "im lặng" vì toàn bộ trải nghiệm là 1 cuộc gọi. Gộp logic phát âm thanh
  (audio thật từ `/voice/turn` hoặc giọng đọc trình duyệt) vào 1 hàm dùng chung
  `speakReply()` thay vì lặp lại ở `sendText`/`handleVoiceRecorded`.
- `BookingProgressStrip` (tiến trình đặt xe) chuyển từ khung chat cũ sang hiện ngay
  trong `VoiceCallPanel`, phía trên transcript.
- Đã qua `tsc -b`/`oxlint`/`npm run build` sạch. Không đổi API/backend — thuần
  frontend, không cần verify lại server.

## 16. Cuộc gọi rảnh tay — bỏ hẳn kiểu "bấm mic mới được nói"

Theo yêu cầu trực tiếp ("tôi muốn nghe và xử lí trực tiếp luôn chứ không phải phải
bấm nút micro"): thay `useVoiceRecorder` (ghi âm thủ công, bấm bắt đầu/bấm kết thúc)
bằng `useVoiceActivityRecorder` mới — tự phát hiện giọng nói bằng năng lượng âm thanh
(RMS) đọc liên tục từ `AnalyserNode` (Web Audio API), không cần thư viện ngoài:

- Xin quyền micro **đúng 1 lần** khi vào cuộc gọi, giữ nguyên 1 `MediaStream` xuyên
  suốt (không xin lại quyền mỗi lượt nói).
- Tự bắt đầu ghi khi năng lượng vượt ngưỡng (`SPEECH_RMS_THRESHOLD=0.02`), tự dừng và
  gửi đi khi im lặng liên tục 900ms (`SILENCE_HANGOVER_MS` — khớp
  `VOICE_VAD_SILENCE_MS=900` đã có sẵn ở backend cho pipeline giọng nói khác, giữ cùng
  "nhịp" chờ). Bỏ qua đoạn ghi dưới 300ms (tiếng ho/gõ bàn, không phải câu nói thật).
- Tự tạm dừng lắng nghe khi AI đang xử lý/đang trả lời (tránh ghi đè lượt đang gửi
  hoặc tự thu lại chính giọng AI phát ra loa), tự lắng nghe lại ngay khi AI trả lời
  xong — không cần thao tác gì thêm.
- Nút mic ở giữa đổi từ "bấm để nói" (push-to-talk) thành nút **tắt/bật micro của
  chính mình** — giống nút mute trên mọi app gọi điện thật, mặc định luôn bật.
- Xoá `useVoiceRecorder.ts` cũ (không còn ai gọi).

Đã qua `tsc -b`/`oxlint`/`npm run build` sạch. Thuần frontend (Web Audio API chạy
trong trình duyệt), không đổi API/backend.

## 17. Việc còn lại (`mustdo.md` — cần người/credential thật)

1. Tạo project Supabase thật (database production).
2. Chọn 1 trong 2 hệ thống Voice AI để giữ lâu dài (không chặn, chỉ nên dọn sau).
3. Payment Gateway thật (VNPay/MoMo/Stripe) — nếu muốn Ví AloSM Pay hoạt động thật.
4. Coupon/loyalty — cần quyết định nghiệp vụ trước khi code.
5. 2FA thật (TOTP/SMS) — hiện chỉ persist lựa chọn, chưa enforce lúc đăng nhập.
6. `OPENAI_API_KEY` thật nếu muốn bật LLM hiểu ngôn ngữ tự nhiên đầy đủ (`AGENT_LLM_*`)
   và tính năng viết lại câu theo ngữ cảnh (`AGENT_REWRITE_*`, mục 9).
7. Maps/routing API thật nếu muốn khoảng cách/giá cước chính xác theo GPS thay vì suy
   deterministic từ hash cặp điểm đón/đến (mục 9 — `PricingService`).
8. Router/dialogue-act detector rule-based (khi tắt LLM) đôi lúc hiểu sai câu hỏi FAQ
   thành lệnh huỷ/khác (quan sát khi verify mục 9) — thuộc logic gốc của nhánh
   feature/agentic-ai, sẽ tự cải thiện khi bật `AGENT_LLM_ENABLED`/`AGENT_REWRITE_ENABLED`
   thật, không sửa trong project này để giữ đúng logic gốc.

## 18. Lệnh kiểm tra nhanh

```bash
# Backend
python -m pytest -q
uvicorn src.main:app --reload --port 8000

# Frontend
cd src/frontend
npx tsc -b && npm run build && npm run lint
npm run dev
```
