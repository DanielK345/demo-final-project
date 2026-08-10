# 🚀 AloSM AI Booking — Frontend Guidelines & Architecture Docs

Tài liệu này dành cho các thành viên phát triển Frontend (Frontend Developers) của dự án **AloSM AI Booking**. 

Mục tiêu của tài liệu là giúp tất cả các thành viên trong team nắm rõ bối cảnh (context), cấu trúc thư mục, quy tắc viết code và phân chia công việc rõ ràng để **tránh tối đa xung đột git (merge conflict)** và duy trì tốc độ phát triển cao ("vibe code" mượt mà).

---

## ⚠️ QUY TẮC VÀNG (CRITICAL RULES)

1. **CHỈ THÊM CODE, KHÔNG ĐƯỢC XÓA CODE HIỆN CÓ (ADDITIVE-ONLY RULE)**:
   - Tất cả các Component (`CustomerUI.tsx`, `OperatorUI.tsx`), State, và hàm giả lập (stub functions) đã dựng sẵn **KHÔNG ĐƯỢC PHÉP XÓA**.
   - Khi phát triển tính năng mới, bạn **chỉ viết thêm (add/extend)**: thêm hàm mới, thêm state mới, tạo thêm file service/hook mới và import vào.
   - Không được tự ý xóa hoặc sửa tên các class Tailwind/Material Icon đã dựng chuẩn thiết kế.

2. **TUÂN THỦ CẤU TRÚC PHÂN MÔ-ĐUN (MODULAR ARCHITECTURE)**:
   - Tách biệt rõ ràng: **UI Component (View)** ↔ **Custom Hooks (Logic)** ↔ **Services (WebSocket/API)** ↔ **Types (Interface)**.
   - Hạn chế viết logic xử lý API phức tạp trực tiếp bên trong file Component. Hãy viết ra file riêng trong `src/services/` hoặc `src/hooks/`.

---

## 🛠️ NỀN TẢNG CÔNG NGHỆ (TECH STACK)

- **Framework**: React 19 + TypeScript + Vite
- **Styling**: Tailwind CSS v3
- **Icons & Fonts**: Google Material Symbols Outlined & Font Montserrat
- **Routing**: React Router DOM v7

---

## 📁 CẤU TRÚC THƯ MỤC PROJECT

```text
frontend/
├── index.html                  # Thẻ head chứa Google Fonts & Material Symbols
├── tailwind.config.js          # Cấu hình màu sắc, typography (Design Tokens)
├── package.json
├── src/
│   ├── main.tsx                # Entry point
│   ├── App.tsx                 # Cấu hình Routing (/customer, /operator)
│   ├── index.css               # Animation CSS & Material Symbol rules
│   │
│   ├── components/             # Thư mục UI Components chính
│   │   ├── CustomerUI.tsx      # [Giao diện Khách hàng] Đặt xe bằng giọng nói & Modal
│   │   └── OperatorUI.tsx      # [Giao diện Tổng đài viên] Handoff Dashboard
│   │
│   ├── services/               # [NEW FOR DEV 3] Thư mục chứa API & WebSocket
│   │   ├── websocket.ts        # Service quản lý kết nối WebSocket voice stream
│   │   └── api.ts              # Service gọi HTTP API (Booking, Trip Status, Handoff)
│   │
│   ├── hooks/                  # [NEW FOR DEV 1 & 2] Custom React Hooks
│   │   ├── useVoiceCall.ts     # Hook quản lý thu âm Mic & Audio Stream
│   │   └── useHandoffQueue.ts  # Hook quản lý danh sách cuộc gọi Handoff
│   │
│   └── types/                  # [NEW] Định nghĩa TypeScript Interfaces tập trung
│       └── index.ts            # CallState, BookingData, HandoffPackage, TranscriptItem
```

---

## 👥 PHÂN CHIA CÔNG VIỆC CHI TIẾT (TASK DIVISION FOR TEAM)

