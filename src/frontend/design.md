# AloSM Web — UI/UX & Frontend Design Specification

## 0. Technology Stack

Frontend của AloSM phải được xây dựng bằng:

### Core

* **React**
* **TypeScript**
* **Vite**

Không sử dụng Vue, Angular, Svelte hoặc JavaScript thuần cho frontend.

### Recommended Stack

```text
React
TypeScript
Vite
```

Các thư viện bổ trợ có thể sử dụng khi phù hợp:

```text
React Router
Tailwind CSS
Lucide React
TanStack Query
Zod
React Hook Form
```

Không được thêm thư viện chỉ để giải quyết một vấn đề nhỏ nếu có thể giải quyết bằng code hiện tại hoặc thư viện đã có.

---

## 0.1 Frontend Architecture

Frontend nên được tổ chức theo hướng:

```text
fe/
├── design.md
├── package.json
├── tsconfig.json
├── vite.config.ts
├── public/
└── src/
    ├── app/
    │   ├── router/
    │   ├── providers/
    │   └── config/
    │
    ├── components/
    │   ├── ui/
    │   ├── layout/
    │   └── common/
    │
    ├── features/
    │   ├── auth/
    │   ├── booking/
    │   ├── activity/
    │   ├── payment/
    │   ├── ai-assistant/
    │   └── profile/
    │
    ├── pages/
    │   ├── Home/
    │   ├── Booking/
    │   ├── Activity/
    │   ├── Assistant/
    │   └── Profile/
    │
    ├── hooks/
    ├── services/
    ├── types/
    ├── utils/
    ├── assets/
    └── styles/
```

Không bắt buộc phải sử dụng chính xác structure này nếu project hiện tại đã có architecture tốt. Agent phải **inspect source code trước và giữ lại architecture hợp lý**.

---

## 0.2 TypeScript Rules

Sử dụng TypeScript nghiêm túc.

Không sử dụng:

```ts
any
```

trừ trường hợp thực sự cần thiết và phải có lý do.

Ưu tiên:

```ts
interface
type
enum / union types
generic types
type guards
```

API response phải có type rõ ràng.

Ví dụ:

```ts
interface Booking {
  id: string;
  pickup: string;
  destination: string;
  status: BookingStatus;
  price: number;
}
```

Không để component tự suy đoán shape của API response.

---

## 0.3 React Rules

Sử dụng:

* Functional Components
* React Hooks
* Composition
* Reusable components

Không sử dụng class components nếu không có lý do đặc biệt.

Ưu tiên component nhỏ, có trách nhiệm rõ ràng.

Không tạo component khổng lồ kiểu:

```text
HomePage.tsx
→ 1000+ lines
```

Nếu một page quá lớn, tách thành:

```text
HomePage
├── Header
├── Hero
├── ServiceSection
├── RecentActivity
└── AIAssistantCard
```

---

## 0.4 Component Philosophy

Thiết kế component theo 3 tầng:

### Primitive

```text
Button
Input
Badge
Avatar
IconButton
```

### Composite

```text
Card
SearchBar
LocationPicker
ServiceCard
BookingCard
```

### Feature Components

```text
BookingPanel
AI Assistant
TripStatus
PaymentSummary
```

Không duplicate cùng một UI pattern ở nhiều page.

---

## 0.5 Styling

Ưu tiên **Tailwind CSS** nếu project chưa có styling system.

Tuy nhiên không được lạm dụng utility classes đến mức khó maintain.

Design tokens phải được chuẩn hóa.

Ví dụ:

```text
colors
spacing
radius
typography
shadows
breakpoints
```

Không viết random:

```css
margin: 13px;
border-radius: 17px;
color: #38a94f;
```

nếu những giá trị này không thuộc design system.

---

## 0.6 Icons

Ưu tiên:

**Lucide React**

Ví dụ:

```tsx
import { MapPin, Car, Bell, User } from "lucide-react";
```

Không sử dụng emoji làm production UI icon.

Không trộn nhiều icon libraries nếu không cần thiết.

---

## 0.7 Routing

Sử dụng React Router nếu project cần client-side routing.

Route structure nên rõ ràng:

```text
/
 /booking
 /activity
 /assistant
 /payment
 /profile
 /settings
```

Protected routes phải được xử lý ở frontend layer nhưng không thay thế authorization ở backend.

---

## 0.8 API Layer

Không gọi API trực tiếp rải rác trong UI components.

Không nên:

```tsx
<Button onClick={() => fetch("/api/booking")}>
```

Ưu tiên:

```text
Component
    ↓
Hook
    ↓
Service
    ↓
API
```

