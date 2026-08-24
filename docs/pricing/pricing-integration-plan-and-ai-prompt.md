# Kế hoạch và prompt hoàn thiện Pricing Platform AloSM

Cập nhật: **2026-08-16**
Branch đích: **`feature/voice-ai`**
Trạng thái dữ liệu hiện tại: **DEMO — không được công bố là bảng giá AloSM chính thức**

## 1. Mục tiêu và trạng thái đã hoàn thành

`feature/backend-data` đã được fast-forward đầy đủ vào `feature/voice-ai`, không có conflict. Catalog
người dùng cung cấp đã được nhập thành `data/pricing/hanoi_demo_2026-08-16.yaml`, giữ SHA-256 nguồn,
version, vùng, owner/approver, nguồn tham khảo và nhãn DEMO.

Đã hoàn thành bằng code:

1. Loader Pydantic fail-closed, cấm field lạ, kiểm tra amount, tier tăng dần, tier cuối unbounded và đủ
   bốn loại xe.
2. Pricing service đọc catalog thay cho giá hard-code; tính progressive distance tiers đúng quy tắc
   base fare bao phủ 2 km đầu.
3. Quote trả provenance, breakdown, version, region, issued/expiry, source type và data quality.
4. Không tự tính phí thời gian/phụ phí khi route demo không có bằng chứng nghiệp vụ.
5. Đồng bộ `LUXURY` qua Core Agent, legacy extraction/safety và nhãn/catalog frontend.
6. Test catalog, boundary giá, capacity, provenance và invalid catalog; tài liệu nguồn dữ liệu và
   `mustdo.md` đã được cập nhật.

Không tạo migration Postgres/Supabase ở giai đoạn này: catalog là artifact immutable trong Git và
chưa được Finance phê duyệt. Đưa giá DEMO vào database production sẽ làm tăng nguy cơ bị sử dụng nhầm.

## 2. Kế hoạch production theo thứ tự dependency

### P0 — Business truth và quote integrity

1. Finance/Legal ký catalog APPROVED mới; không đổi status của file DEMO tại chỗ.
2. Chốt semantics phí phút, phí chờ, surcharge, rounding, timezone, hủy/no-show và golden cases.
3. Thay route hash bằng routing provider thật; distance/duration phải có provider timestamp và TTL.
4. Tạo quote store dùng chung (Postgres/Redis theo kiến trúc được duyệt), lưu input hash, breakdown,
   pricing version và expiry; `create_booking` kiểm tra và consume quote nguyên tử.
5. Booking audit giữ nguyên pricing version/breakdown đã xác nhận, không recompute bằng catalog mới.

### P1 — Promotions, API và vận hành

1. Backend promotion eligibility/ranking, tự chọn voucher có saving lớn nhất với tie-break deterministic;
   frontend không tự tính giá/voucher.
2. API vehicle options/quote trả typed contract; typed errors cho catalog unavailable, route unavailable,
   unsupported region/vehicle, expired/mismatched quote.
3. Cache hữu hạn theo region/version, invalidate khi activate/rollback catalog; metrics theo version,
   quote latency/error/expiry/mismatch và discrepancy.
4. Admin activation cần RBAC, four-eyes approval, audit log và rollback.
5. Contract/integration/concurrency tests bằng Postgres/Redis/provider sandbox thật; mock không phải acceptance.

### P2 — Release gates

1. Finance đối soát golden cases và boundary từng tier/vùng/khung giờ.
2. Staging soak/load test, multi-instance quote consistency, catalog rollback drill.
3. Security review, tamper test, PII/log review, alert/runbook và sign-off go-live.

## 3. Prompt triển khai cho AI

