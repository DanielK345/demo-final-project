# Hướng Dẫn Đấu Nối Backend API Cho Đội Ngũ Lập Trình Backend (Backend Integration Guide)

Tài liệu này được biên soạn dành riêng cho **Backend Developers (Python FastAPI / Node.js)** để triển khai các API endpoints khớp 100% với giao diện Frontend AloSM.

---

## 📌 1. Tổng Quan Kiến Trúc & Cấu Hình

- **Base URL Backend**: `http://localhost:8000` (Có thể thay đổi trong `frontend/src/app/config/api.ts`).
- **Header chuẩn**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <access_token>` (khi đã đăng nhập).
- **CORS Config (Bắt buộc phía Backend)**:
  - Cho phép Origin: `http://localhost:5173` (Vite dev server)
  - Allow Methods: `GET, POST, PUT, DELETE, OPTIONS`
  - Allow Headers: `Content-Type, Authorization`

---

## 🔑 2. Chi Tiết Các Endpoints Cần Triển Khai (API Specifications)

### 2.1. Phân Hệ Xác Thực (Authentication & Profile)

#### `POST /api/v1/auth/login` — Đăng nhập tài khoản

- **Frontend Caller**: [LoginForm.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/auth/components/LoginForm.tsx)

**Request Body (`JSON`)**:

```json
{
  "email": "viet.nguyen@alosm.vn",
  "password": "Password123!"
}
```

