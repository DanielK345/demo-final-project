# AloSM — Premium AI Booking & Mobility Web Application

![AloSM Logo](./src/assets/logo.svg)

> **AloSM Frontend Web Platform** — Nền tảng đặt xe công nghệ xanh tích hợp Trợ lý AI thông minh (LangGraph / FastAPI), giao diện Kinetic Teal cao cấp chuẩn Figma design.

---

## 📑 Mục Lục Documentation

Tài liệu chi tiết dành cho Đội ngũ Phát triển (Frontend & Backend):

1. 📖 **[Backend Integration Guide](./docs/backend-integration-guide.md)** — **(QUAN TRỌNG CHO BACKEND)**: Hướng dẫn chi tiết hợp đồng API (API Contracts), Data Schemas và quy trình đấu nối Backend APIs.
2. 📊 **[Frontend Status Report](./docs/frontend-status.md)**: Báo cáo trạng thái hardened frontend & ma trận tính năng.
3. 🔍 **[Frontend Audit Matrix](./docs/frontend-audit.md)**: Ma trận kiểm định kiến trúc và phân định Mock vs Real API.
4. 🔄 **[User Flow & Diagram](./docs/user-flow.md)**: Luồng trải nghiệm người dùng End-to-End với Mermaid chart.

---

## 🚀 Công Nghệ Sử Dụng (Tech Stack)

- **Framework**: React 19 + Vite 6 (Fast Refresh, Build siêu tốc ~500ms)
- **Language**: TypeScript 5.8+ (Strict type checking, `tsc -b`)
- **Styling**: Tailwind CSS v4 (`@tailwindcss/vite`) + Custom Glassmorphism System
- **Icons**: Lucide React + Material Symbols Outlined
- **Routing**: React Router v7 (`createBrowserRouter`)
- **Data Fetching**: TanStack React Query v5
- **Design System**: Kinetic Teal Palette (`#00D1C1` Primary, `#006a62` Deep Teal, `#F8F9FB` Soft Gray)
- **Typography**: Montserrat Font Family

---

## 📁 Cấu Trúc Dự Án (Directory Structure)

```text
frontend/
├── docs/                             # Documentations dành cho Đội phát triển
│   ├── backend-integration-guide.md  # 🔥 Hướng dẫn đấu nối Backend API cho BE Dev
│   ├── frontend-audit.md             # Ma trận kiểm định kiến trúc
│   ├── frontend-status.md            # Báo cáo trạng thái hardened frontend
│   └── user-flow.md                  # Luồng trải nghiệm người dùng End-to-End
├── public/                           # Assets tĩnh (Favicon SVG)
├── src/
│   ├── app/                          # Cấu hình App, Router & Providers
│   │   ├── config/                   # API endpoint config (`api.ts`)
│   │   ├── providers/                # React Query & Context Providers
│   │   └── router/                   # React Router v7 routes definition
│   ├── assets/                       # Offical SVG Logo (`logo.svg`)
│   ├── components/                   # UI Components dùng chung
│   │   ├── layout/                   # Sidebar, Topbar, AppLayout, MobileNav
│   │   └── ui/                       # Button, Card, Avatar, Badge, IconButton
│   ├── features/                     # Feature Modules (Domain-Driven Design)
│   │   ├── ai-assistant/             # Trợ lý AI (STT/TTS, LangGraph Chat Hook)
│   │   ├── auth/                     # Authentication state & Login form
│   │   ├── booking/                  # Catalogs, Confirm Ride Modal & Mock Data
│   │   ├── activity/                 # Lịch sử chuyến đi & Filter Chips
│   │   └── tracking/                 # Live GPS Tracking prototype & Types
│   ├── pages/                        # Page Views chính của ứng dụng
│   │   ├── Home/                     # Trang chủ Bento Dashboard (`/`)
│   │   ├── Booking/                  # Danh mục dịch vụ & Đặt xe (`/booking`)
│   │   ├── Activity/                 # Lịch sử chuyến đi (`/activity`)
│   │   ├── Assistant/                # Trợ lý AI thoại & Chat (`/assistant`)
│   │   ├── Tracking/                 # Theo dõi chuyến đi trực tiếp (`/tracking`)
│   │   ├── Payment/                  # Cài đặt ứng dụng (`/payment` & `/settings`)
│   │   ├── Profile/                  # Tài khoản cá nhân (`/profile`)
│   │   └── Login/                    # Đăng nhập (`/login`)
│   ├── types/                        # Global Type definitions
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## ⚙️ Hướng Dẫn Chạy Ứng Dụng (Quick Start)

### 1. Cài đặt Dependencies

```bash
cd frontend
npm install
```

### 2. Khởi chạy Development Server

```bash
npm run dev
```
Trình duyệt sẽ mở tại địa chỉ: `http://localhost:5173`

### 3. Kiểm tra Biên dịch Production (Production Build Check)

```bash
npm run build
```
Hệ thống sẽ chạy TypeScript typecheck (`tsc -b`) và Vite build. Kết quả biên dịch sạch **0 lỗi**.

---

## 🔌 Tóm Tắt API Endpoints Cần Backend Triển Khai

| Endpoint | Method | Mục đích | Trạng thái hiện tại |
|:---|:---|:---|:---:|
| `/health` | `GET` | Healthcheck backend | ✅ Đã kết nối |
| `/api/v1/status` | `GET` | Kiểm tra trạng thái Agent AI | ✅ Đã kết nối |
| `/api/v1/chat` | `POST` | Trò chuyện với Trợ lý AI (LangGraph) | ✅ Đã kết nối |
| `/api/v1/auth/login` | `POST` | Đăng nhập tài khoản | ⏳ Cần BE code |
| `/api/v1/services` | `GET` | Lấy danh mục xe & bảng giá | ⏳ Cần BE code |
| `/api/v1/bookings` | `POST` | Khởi tạo đơn đặt xe | ⏳ Cần BE code |
| `/api/v1/trips` | `GET` | Lấy lịch sử chuyến đi người dùng | ⏳ Cần BE code |
| `/api/v1/tracking/{id}` | `WS / GET` | Theo dõi tọa độ GPS tài xế theo thời gian thực | ⏳ Cần BE code |

👉 **Xem chi tiết hợp đồng Request / Response Data Payload dành cho Backend tại: [docs/backend-integration-guide.md](./docs/backend-integration-guide.md)**
