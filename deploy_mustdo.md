# DEPLOY MUST DO — Các bước bắt buộc bạn cần tự thực hiện khi Deploy

> **Dành cho:** Owner / Kỹ sư phụ trách triển khai hệ thống AloSM Voice AI.  
> **Cập nhật:** 2026-08-20  
> **Nguyên tắc:** AI có thể tự động sinh cấu hình Docker, script deploy và cấu trúc hệ thống, nhưng **không thể** tự đăng ký tài khoản đám mây, nạp thẻ thanh toán, cấp phát API Key có phí hoặc bấm phê duyệt thay đổi Database trên môi trường thật.

---

## 📋 Tóm tắt các bước theo thứ tự thực hiện

```mermaid
graph TD
    Step1["1. Chuẩn bị Tài khoản Cloud<br/>(Supabase, LiveKit, Fly.io/Render/Vercel)"] --> Step2["2. Thiết lập Database Supabase<br/>(Lấy Connection String, Chạy Migration)"]
    Step2 --> Step3["3. Đăng ký LiveKit Cloud & Lấy Keys<br/>(URL, API Key, Secret)"]
    Step3 --> Step4["4. Cấu hình Secret & Deploy Backend + Worker<br/>(Fly.io hoặc Render)"]
    Step4 --> Step5["5. Deploy Frontend React<br/>(Vercel hoặc Cloudflare Pages)"]
    Step5 --> Step6["6. Cập nhật CORS & Kiểm tra Nghiệm thu"]
```

---

## 1. Chuẩn bị Tài nguyên & Tài khoản Cloud

Bạn cần chuẩn bị hoặc đăng ký các tài khoản dịch vụ sau (tất cả đều có gói Free-tier để thử nghiệm):

