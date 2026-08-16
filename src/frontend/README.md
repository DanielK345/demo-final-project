# AloSM frontend

React 19 + Vite + TypeScript + Tailwind frontend cho AloSM Voice.

## Tài liệu
+
+- [`docs/frontend-status.md`](docs/frontend-status.md): ma trận trạng thái hiện hành.
+- [`docs/backend-integration-guide.md`](docs/backend-integration-guide.md): API client/Backend contract.
+- [`docs/user-flow.md`](docs/user-flow.md): user flow và safety rules.
+- [`design.md`](design.md): design system/UI conventions.
+- [`../../docs/PROJECT_SOURCE_OF_TRUTH.md`](../../docs/PROJECT_SOURCE_OF_TRUTH.md): trạng thái toàn project.
+
+## Route
+
+`/login`, `/`, `/booking`, `/tracking`, `/activity`, `/payment`, `/profile`.
+`/assistant` là compatibility redirect: mở Voice popup rồi về `/`.
+
+## Data truth
+
+- Auth/session/settings/history/trip/Voice dùng API client thật nhưng Backend còn
+  process-memory ở nhiều miền.
+- Booking service catalog, fleet/map marker, ETA/voucher và payment còn phần demo
+  cho tới khi có provider/business data.
+- Frontend không tự tính fare/voucher hoặc tự công bố booking thành công.
+
+## Chạy
+
+```powershell
+npm install
+npm run dev
+```
+
+Backend mặc định: `http://localhost:8000`; cấu hình tại `src/app/config/api.ts`.
+
+## Kiểm tra
+
+```powershell
+npm run lint
+npx tsc -b
+npm run build
+```
+
+Build pass chỉ chứng minh code frontend hợp lệ; device/audio/provider/business data
+release gate nằm trong `mustdo.md`.