### 👤 Developer 1: Xử lý Voice Interaction & Customer UI Logic
- **File phụ trách chính**: `src/components/CustomerUI.tsx` và `src/hooks/useVoiceCall.ts`
- **Nhiệm vụ**:
  1. Xin quyền Microphone từ trình duyệt (`navigator.mediaDevices.getUserMedia`).
  2. Bắt sự kiện nút bấm **"Nói Ngay"** và **"Kết Thúc Gọi"**.
  3. Cập nhật `uiState` (`ready` ↔ `listening` ↔ `processing` ↔ `speaking`).
  4. Đưa dữ liệu transcript phản hồi từ AI vào danh sách `transcripts` để hiển thị các bong bóng chat và hộp text lớn.
  5. Xử lý mở 2 bước Modal: **"Xác nhận đặt xe?"** (`confirm`) ➔ **"Đặt Xe Thành Công!"** (`success`).
- **Lưu ý**: *Không sửa cấu trúc HTML/Tailwind của card bên phải, chỉ truyền state `pickup`, `destination`, `vehicle` vào để hiển thị.*

---

### 👤 Developer 2: Xử lý Operator Handoff Dashboard
- **File phụ trách chính**: `src/components/OperatorUI.tsx` và `src/hooks/useHandoffQueue.ts`
- **Nhiệm vụ**:
  1. Kết nối API kéo danh sách các cuộc gọi đang chờ Handoff từ Backend (FastAPI).
  2. Render danh sách cuộc gọi ở cột bên trái (Call ID, Lý do Handoff: `ASR Fail`, `Out of Scope`, v.v.).
  3. Khi chọn 1 cuộc gọi, hiển thị chi tiết ở cột bên phải: `AI Summary`, `Pending Action` (Hành động cần thiết), `Thông tin đã thu thập` và `Transcript Log`.
  4. Xử lý sự kiện nút **"Tiếp Nhận Cuộc Gọi"** (`btn-accept-handoff`) để chuyển trạng thái cuộc gọi.

---

### 👤 Developer 3: Tích hợp WebSocket & HTTP API Services
- **File phụ trách chính**: `src/services/websocket.ts`, `src/services/api.ts`, và `src/types/index.ts`
- **Nhiệm vụ**:
  1. **Định nghĩa Data Types** trong `src/types/index.ts`:
     ```typescript
     export interface HandoffPackage {
       call_id: string;
       reason: 'asr_failure' | 'out_of_scope' | 'api_failure' | 'user_request';
       intent: string;
       pickup?: string;
       destination?: string;
       vehicle?: string;
       summary: string;
       pending_action: string;
     }
     ```
  2. **WebSocket Service**: Tạo class/function kết nối WebSocket với backend FastAPI (`ws://localhost:8000/ws/call/{call_id}`) để gửi PCM Audio Stream và nhận Transcript / Event realtime.
  3. **HTTP API Service**: Viết hàm `confirmBooking()`, `getHandoffQueue()`, `acceptHandoffCall()` sử dụng `fetch` hoặc `axios`.

---

## 🚫 QUY TẮC TRÁNH CONFLICT GIT (HOW TO AVOID MERGE CONFLICTS)

1. **Mỗi Developer tạo 1 nhánh feature riêng từ `feature/frontend-mvp`**:
   - Dev 1: `git checkout -b feature/fe-customer-voice`
   - Dev 2: `git checkout -b feature/fe-operator-handoff`
   - Dev 3: `git checkout -b feature/fe-api-services`

2. **Chỉ thêm file mới trong thư mục cá nhân**:
   - Dev 3 viết hết code service vào `src/services/`.
   - Dev 1 & 2 sau đó chỉ việc `import { ... } from '../services/api'` vào file Component của mình mà không cần chạm vào code của Dev 3.

3. **Khi cần sửa file chung (ví dụ `App.tsx` hay `types/index.ts`)**:
   - Trao đổi nhanh với Frontend Lead trước khi push.
   - Thêm interface mới ở **cuối file**, không sửa hoặc xóa interface cũ.

---

## 🚀 HƯỚNG DẪN KHỞI CHẠY (LOCAL DEVELOPMENT)

```bash
# 1. Truy cập vào thư mục frontend
cd frontend

# 2. Cài đặt các thư viện (nếu chưa cài)
npm install

# 3. Chạy môi trường Dev với Vite
npm run dev
```

Ứng dụng sẽ chạy tại địa chỉ: `http://localhost:5173/`
- Trải nghiệm màn khách hàng: `http://localhost:5173/customer`
- Trải nghiệm màn tổng đài viên: `http://localhost:5173/operator`
