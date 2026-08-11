# AloSM Web — End-to-End User Flow Documentation

Sơ đồ thể hiện luồng người dùng End-to-End từ truy cập ứng dụng đến hoàn thành chuyến đi và xem lịch sử.

```mermaid
graph TD
    A[Truy cập AloSM Web] --> B[Home Dashboard /]
    
    %% AI Conversation Branch
    B --> C[Trợ lý AI Copilot /assistant]
    C -->|POST /api/v1/chat| D[FastAPI LangGraph Agent]
    D -->|Trả về Response & Analysis| C
    
    %% Booking Branch
    B --> E[Khám Phá Dịch Vụ /booking]
    E --> F[Nhập Điểm Đón & Điểm Đến]
    F --> G[Chọn Loại Xe: Taxi / Plus / Premium / Bike]
    G --> H[Nhấn Đặt Ngay / Tiến Hành Đặt Xe]
    H --> I[Confirm Ride Modal Popup Overlay]
    
    %% Confirmation & Tracking
    I -->|Xác Nhận| J[Thành Công / Xử Lý Chuyến Đi]
    J --> K[Live Tracking /tracking]
    
    %% History & Wallet
    B --> L[Lịch Sử Chuyến Đi /activity]
    B --> M[Ví & Thanh Toán /payment]
    B --> N[Tài Khoản /profile]

    classDef implemented fill:#00D1C1,stroke:#006a62,stroke-width:2px,color:#fff;
    classDef pending fill:#f1f5f9,stroke:#94a3b8,stroke-width:1px,stroke-dasharray: 5 5,color:#475569;
    classDef mock fill:#fef08a,stroke:#ca8a04,stroke-width:1px,color:#854d0e;

    class C,D,B implemented;
    class E,F,G,H,I,J,L,M,N mock;
    class K pending;
```

## Luồng Chi Tiết Theo Màn Hình

### 1. Home Dashboard (`/`) `[IMPLEMENTED & PARTIAL]`
- Người dùng xem thông tin tổng quan, chào mừng cá nhân hóa, gợi ý AI Assistant và danh mục dịch vụ nhanh.

### 2. AI Assistant (`/assistant`) `[IMPLEMENTED]`
- Tương tác thoại (Mic Visualizer UI) hoặc nhập câu hỏi văn bản.
- Gọi trực tiếp tới backend `POST /api/v1/chat`.
- Nhận phản hồi câu trả lời + thông tin suy luận từ LangGraph Agent.

### 3. Booking & Service Selection (`/booking`) `[MOCK DATA & UI ONLY]`
- Chọn điểm đón / điểm đến.
- Lựa chọn giữa các loại xe: AloSM Taxi, AloSM Plus, AloSM Premium, AloSM Bike, AloSM Express.
- Nhấn "Đặt Ngay" để mở **Confirm Ride Modal** (bản đồ mờ nền, ví AloSM Pay, thông số xe và cước phí).

### 4. Live Tracking (`/tracking`) `[BACKEND INTEGRATION PENDING]`
- Sau khi xác nhận đặt xe, chuyển hướng tới màn hình Theo dõi hành trình trực tiếp.
- Hiển thị vị trí tài xế giả lập, biển số xe và thời gian tài xế đến (ETA).

### 5. Trip History (`/activity`) `[MOCK DATA]`
- Tra cứu danh sách chuyến đi đã hoàn thành hoặc đã hủy.
- Sử dụng bộ lọc chip ngang (`Tất cả`, `Gần đây`, `Tháng trước`, `Đã hủy`).