- [ ] **Supabase** ([supabase.com](https://supabase.com)): Quản lý Database PostgreSQL.
- [ ] **LiveKit Cloud** ([cloud.livekit.io](https://cloud.livekit.io)): Hạ tầng WebRTC & Voice AI Pipeline.
- [ ] **Fly.io** ([fly.io](https://fly.io)) HOẶC **Render** ([render.com](https://render.com)): Nơi chạy Backend FastAPI + LiveKit Worker.
- [ ] **Vercel** ([vercel.com](https://vercel.com)) HOẶC **Cloudflare Pages** ([pages.cloudflare.com](https://pages.cloudflare.com)): Nơi host Frontend React UI.
- [ ] **OpenAI / OpenRouter / Gemini API Keys**: Tài khoản cung cấp Model AI cho nhận dạng, xử lý ngôn ngữ và tổng hợp giọng nói.

---

## 2. Thiết lập Database PostgreSQL trên Supabase

1. Mở **Supabase Dashboard** → Tạo Project mới (ví dụ: `AloSM-Production`, khu vực Singapore `ap-southeast-1`).
2. Vào mục **Project Settings → Database → Connection string**:
   - Chọn tab **URI**.
   - Chọn chế độ **Transaction pooler** (Cổng `6543`) để lấy `DATABASE_URL` cho app FastAPI runtime:
     ```
     postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
     ```
   - Chọn chế độ **Direct connection** (Cổng `5432`) để lấy `DATABASE_URL_MIGRATIONS` cho Alembic:
     ```
     postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
     ```
3. **Áp dụng Migration Database:**
   - **Trạng thái**: Đã được AI tự động chạy và nghiệm thu 100% PASS trên Supabase database (`db.bmnnykrmesauqaikbcot.supabase.co`) tại revision `acc88dbc1e83 (head)`.
   - Để kiểm tra lại bất kỳ lúc nào:
     ```powershell
     uv run alembic current
     uv run python scripts/verify_postgres_persistence.py
     ```


---

## 3. Cấu hình LiveKit Cloud (Hạ tầng Thoại Realtime)

1. Mở **LiveKit Cloud Console** ([cloud.livekit.io](https://cloud.livekit.io)) → Tạo Project mới (ví dụ: `alosm-voice`).
2. Vào **Settings → Keys** → Tạo API Key mới:
   - Lưu lại `LIVEKIT_URL` (dạng `wss://alosm-xxxxxx.livekit.cloud`).
   - Lưu lại `LIVEKIT_API_KEY` (dạng `APIxxxxxxxxxxxx`).
   - Lưu lại `LIVEKIT_API_SECRET` (dạng `secret_xxxxxxxxxxxxxxxxxxxxxx`).
3. Vào mục **Inference / Models** trên LiveKit Cloud:
   - Đảm bảo các model sau đã được bật hoặc có quota:
     - STT: `deepgram/nova-3` (tiếng Việt `vi`)
     - LLM: `google/gemma-4-31b-it` hoặc `openai/gpt-4o-mini`
     - TTS: `cartesia/sonic-3` (voice Vietnamese) hoặc `openai/tts-1`

---

## 4. Deploy Backend & LiveKit Worker

### Lựa chọn A: Triển khai lên Fly.io (Khuyên dùng)

1. Cài đặt Fly CLI nếu chưa có:
   ```powershell
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```
2. Đăng nhập: `fly auth login`
3. Khởi tạo app từ thư mục gốc của dự án:
   ```powershell
   fly launch --no-deploy --copy-config
   ```
4. **Nạp các Secret quan trọng lên Fly.io:**
   ```powershell
   fly secrets set `
     DATABASE_URL="postgresql://postgres.xxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres" `
     DATABASE_URL_MIGRATIONS="postgresql://postgres.xxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres" `
     QUOTE_SIGNING_KEY="tao-chuoi-ngau-nhien-it-nhat-32-ky-tu-o-day" `
     FIELD_ENCRYPTION_KEY="tao-chuoi-ngau-nhien-it-nhat-32-ky-tu-o-day" `
     JWT_SECRET_KEY="tao-chuoi-jwt-secret-ngau-nhien-o-day" `
     LIVEKIT_URL="wss://alosm-xxxx.livekit.cloud" `
     LIVEKIT_API_KEY="APxxxxxxx" `
     LIVEKIT_API_SECRET="secret_xxxxxxx" `
     OPENAI_API_KEY="sk-xxxxxxx" `
     OPENROUTER_API_KEY="sk-or-xxxxxxx" `
     GEMINI_API_KEY="AIzaxxxxxxx" `
     VOICE_RUNTIME="livekit" `
     APP_ENV="production"
   ```
5. Deploy lên mạng:
   ```powershell
   fly deploy
   ```
6. Lưu lại URL của backend: `https://ten-app-cua-ban.fly.dev`

---

### Lựa chọn B: Triển khai lên Render.com (Dùng Blueprint tự động)

1. Đăng nhập [Render.com](https://render.com) → Chọn **New + → Blueprint**.
2. Kết nối tới Git repository của bạn (Render sẽ tự đọc file `render.yaml`).
3. Render sẽ tạo ra 2 dịch vụ:
   - **alo-sm-backend** (FastAPI Web Service)
   - **alo-sm-voice-worker** (LiveKit Agent Background Worker)
4. Vào từng dịch vụ → Tab **Environment** → Điền các giá trị secret thật (tương tự danh sách ở Bước 4 - Lựa chọn A).

---

## 5. Deploy Frontend (React UI)

1. Đăng nhập [Vercel.com](https://vercel.com) → Click **Add New Project** → Import repository GitHub.
2. Cấu hình build:
   - **Root Directory:** Chọn `src/frontend` (hoặc cấu hình build command `cd src/frontend && npm run build`).
   - **Framework Preset:** `Vite`.
3. **Thêm biến môi trường (Environment Variables) trên Vercel:**
   - `VITE_API_BASE_URL`: Điền URL backend đã deploy ở bước 4 (ví dụ: `https://ten-app-cua-ban.fly.dev`).
   - `VITE_VOICE_RUNTIME`: `livekit`
4. Bấm **Deploy**.
5. Lưu lại tên miền của frontend (ví dụ: `https://alosm-frontend.vercel.app`).

---

## 6. Cập nhật CORS Backend & Kiểm tra Nghiệm thu (Smoke Test)

1. **Thêm Domain Frontend vào CORS của Backend:**
   - Trên **Fly.io**:
     ```powershell
     fly secrets set CORS_ORIGINS="https://alosm-frontend.vercel.app,http://localhost:5173"
     ```
   - Hoặc trên **Render**: Cập nhật biến `CORS_ORIGINS` trong tab Environment của service backend.

2. **Kiểm tra Nghiệm thu (Smoke Test Checklist):**
   - [ ] **Health Check:** Truy cập `https://ten-backend.fly.dev/health/ready` → Trả về `{"status":"ready",...}`.
   - [ ] **Trang chủ Frontend:** Mở `https://alosm-frontend.vercel.app` → Giao diện tải mượt mà không bị lỗi trắng trang.
   - [ ] **Đăng nhập:** Thử đăng nhập hoặc đăng ký tài khoản khách hàng mới.
   - [ ] **Cuộc gọi Thoại (Voice Call):**
     - Bấm nút icon Micro / Gọi xe trên web.
     - Cấp quyền Micro trình duyệt.
     - Nói: *"Cho tôi đặt xe đón ở Hồ Hoàn Kiếm đến Sân bay Nội Bài"*.
     - Nghe AI Agent phản hồi lại bằng tiếng Việt, tìm địa điểm và báo giá.
     - Nói: *"Tôi xác nhận đặt chuyến này"*.
     - Xác nhận mã chuyến và trạng thái booking xuất hiện trên màn hình.

---

## 7. Xử lý Sự cố Thường gặp (Troubleshooting)

| Triệu chứng | Nguyên nhân có thể | Cách khắc phục |
|---|---|---|
| **Gọi API báo lỗi `CORS error` trên Browser Console** | Backend chưa cho phép domain của Vercel | Kiểm tra biến `CORS_ORIGINS` trên Backend, đảm bảo có chính xác URL `https://your-domain.vercel.app` (không có dấu `/` ở cuối). |
| **Bấm gọi thoại nhưng không nghe thấy tiếng AI** | LiveKit Worker chưa chạy hoặc sai API Secret | Kiểm tra log của Worker (`fly logs -a ten-app` hoặc Render Logs); kiểm tra lại `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`. |
| **API trả về lỗi 500 khi Booking** | Thiếu Migration Database hoặc `QUOTE_SIGNING_KEY` | Chạy `python -m alembic upgrade head` lên Supabase; kiểm tra key ký quote trong biến môi trường. |
| **Trình duyệt báo lỗi Micro** | Trang web không có HTTPS | Vercel/Fly.io tự động cấp HTTPS; đảm bảo bạn truy cập qua link `https://...` thay vì `http://...`. |
