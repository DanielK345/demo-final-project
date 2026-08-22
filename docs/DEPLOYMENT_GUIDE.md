# 🚀 Hướng dẫn Triển khai AloSM Voice AI lên Môi trường Mạng (Cloud Deployment)

**Cập nhật:** 2026-08-20  
**Tài liệu đi kèm:** [`deploy_mustdo.md`](../deploy_mustdo.md) (Checklist các việc bạn cần tự làm)

---

## 1. Tổng quan Kiến trúc khi Triển khai

Hệ thống AloSM Voice AI gồm 4 dịch vụ độc lập hoạt động cùng nhau:

| Thành phần | Công nghệ | Nhiệm vụ | Nơi deploy đề xuất |
|---|---|---|---|
| **Frontend** | React 19 + Vite | Giao diện người dùng web, nút bấm gọi xe, hiển thị bản đồ và trạng thái | **Vercel** / **Cloudflare Pages** |
| **Backend API** | FastAPI (Python) | Xử lý đăng nhập, cấp token LiveKit, điều phối dữ liệu booking, quản lý lịch sử | **Fly.io** / **Render** |
| **Voice Worker** | LiveKit Agent Server | Tiếp nhận luồng audio realtime, xử lý nhận dạng STT, quyết định Agent và TTS | **Fly.io** / **Render** |
| **Database** | PostgreSQL (Supabase) | Lưu trữ phiên gọi, tài khoản, quote giá được ký bảo mật, đơn đặt xe | **Supabase** (Singapore) |
| **Realtime Gateway** | LiveKit Cloud | Máy chủ WebRTC xử lý phòng thoại âm thanh độ trễ thấp | **LiveKit Cloud** |

---

## 2. Lựa chọn Phương án Triển khai

### 🌟 Phương án 1: Fly.io + Vercel + Supabase (Khuyên dùng)
- **Ưu điểm:** Độ trễ thấp nhất vì server đặt tại Singapore (`sin`), tương thích 100% với kiến trúc Voice AI realtime, WebRTC mượt mà.
- **Chi phí:** Có thể chạy gói Free / Tiết kiệm (~$0 - $5/tháng).

### ⚡ Phương án 2: Render.com Blueprint (Đơn giản nhất)
- **Ưu điểm:** Dùng file `render.yaml` tạo tự động cả Backend và Worker chỉ với vài cú click trên giao diện web.
- **Chi phí:** Gói Free hoặc Starter $7/tháng/service.

### 🖥️ Phương án 3: Tự host trên VPS (Ubuntu / Linux)
- **Ưu điểm:** Toàn quyền kiểm soát server, dùng file `docker-compose.prod.yml`.
- **Chi phí:** $4 - $6/tháng trên DigitalOcean / Hetzner / Linode.

---

## 3. Hướng dẫn Chi tiết Phương án 1 (Fly.io + Vercel + Supabase)

