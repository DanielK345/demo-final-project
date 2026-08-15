# AloSM Frontend — Technical Audit & Feature Gap Analysis

Tài liệu này đánh giá tính thực tế của các tính năng trên Frontend AloSM Web đối chiếu với Backend FastAPI hiện tại.

## 1. Feature Audit Matrix

| Feature | UI Implementation | Frontend Logic | API Contract | Backend Implementation | Status |
|:---|:---|:---|:---|:---|:---:|
| **Authentication** | UI Pending | Auth Architecture Pending | Missing | Missing | `BACKEND MISSING` |
| **Home Dashboard** | Premium Figma Bento Grid | Complete | Static Layout / Status API | GET `/api/v1/status` | `PARTIAL` |
| **AI Assistant** | Immersive Visualizer + Chat | Complete | POST `/api/v1/chat` | FastAPI LangGraph Agent | `IMPLEMENTED` |
| **Voice Interaction (STT/TTS)** | Mic Pulse & Waveform UI | Simulated UI state (`isListening`) | Missing | STT/TTS Engine Missing | `UI ONLY` |
| **Service & Booking** | Full Catalog & Selection | Selection State & Step Flow | Missing | Booking API Missing | `MOCK DATA` |
| **Booking Confirmation Modal** | Backdrop Map Modal Card | State Transition | Missing | Booking Creation API Missing | `UI ONLY` |
| **Live Tracking** | Map Route Placeholder | Architecture Needed | Missing | Real-time GPS Streaming Missing | `BACKEND MISSING` |
| **Trip History (Activity)** | Chips Filter + Timeline Cards | Filter State | Missing | Trip History Database API Missing | `MOCK DATA` |
| **Payment & Wallet** | Balance Card + Methods | Static State | Missing | Payment Gateway / Wallet API Missing | `UI ONLY` |
| **Profile & Settings** | User Profile & Security UI | Static State | Missing | `/me` User Profile API Missing | `UI ONLY` |
| **Notifications** | Icon Badge | Static State | Missing | Push Notification Server Missing | `UI ONLY` |

---

## 2. Detailed Findings

### 2.1. Backend API Reality Check
Backend FastAPI hiện tại trong `src/api/routes.py` chỉ cung cấp chính xác **3 API Endpoints**:
1. `GET /health` -> Health check (`{ "status": "ok", "env": "development" }`)
2. `GET /api/v1/status` -> Trạng thái LangGraph Agent (`{ "status": "ready", "agent": "..." }`)
3. `POST /api/v1/chat` -> Chat với AI Agent (`ChatRequest` -> `ChatResponse`)

**Không có bất kỳ Backend API nào cho**: Auth, Booking, Trip History, Payment, GPS Tracking, STT/TTS Audio Streaming.

### 2.2. Documentation Overclaim Correction
Bất kỳ tuyên bố trước đây nào cho rằng "Booking/Payment/Trip History đã được tích hợp 100% với Production Backend" là **không chính xác**. Chúng ta cần điều chỉnh tài liệu để phản ánh đúng thực tế:
- **Tích hợp thực tế**: Chỉ có AI Assistant (`/api/v1/chat`) và Agent Status (`/api/v1/status`).
- **Nghiệp vụ khác**: Sử dụng Typed Mock Data độc lập và chuẩn bị sẵn Service Abstractions layer cho tích hợp tương lai.

### 2.3. Architecture Gaps & Hardening Action Plan
1. **Mock Data Isolation**: Tách dữ liệu giả trong `ActivityList.tsx` và `BookingPage.tsx` ra tệp `mockData.ts` riêng biệt trong thư mục `features/*/`.
2. **Voice UI Clarification**: Đánh dấu rõ ràng giao diện Micrô & Sóng âm thanh là **UI Layer ready for STT/TTS integration**.
3. **Live Tracking Architecture Gap**: Tạo thư mục `features/tracking/` và trang `pages/Tracking/TrackingPage.tsx` với giao diện đệm thông tin hành trình & GPS placeholder.
4. **Services Layer Standard**: Tách biệt rõ ràng `api.ts`, `types.ts`, `hooks.ts`, và `mockData.ts` trong các thư mục feature.