```text
# ROLE
Bạn là Principal Backend Engineer + Pricing Platform Engineer + Data Governance Engineer làm trực tiếp
trong repository C:\Users\KHANH\Documents\GitHub\P-160, branch feature/voice-ai.

# OBJECTIVE
Hoàn thiện Pricing Platform AloSM production-safe dựa trên catalog version hóa hiện có. Không được biến
bảng giá DEMO thành dữ liệu APPROVED, không mock/fake/simulate acceptance evidence, không tự bịa rule
kinh doanh. Tự làm mọi việc có thể hoàn thành thực tế trong repository; việc cần credential, hạ tầng,
dữ liệu chính thức hoặc phê duyệt con người phải ghi đầy đủ vào mustdo.md.

# SOURCE OF TRUTH — ĐỌC TRƯỚC KHI SỬA
1. docs/PROJECT_SOURCE_OF_TRUTH.md
2. data/catalog.json
3. src/agents/DATAFINDING.md
4. mustdo.md
5. data/pricing/hanoi_demo_2026-08-16.yaml
6. src/backend/services/pricing_catalog.py
7. src/backend/services/pricing_service.py
8. src/agents/tools/schemas.py và src/agents/core/booking/state.py
9. booking create/confirm flow, frontend vehicle/voucher UI và toàn bộ test pricing/booking.

# NON-NEGOTIABLE DATA RULES
- DEMO, STAGING_ONLY, APPROVED và HISTORICAL là trạng thái khác nhau; fail closed nếu không có catalog
  APPROVED phù hợp region/effective time trong production.
- Mỗi quote phải giữ pricing_version, region, currency, route facts, từng dòng breakdown, issued_at,
  expires_at và input hash. Không cho client gửi total làm nguồn sự thật.
- Base fare bao phủ base_km. Tiers progressive, boundary rõ, monetary arithmetic dùng integer VND hoặc
  Decimal; không dùng float cho tiền.
- Không áp per_minute/surcharge/cancellation nếu chưa có facts và rule APPROVED. Không lấy giá đối thủ
  làm giá AloSM production.
- Booking chỉ được tạo với quote chưa hết hạn, khớp pickup/destination/vehicle/passenger/promotion và
  được consume/lock nguyên tử. Retry idempotent không được tạo giá/booking khác.
- Frontend chỉ hiển thị backend quote; mọi giá/voucher tự tính ở browser phải được thay bằng dữ liệu
  backend hoặc ghi rõ minh họa và không dùng để xác nhận booking.

# IMPLEMENTATION ORDER
P0. Audit git status, branch, schema/runtime contracts và test baseline; bảo toàn thay đổi người dùng.
P0. Thiết kế typed PricingCatalog/Quote/Breakdown/Promotion contracts và ADR ngắn. Nếu tạo/chỉnh DB,
    bắt buộc dùng migration Alembic, index/FK/check constraint phù hợp, least privilege và RLS khi Data
    API có thể truy cập; không dùng service_role ở client.
P0. Implement catalog activation theo effective window/region; immutable versions + rollback.
P0. Implement routing adapter thật khi credential có sẵn; timeout/retry hữu hạn/circuit breaker; không
    fallback sang khoảng cách hash trong production.
P0. Implement durable quote repository + atomic validate/consume in create_booking; preserve booking
    price snapshot and idempotency. Handle restart/multi-instance/concurrency.
P1. Implement backend promotions: eligibility, caps, budget reference, stackability, deterministic
    best-voucher ranking và explanation. Voucher phải gắn quote version/expiry.
P1. Wire agent tool schemas/state/confirmation and REST/WebSocket responses end-to-end. Agent phải đọc
    đúng giá, nói rõ “dự kiến”, không cam kết surcharge/discount chưa xác nhận.
P1. Replace frontend derived fare/voucher with typed backend data; show loading/error/expired/requote;
    keyboard/mobile/accessibility; không nuốt error.
P1. Add structured logs/metrics/traces without full address/phone/coordinates; include correlation ID,
    pricing version, latency stages, mismatch/expiry/requote counters.
P1. Add unit, property/boundary, contract, integration, migration, concurrency and idempotency tests.
    Dùng provider sandbox/DB/Redis thật cho acceptance; test double chỉ dùng unit test và không được ghi
    là bằng chứng production.
P2. Run Finance golden-case evaluator, load/soak, rollback drill and security checks when external inputs
    exist. Otherwise add an actionable mustdo item with owner, why, exact artifact/env, expected result,
    verify command and risk.

# REQUIRED ERROR CONTRACT
Use stable codes at minimum: PRICING_CATALOG_UNAVAILABLE, PRICING_NOT_APPROVED,
PRICING_REGION_UNSUPPORTED, VEHICLE_UNSUPPORTED, ROUTE_UNAVAILABLE, QUOTE_EXPIRED,
QUOTE_MISMATCH, QUOTE_ALREADY_CONSUMED, PROMOTION_INELIGIBLE, PROMOTION_BUDGET_UNAVAILABLE.
No uncontrolled HTTP 500 and no silent fallback to stale/demo prices in production.

# VERIFICATION
- uv lock --check
- python -m pytest -q
- python -m ruff check .
- frontend npm run lint, npm run typecheck, npm run build
- migration upgrade/current/downgrade/upgrade on an isolated real database if migrations change
- scan conflict markers, secrets and stale hard-coded prices
- report exact pass/fail/skip counts and clearly separate automated evidence from external gates.

# DOCUMENTATION OUTPUT
Update data/catalog.json, src/agents/DATAFINDING.md, API/OpenAPI docs, relevant ADR/runbook and
mustdo.md. Remove obsolete statements only after proving they have no runtime consumer; preserve history
through Git, not duplicate “old/current” docs.

# FINAL REPORT
Return: merged commits; files changed; architecture/contract decisions; pricing provenance; tests with
exact results; remaining external blockers; security/data risks; commit SHA and push result. Commit and
push to origin/feature/voice-ai only after all available gates pass. Do not ask routine questions; make
safe in-scope assumptions. Stop rather than inventing business truth or credentials.
```

## 4. Definition of Done

Code hoàn thành khi catalog invalid fail-closed; calculation boundary pass; mọi quote/booking giữ được
provenance; frontend không trở thành pricing authority; expired/mismatch quote bị từ chối; test/lint/build
pass. Production chỉ hoàn thành khi các mục Finance/Legal/Maps/quote-store trong `mustdo.md` có artifact
thật và sign-off — việc code pass không thay thế các gate đó.