**Response Payload (`200 OK`)**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "usr_99812",
    "email": "viet.nguyen@alosm.vn",
    "name": "Nguyễn Văn Việt",
    "avatar": "https://lh3.googleusercontent.com/aida-public/...",
    "role": "customer",
    "membership_tier": "Gold"
  }
}
```

---

### 2.2. Phân Hệ Trợ Lý AI (AI Assistant — đã có nền tảng FastAPI)

#### `POST /api/v1/chat` — Trò chuyện & xử lý ý định đặt xe với LangGraph

- **Frontend Hook**: [useSendMessage.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/ai-assistant/hooks.ts)
- **Backend Handler Hiện Tại**: [src/api/routes.py](file:///c:/Users/Admin/Desktop/P-160/src/api/routes.py)

**Request Body (`JSON`)**:

```json
{
  "message": "Đặt cho tôi một xe AloSM Plus từ 123 Tech St ra Sân bay Tân Sơn Nhất"
}
```

**Response Payload (`200 OK`)**:

```json
{
  "response": "Tôi đã tìm thấy xe AloSM Plus khả dụng. Ước tính cước phí 250,000 ₫.",
  "analysis": "Intent: BOOKING | Pickup: 123 Tech St, Quận 1 | Dropoff: Sân bay Tân Sơn Nhất | Vehicle: AloSM Plus",
  "status": "success"
}
```

---

### 2.3. Phân Hệ Dịch Vụ & Đặt Xe (Services Catalog & Booking)

#### `GET /api/v1/services` — Lấy danh sách dịch vụ xe & bảng giá

- **Frontend Isolation File**: [mockData.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/booking/mockData.ts)

**Response Payload (`200 OK`)**:

```json
[
  {
    "id": "taxi",
    "name": "AloSM Taxi",
    "description": "Di chuyển hàng ngày nhanh chóng, tiết kiệm và thân thiện môi trường.",
    "startingPrice": "50.000đ",
    "basePrice": 50000,
    "features": [
      { "icon": "group", "label": "4 Chỗ" },
      { "icon": "ac_unit", "label": "Điều hòa mát mẻ" }
    ],
    "image": "https://lh3.googleusercontent.com/aida-public/..."
  },
  {
    "id": "plus",
    "name": "AloSM Plus",
    "description": "Không gian rộng rãi, tiện nghi cao cấp. Phù hợp cho gia đình và công việc.",
    "startingPrice": "80.000đ",
    "basePrice": 80000,
    "features": [
      { "icon": "group", "label": "7 Chỗ" },
      { "icon": "wifi", "label": "Wi-Fi & Sạc miễn phí" }
    ],
    "image": "https://lh3.googleusercontent.com/aida-public/..."
  },
  {
    "id": "premium",
    "name": "AloSM Premium",
    "description": "Trải nghiệm đẳng cấp thương gia với tài xế riêng và dòng xe sang trọng nhất.",
    "startingPrice": "150.000đ",
    "basePrice": 150000,
    "features": [
      { "icon": "directions_car", "label": "Xe hạng sang" },
      { "icon": "star", "label": "Tài xế 5 sao" }
    ],
    "image": "https://lh3.googleusercontent.com/aida-public/..."
  }
]
```

#### `POST /api/v1/bookings` — Tạo yêu cầu đặt xe

- **Frontend Component**: [BookingPage.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/pages/Booking/BookingPage.tsx)

**Request Body (`JSON`)**:

```json
{
  "service_id": "plus",
  "pickup_address": "123 Tech Boulevard, Innovation District",
  "dropoff_address": "Terminal 1, City International Airport",
  "pickup_lat": 10.7769,
  "pickup_lng": 106.7009,
  "dropoff_lat": 10.8185,
  "dropoff_lng": 106.6519,
  "payment_method": "alosm_pay"
}
```

**Response Payload (`201 Created`)**:

```json
{
  "booking_id": "bk_887910",
  "status": "confirmed",
  "estimated_price": 250000,
  "currency": "VND",
  "pickup_time": "2026-08-11T17:35:00Z",
  "driver": {
    "id": "drv_007",
    "name": "Nguyễn Văn A",
    "phone": "0988888888",
    "rating": 4.9,
    "vehicle_model": "VinFast VF8 (Teal)",
    "vehicle_plate": "29A-888.88"
  }
}
```

---

### 2.4. Phân Hệ Theo Dõi Chuyến Đi Trực Tiếp (Live GPS Tracking)

#### `GET /api/v1/tracking/{ride_id}` hoặc `WebSocket /ws/v1/tracking/{ride_id}`

- **Frontend Page**: [TrackingPage.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/pages/Tracking/TrackingPage.tsx)
- **Frontend Component**: [TrackingCard.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/tracking/components/TrackingCard.tsx)

**Data Format Stream (`JSON`)**:

```json
{
  "ride_id": "bk_887910",
  "driver": {
    "name": "Nguyễn Văn A",
    "phone": "0988888888",
    "rating": 4.9,
    "vehicle": "VinFast VF8 • 29A-888.88"
  },
  "current_location": {
    "lat": 10.7801,
    "lng": 106.6990,
    "bearing": 45
  },
  "eta_minutes": 4,
  "distance_km": 1.2,
  "status": "on_the_way"
}
```

---

### 2.5. Phân Hệ Lịch Sử Chuyến Đi (Activity / Trip History)

#### `GET /api/v1/trips` — Lấy lịch sử chuyến đi của người dùng

- **Frontend Isolation File**: [mockData.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/activity/mockData.ts)
- **Frontend Component**: [ActivityList.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/activity/components/ActivityList.tsx)

**Query Parameters**: `?status=all|completed|cancelled`

**Response Payload (`200 OK`)**:

```json
[
  {
    "id": "trip_01",
    "serviceName": "AloSM Plus",
    "date": "10/08/2026 • 14:30",
    "pickup": "123 Tech St, Quận 1",
    "dropoff": "Sân bay Tân Sơn Nhất",
    "price": "152.000đ",
    "status": "completed",
    "statusLabel": "Hoàn thành",
    "driverName": "Nguyễn Văn A",
    "driverAvatar": "https://lh3.googleusercontent.com/aida-public/...",
    "licensePlate": "29A-888.88",
    "mapImage": "https://lh3.googleusercontent.com/aida-public/..."
  }
]
```

---

## 🛠️ 3. Quy Trình Chuyển Từ Mock Data Sang Real Backend API

Khi Backend hoàn thành triển khai endpoint nào, Frontend Developer chỉ cần 2 bước để chuyển đổi:

1. Mở file [api.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/app/config/api.ts) kiểm tra định nghĩa URL.
2. Thay thế việc import từ `mockData.ts` bằng React Query hook gọi `apiClient.get()` hoặc `apiClient.post()`.

---

## 🎯 4. Danh Sách Tệp Nguồn Frontend Cần Tham Chiếu

| Tính năng               | Tệp Nguồn Frontend                                                                                    | Tệp Types/Mock                                                                                        |
| :------------------------ | :------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------- |
| **Auth / Login**    | [LoginPage.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/pages/Login/LoginPage.tsx)             | [auth/types.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/auth/types.ts)               |
| **AI Assistant**    | [AssistantPage.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/pages/Assistant/AssistantPage.tsx) | [ai-assistant/api.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/ai-assistant/api.ts)   |
| **Booking & Modal** | [BookingPage.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/pages/Booking/BookingPage.tsx)       | [booking/mockData.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/booking/mockData.ts)   |
| **Trip History**    | [ActivityPage.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/pages/Activity/ActivityPage.tsx)    | [activity/mockData.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/activity/mockData.ts) |
| **Live Tracking**   | [TrackingPage.tsx](file:///c:/Users/Admin/Desktop/P-160/frontend/src/pages/Tracking/TrackingPage.tsx)    | [tracking/types.ts](file:///c:/Users/Admin/Desktop/P-160/frontend/src/features/tracking/types.ts)       |