Ví dụ:

```text
features/booking/
├── api.ts
├── hooks.ts
├── types.ts
└── components/
```

---

## 0.9 Data Fetching

Nếu project có nhiều server state:

Ưu tiên **TanStack Query**.

Dùng cho:

* Booking
* Activity
* User data
* Notifications
* Services

Không dùng global state cho mọi thứ.

Phân biệt:

```text
Server State
UI State
Form State
Global App State
```

---

## 0.10 Forms

Nếu form phức tạp:

```text
React Hook Form
+
Zod
```

Validation phải có:

* client-side validation
* clear error message
* typed form values

Nhưng không được coi frontend validation là security boundary.

Backend vẫn phải validate.

---

## 0.11 Responsive Web

Đây là **Web Application**, không phải mobile app.

Ưu tiên:

```text
Desktop
↓
Tablet
↓
Mobile
```

Desktop phải được thiết kế hoàn chỉnh.

Không được chỉ:

> "Làm mobile trước rồi kéo dài ra desktop."

Desktop cần tận dụng:

* Sidebar
* Topbar
* Grid
* Multi-column layout
* Large content area
* Map + contextual panel
* Keyboard interaction
* Hover states

Mobile sẽ chuyển đổi layout khi cần.

---

## 0.12 Performance

React frontend cần chú ý:

* Lazy loading
* Route-based code splitting
* Image optimization
* Avoid unnecessary re-render
* Memoization khi thực sự cần
* Avoid huge component bundles
* Skeleton loading

Không tối ưu premature.

Chỉ tối ưu những điểm có tác động thực tế.

---

## 0.13 Accessibility

Web UI phải hỗ trợ:

* Keyboard navigation
* Focus states
* Semantic HTML
* ARIA labels khi cần
* Screen reader
* Color contrast
* Reduced motion

Interactive element phải có accessible name.

Không dùng:

```html
<div onClick={...}>
```

thay cho button nếu đó thực sự là button.

---

## 0.14 Quality Rules

Trước khi hoàn thành frontend:

```text
npm run build
```

phải chạy thành công.

Nếu project có:

```text
npm run lint
npm run test
```

thì phải kiểm tra.

Không để:

* TypeScript errors
* ESLint errors nghiêm trọng
* Broken imports
* Dead components
* Console errors
* Broken responsive layout

---

# 1. Design Mission

Tôi đang thực hiện **kiểm định và redesign toàn diện UI/UX cho AloSM Web**.

Hãy đóng vai:

* Senior Product Designer
* Senior UX/UI Designer
* Senior React Engineer
* Senior TypeScript Engineer
* Design System Architect

Mục tiêu:

> Biến AloSM thành một production-quality web application với chất lượng UI/UX tương đương một startup công nghệ lớn.

Lấy cảm hứng từ những sản phẩm mobility hiện đại như Xanh SM về:

* simplicity
* information hierarchy
* service discovery
* CTA
* booking flow
* visual consistency

Nhưng AloSM phải có **bản sắc thương hiệu riêng**.

Không copy:

* Logo
* Brand identity
* Images
* Icons
* Layout
* Pixel-perfect design
* Exact color palette

---

# 2. Golden Rule

**Đừng chỉ làm cho giao diện "đẹp".**

Hãy làm cho nó:

```text
Beautiful
+
Useful
+
Fast
+
Accessible
+
Consistent
+
Trustworthy
```

Mọi quyết định UI phải phục vụ UX.

---

# 3. Agent Workflow

Agent phải làm theo thứ tự:

```text
1. Inspect project
        ↓
2. Understand current frontend
        ↓
3. Audit UI/UX
        ↓
4. Identify problems
        ↓
5. Define design system
        ↓
6. Define component architecture
        ↓
7. Implement foundation
        ↓
8. Redesign pages
        ↓
9. Responsive optimization
        ↓
10. Loading/Error/Empty states
        ↓
11. Accessibility
        ↓
12. Visual polish
        ↓
13. Build + lint + test
```

**Không bắt đầu bằng việc thay màu.**

Hãy giải quyết:

```text
Information Architecture
↓
Layout
↓
Hierarchy
↓
Components
↓
Interaction
↓
Visual polish
```

---

# 4. Final Quality Bar

Hãy đánh giá AloSM như một sản phẩm chuẩn bị public release.

Nếu một designer hoặc developer nhìn vào UI và nói:

> "Đây trông giống một template React bình thường."

thì redesign chưa đạt.

Mục tiêu:

> **Premium SaaS quality + Modern Mobility UX + AI-native interaction + Vietnamese user familiarity + AloSM brand identity.**