### Bước 1: Chuẩn bị Database Supabase
1. Đăng ký tại [supabase.com](https://supabase.com) và tạo project tại khu vực **Singapore (`ap-southeast-1`)**.
2. Lấy 2 chuỗi kết nối trong **Project Settings → Database → Connection string**:
   - `DATABASE_URL`: persistent service dùng Direct/Session Pooler (cổng `5432`); chỉ workload tạm thời mới dùng Transaction Pooler `6543`.
   - `DATABASE_URL_MIGRATIONS`: URI dạng Direct Connection (Cổng `5432`).
3. Chạy lệnh cập nhật database từ máy tính của bạn:
   ```powershell
   $env:DATABASE_URL_MIGRATIONS="postgresql://postgres.[REF]:[PASS]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

### Bước 2: Chuẩn bị LiveKit Cloud
1. Đăng ký tại [cloud.livekit.io](https://cloud.livekit.io) và tạo project `alosm-voice`.
2. Vào **Settings → Keys** để lấy: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.

### Bước 3: Deploy Backend & Voice Worker lên Fly.io
1. Cài đặt Fly CLI: `powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"`
2. Đăng nhập: `fly auth login`
3. Khởi tạo app: `fly launch --no-deploy --copy-config`
4. Cài đặt các biến bí mật (Secrets):
   ```powershell
   fly secrets set `
     DATABASE_URL="postgresql://postgres.xxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres" `
     DATABASE_URL_MIGRATIONS="postgresql://postgres.xxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres" `
     QUOTE_SIGNING_KEY="tao-khoa-32-ky-tu-ngau-nhien-o-day" `
     FIELD_ENCRYPTION_KEY="tao-khoa-32-ky-tu-ngau-nhien-o-day" `
     JWT_SECRET_KEY="tao-khoa-jwt-32-ky-tu-o-day" `
     LIVEKIT_URL="wss://your-project.livekit.cloud" `
     LIVEKIT_API_KEY="APxxxxxxx" `
     LIVEKIT_API_SECRET="secret_xxxxxxx" `
     OPENAI_API_KEY="sk-xxxxxxx" `
     OPENROUTER_API_KEY="sk-or-xxxxxxx"
   ```
5. Deploy:
   ```powershell
   fly deploy
   ```
6. Backend của bạn sẽ chạy tại: `https://alosm-voice-ai.fly.dev` (hoặc tên app bạn đã đặt).

### Bước 4: Deploy Frontend lên Vercel
1. Đăng nhập [vercel.com](https://vercel.com) → Chọn **Add New Project** → Chọn repo GitHub của bạn.
2. Cấu hình:
   - **Root Directory:** `src/frontend`
   - **Framework:** `Vite`
3. Thêm biến môi trường:
   - `VITE_API_BASE_URL`: `https://alosm-voice-ai.fly.dev` (URL backend ở bước 3)
4. Bấm **Deploy**. Bạn sẽ nhận được đường link website: `https://alosm-frontend.vercel.app`.

### Bước 5: Cấu hình CORS cho Backend
Để trình duyệt cho phép Frontend gọi vào Backend, bạn thêm domain Vercel vào Backend:
```powershell
fly secrets set CORS_ORIGINS="https://alosm-frontend.vercel.app,http://localhost:5173"
```

---

## 4. Kiểm tra Sau khi Triển khai (Smoke Testing)

1. Mở đường link Frontend trên trình duyệt (có biểu tượng ổ khóa bảo mật `https://`).
2. Bấm nút **Micro** để bắt đầu cuộc gọi thoại:
   - Trình duyệt sẽ hỏi: *"Cho phép trang web sử dụng micro của bạn?"* → Chọn **Cho phép (Allow)**.
   - Nói: *"Chào tổng đài, đón tôi ở Hồ Gươm đi Nội Bài"*
   - AI Agent sẽ trả lời và hiển thị thông tin chuyến xe trên màn hình.
   - Nói: *"Tôi xác nhận đặt chuyến này"*.
   - Hệ thống thông báo đặt xe thành công và tạo mã chuyến.

---

## 5. Danh mục File Cấu hình trong Dự án

- [`fly.toml`](file:///c:/Users/KHANH/Documents/GitHub/P-160/fly.toml): Cấu hình Fly.io (Multi-process Web API + Worker).
- [`render.yaml`](file:///c:/Users/KHANH/Documents/GitHub/P-160/render.yaml): Cấu hình Render Blueprint.
- [`docker-compose.prod.yml`](file:///c:/Users/KHANH/Documents/GitHub/P-160/docker-compose.prod.yml): Cấu hình Docker Compose cho VPS.
- [`.env.production.example`](file:///c:/Users/KHANH/Documents/GitHub/P-160/.env.production.example): Danh sách biến môi trường mẫu cho Production.
- [`deploy_mustdo.md`](file:///c:/Users/KHANH/Documents/GitHub/P-160/deploy_mustdo.md): Checklist các bước cần làm.
