# AloSM Frontend — trạng thái hiện hành

Cập nhật: **2026-08-16**. Trạng thái dùng taxonomy tại
`docs/PROJECT_SOURCE_OF_TRUTH.md`; build pass không đồng nghĩa dữ liệu production.

## Ma trận tính năng

| Feature | UI/route | API đang dùng | Trạng thái dữ liệu |
|---|---|---|---|
| Authentication + 2FA | `/login`, guard | `/api/v1/auth/*` | `DEMO`: backend identity còn process-memory |
| Home | `/` | agent status + session APIs | `IMPLEMENTED`, business cards phụ thuộc data bên dưới |
| Voice assistant popup | toàn bộ AppLayout | LiveKit Room + `/api/v1/livekit/*` | `IMPLEMENTED` |
| Typed booking conversation | popup | `/api/v1/sessions/*` | `IMPLEMENTED`, provider business còn demo |
| Service catalog | `/booking` | `MOCK_SERVICES_CATALOG` | `DEMO` |
| Tracking | `/tracking` | `/api/v1/trips/status` | `STAGING_ONLY`: trip process-memory, chưa GPS/dispatch thật |
| Activity/history | `/activity` | `/api/v1/bookings`, `/api/v1/sessions/history*` | `STAGING_ONLY`: dữ liệu backend chưa persistent |
| Payment/security | `/payment` | settings/2FA/password APIs | Security settings có API; wallet/payment là `DEMO/EXTERNAL_BLOCKED` |
| Profile/settings | `/profile` | auth/settings APIs | `DEMO`: settings process-memory |
| `/assistant` compatibility | redirect + mở popup | không có page riêng | `IMPLEMENTED` |

## Boundary bắt buộc

- Frontend không tự tính fare, ETA, voucher eligibility hoặc booking success.
- Marker xe chưa assign phải được aggregate/privacy-filter từ Backend.
- Mọi lỗi Room/audio/provider phải hiển thị; không chuyển runtime âm thầm.
- Khi API business chưa sẵn sàng, component phải gắn nhãn demo và giữ data trong
  file riêng; không trộn mock vào API client.
- OpenAPI/DTO Backend là contract; type gần giống nhưng khác semantics phải bị loại.

## Kiểm tra bắt buộc

```powershell
cd src/frontend
npm run lint
npx tsc -b
npm run build
```

Nghiệm thu production còn cần device/browser matrix, API business truth và
multi-instance persistence; xem `mustdo.md`.
