# AloSM Voice — nguồn sự thật và trình tự hoàn thiện project

Cập nhật: **2026-08-20**. Tài liệu này là nguồn trạng thái toàn project. Với công
việc LiveKit, điểm bắt đầu là `docs/CODING_AGENT_HANDOFF.md`. Tài liệu này xác định
nào có thẩm quyền, dữ liệu nào đang là demo, contract nào đang chạy và phải hoàn
thiện project theo thứ tự nào. Không dùng báo cáo tiến trình hoặc kế hoạch cũ để
suy ra trạng thái runtime.

## 1. Quy tắc nguồn sự thật

Khi hai nguồn mâu thuẫn, áp dụng thứ tự sau:

1. Code runtime + migration + test đang pass.
2. Contract hiện hành của từng track.
3. Tài liệu trạng thái hiện hành.
4. PRD/MVP cho yêu cầu sản phẩm chưa được triển khai.
5. Git history khi cần truy vết quyết định hoặc kế hoạch đã bị thay thế.

| Câu hỏi | Nguồn chuẩn |
|---|---|
| Sản phẩm hướng tới điều gì? | `docs/PRODUCT_BRIEF.md`, sau đó `docs/PRD_AloSM_Voice.md` và `docs/MVP.md` |
| Hệ thống hiện chạy thế nào? | code trong `src/`, migration và test |
| Contract Agent | `src/agents/README.md`, `src/agents/docs/BACKEND_INTEGRATION.md` |
| Trạng thái Core Agent | `src/agents/docs/CORE_AGENT_STATUS.md` |
| Data production cần gì? | `src/agents/DATAFINDING.md`, `data/catalog.json` |
| Voice runtime hiện tại | `docs/CODING_AGENT_HANDOFF.md`, `docs/LIVEKIT_TEAM_SETUP.md` |
| LiveKit architecture/history | `docs/LIVEKIT_MIGRATION_IMPLEMENTATION.md` |
| Voice evaluation/cutover | `docs/PHASE4_EVALUATION_PLAN.md` |
| Legacy voice rollback/evidence | `docs/voice-ai/README.md` |
| Việc AI/code không thể tự hoàn tất | `mustdo.md` |
| Cần truy vết tài liệu đã thay thế | Git history; không giữ duplicate trong cây hiện hành |

## 2. Từ điển trạng thái thống nhất

Chỉ dùng các trạng thái sau trong tài liệu và báo cáo mới:

| Trạng thái | Nghĩa |
|---|---|
| `IMPLEMENTED` | Code và contract đã có, test phù hợp đã pass |
| `LIVE_VALIDATED` | Đã chạy qua provider/hạ tầng thật và có artifact kết quả |
| `DEMO` | Chạy được nhưng dùng dữ liệu tĩnh, deterministic hoặc process-memory |
| `STAGING_ONLY` | Có tích hợp thật nhưng chưa đủ SLA, privacy hoặc vận hành production |
| `EXTERNAL_BLOCKED` | Thiếu credential, dữ liệu business, consent, license hoặc hạ tầng |
| `RELEASE_GATED` | Code xong nhưng còn gate người thật/pháp lý/load/soak trước release |
| `HISTORICAL` | Chỉ ghi lại thiết kế hoặc tiến trình cũ |

Không dùng `DONE`, `REAL`, `PRODUCTION_READY` nếu chưa thỏa Definition of Done tại
mục 8.

## 3. Kiến trúc và ownership hiện hành

```text
Browser React
  -> FastAPI auth/session + LiveKit token control plane
  -> LiveKit Room/WebRTC
  -> local alosm-voice AgentServer
  -> AgentSession: VAD -> STT -> AloSMAgent/BookingTask/tools -> TTS
  -> AloSM application services + durable ride_sessions state
  -> LiveKit audio/transcript/structured booking state -> React
```

Legacy REST/WebSocket voice code vẫn tồn tại chỉ để rollback và Phase 4 A/B; không
được mở rộng hoặc gọi từ LiveKit happy path.

| Boundary | Owner dữ liệu | Không được làm |
|---|---|---|
| Frontend | UI state, playback state, token phiên browser | Tự tính giá/voucher hoặc tự xác nhận booking |
| Backend | auth/session, orchestration, idempotency, provider execution | Tin dữ liệu client chưa validate |
| LiveKit Agent/Task | runtime chat context + typed `AloSMSessionData` | Tự tạo fare/place/booking ID hoặc gọi legacy tool loop |
| Maps/Route | place, route, ETA có provenance | Echo free text thành địa điểm đã resolve |
| Pricing/Promotion | quote/version/eligibility | Để frontend tự áp rule |
| Fleet/Dispatch | availability/assignment có timestamp | Lộ vị trí/ID tài xế chưa assign |
| Voice | audio/transcript metadata, ASR/TTS quality | Đổi phủ định/số tiền/địa chỉ khi rewrite |
| Operator | acceptance/disposition/SLA của handoff | Nhận transcript/PII ngoài RBAC |

## 4. Catalog dữ liệu hiện tại

Catalog máy đọc được nằm tại `data/catalog.json`; giải thích cách dùng nằm tại
`data/README.md`.

| Miền | Nguồn runtime hiện tại | Trạng thái | Đích production |
|---|---|---|---|
| Identity/settings | dict trong service | `DEMO` | Postgres + password hash chuẩn + token expiry/revocation |
| Session/Voice state | `ride_sessions` + versioned `voice_agent_state` | `IMPLEMENTED` | Phase 4 concurrent/reconnect evaluation |
| Place | gazetteer seed/free text | `DEMO` | provider Place contract + serviceability + provenance |
| Route/ETA | deterministic pricing helper | `DEMO` | routing provider có traffic timestamp |
| Vehicle catalog/fleet | frontend catalog tĩnh, chưa dispatch | `DEMO` | catalog approved + availability TTL/privacy |
| Fare | bảng giá code + route không thật | `DEMO` | quote versioned, expiring, gắn `estimate_id` |
| Promotion | UI demo, chưa có service eligibility | `DEMO` | backend eligibility/ranking có version |
| Booking/trip | durable/idempotent demo integration | `STAGING_ONLY` | provider dispatch thật + reconciliation |
| Policy/RAG | owner-approved catalog + checksum/citation retrieval | `STAGING_ONLY` | AloSM legal identity/contact + durable consent + production eval |
| Handoff | LiveKit tool + durable record + redacted context/UI | `STAGING_ONLY` | operator accept/join/takeover + telephony SLA |
| LiveKit STT | Google Chirp 2 qua official plugin | `STAGING_ONLY` | WER/CER/entity corpus theo accent/noise |
| LiveKit LLM | GPT-4.1 mini qua official plugin | `STAGING_ONLY` | behavioral/model/cost A/B |
| LiveKit TTS | Cartesia Sonic 3 qua LiveKit Inference | `STAGING_ONLY` | human listening, device matrix, cost/SLA |
| Legacy ZipFormer/rewrite/TTS | rollback + historical evidence | `RELEASE_GATED` | chỉ dùng Phase 4 đối chứng nếu cần |
| Payment/notification | chưa có provider | `EXTERNAL_BLOCKED` | merchant/webhook/reconciliation + consented messaging |

## 5. Chuỗi dữ liệu chuẩn của một booking

Mọi implementation mới phải giữ đúng thứ tự và ID liên kết sau:

1. `User/AuthToken` xác thực caller.
2. `RideSession` tạo `session_id`, `call_id`, channel và trạng thái hội thoại.
3. Audio được chuẩn hóa; ASR tạo raw transcript + confidence + provider metadata.
4. Transcript reviewer chỉ sửa chính tả khi bảo toàn PII placeholder, phủ định,
   confirmation, số tiền, thời gian và địa danh.
5. Core Agent cập nhật `AgentState`; location text vẫn là unresolved cho tới khi
   Backend trả candidate từ provider.
6. Khách chọn `pickup_place_id` và `destination_place_id` đã resolve.
7. Backend lấy `route_id`, sau đó quote/fleet/promotion cùng một snapshot.
8. Backend trình summary; chỉ explicit confirmation mới tạo side effect.
9. `create_booking` dùng idempotency key và quote chưa hết hạn.
10. Booking provider trả `booking_id`; trip/driver chỉ đến từ provider result.
11. Output reviewer kiểm tra booking state trước khi cho TTS nói “thành công”.
12. Mọi event mang `request_id`, `turn_id`, `session_id`, `call_id`, `tool_call_id`
    phù hợp; log public phải redacted.
13. Nếu confidence/tool/provider/safety thất bại, tạo handoff có reason/priority,
    context redacted và trạng thái transfer kiểm chứng được.

## 6. Contract ID, thời gian và version

- ID là opaque string; client không tự tạo ID nghiệp vụ ngoài idempotency key.
- Thời gian trao đổi qua API dùng ISO-8601 UTC có timezone; UI mới đổi sang giờ địa phương.
- Tiền lưu integer VND, không dùng float; luôn có `currency="VND"`.
- Tọa độ dùng WGS84; không log đầy đủ nếu chưa có mục đích/retention được duyệt.
- Dữ liệu provider phải có `provider`, `provider_version` hoặc `observed_at`.
- Pricing, promotion, policy và model đều phải có version/revision.
- Quote, route cache và fleet bắt buộc có `expires_at`/TTL.
- Enum mới phải được khai báo ở contract dùng chung; không tạo string gần giống ở
  frontend, backend và Agent.

## 7. Trình tự hoàn thiện project

> **Không nhầm hai hệ phase:** các phase trong mục này là roadmap production của
> toàn bộ AloSM (Maps, Fleet, Telephony, Policy...). “Phase 4” trong
> [`LIVEKIT_MIGRATION_IMPLEMENTATION.md`](LIVEKIT_MIGRATION_IMPLEMENTATION.md) và
> [`PHASE4_EVALUATION_PLAN.md`](PHASE4_EVALUATION_PLAN.md) là phase đánh giá/cutover
> riêng của nhánh refactor LiveKit. Baseline LiveKit hiện đã hoàn tất implementation
> Phase 3 nhưng toàn project vẫn còn các dependency external ở roadmap dưới đây.

### Phase 0 — khóa contract và baseline

1. Dùng tài liệu này làm entrypoint; không triển khai theo TODO lịch sử.
2. Freeze DTO/AgentState/tool schemas và sinh OpenAPI snapshot cho FE/BE.
3. Chuẩn hóa ENV theo `.env.example`; secret chỉ ở local/secret manager.
4. Chạy backend full test, Ruff, compile và frontend lint/typecheck/build.

Gate: không có duplicate route/env semantics; contract test pass; không có secret
trong Git.

### Phase 1 — persistence và identity (`IMPLEMENTED_IN_CODE`, `LIVE_MIGRATION_GATED`)

1. [x] Nối repositories vào model/migration cho toàn bộ stateful runtime service.
2. [x] Chuyển auth, settings, session, conversation, quote, booking, trip, handoff và call sang durable repository ở development/production.
3. [x] Thêm transaction, optimistic concurrency, hashed token, expiry/revocation, idempotency và outbox.
4. [ ] Owner phê duyệt migration PostgreSQL live; chạy acceptance, restore drill và multi-instance soak theo `mustdo.md`.

Gate: restart không mất dữ liệu; duplicate booking vẫn bằng 0.

### Phase 2 — business truth

1. Product cung cấp vehicle catalog, pricing, service area và promotion policy.
2. Chọn Maps/Route provider sau bake-off địa chỉ Việt Nam.
3. Triển khai Place -> Route -> Fleet -> Quote -> Promotion theo contract trong
   `DATAFINDING.md`.
4. Thay mọi marker, ETA, fare và voucher demo ở UI bằng API; khi API chưa sẵn sàng
   phải gắn nhãn demo, không tự dựng sự thật.

Gate: mọi giá/ETA/voucher/place có provenance, version và expiry.

### Phase 3 — booking/trip end-to-end

1. Nối Backend tool executor với provider booking/dispatch thật.
2. Giữ explicit confirmation, quote validation và idempotency.
3. Thêm reconciliation cho timeout/unknown outcome.
4. Nối Activity/Tracking vào booking/trip đã persist.

Gate: case create/cancel/retry/reconnect không duplicate và không cam kết sai.

### Phase 4 — voice và handoff production

1. Chọn telephony/SIP, codec, consent và kênh operator.
2. Chạy ASR trên corpus telephony đã ẩn danh; khóa model/license/hardware.
3. Chạy transcript rewrite release eval theo accent/noise/critical entities.
4. Chọn TTS có SLA, human listening hai reviewer và device/browser matrix.
5. Diễn tập emergency/complaint/low-confidence handoff với context transfer thật.

Gate: latency/error/SER/CER/WER/handoff SLA đạt ngưỡng được owner ký duyệt.

### Phase 5 — policy/RAG, security và vận hành

1. Ingest policy corpus đã duyệt, có effective date và rollback.
2. Hoàn thiện RBAC, encryption, retention, deletion/export và audit.
3. Metrics/tracing/cost alert theo provider và data version.
4. Pentest, load/soak, backup/restore và disaster-recovery drill.

Gate: release checklist có owner, evidence, rollback và sign-off.

### Phase 6 — pilot và go-live

1. Pilot nhỏ có consent và support trực.
2. Theo dõi slice quality, false resolved, safety/handoff và business outcome.
3. Fix regression bằng fixture hợp pháp; không dùng transcript model sinh làm truth.
4. Chỉ go-live khi toàn bộ P0 trong `mustdo.md` đã đóng bằng bằng chứng.

## 8. Definition of Done production

Mỗi miền dữ liệu chỉ được nâng lên production khi có đủ:

- owner và người phê duyệt;
- schema/contract và validation;
- provenance, version, effective date/TTL;
- credential/license/consent hợp lệ;
- persistence, concurrency và idempotency;
- privacy, retention, RBAC và audit;
- timeout/retry/fallback/circuit breaker phù hợp;
- metrics, SLO, cost alert và runbook;
- test contract/integration/live/load theo rủi ro;
- rollback/reconciliation/restore;
- artifact nghiệm thu, ngày chạy và người ký duyệt.

Thiếu bất kỳ mục nào phải giữ trạng thái `DEMO`, `STAGING_ONLY`,
`EXTERNAL_BLOCKED` hoặc `RELEASE_GATED`.

## 9. Quy tắc cập nhật tài liệu

Khi thay đổi contract/runtime:

1. Sửa code + test trước.
2. Cập nhật tài liệu contract của track.
3. Cập nhật `data/catalog.json` nếu trạng thái/owner/source thay đổi.
4. Cập nhật `DATAFINDING.md` nếu thay data contract/provider/provenance.
5. Chỉ thêm vào `mustdo.md` nếu thực sự cần người, credential hoặc hạ tầng ngoài.
6. Ghi kết quả đã chạy vào report có ngày; không sửa kế hoạch lịch sử thành trạng thái.
7. Cập nhật mục “Trạng thái hiện hành” trong tài liệu này.

## 10. Trạng thái hiện hành

- LiveKit Voice Agent: Phase 3 `IMPLEMENTED`; Phase 4 evaluation/cutover chưa đạt.
- Backend nghiệp vụ: persistence đã nối; Maps/pricing/fleet/dispatch provider vẫn
  `DEMO/STAGING_ONLY` và chưa phải production truth.
- Frontend: route và API client chính đã có; booking catalog/payment/map/fleet còn
  phần demo hoặc chưa có provider production.
- Current model baseline: Google Chirp 2 STT, OpenAI GPT-4.1 mini LLM và LiveKit
  Inference Cartesia Sonic 3 TTS.
- Policy/RAG: `STAGING_ONLY`, catalog owner-approved đã tích hợp; còn pháp nhân/liên hệ AloSM và durable consent.
- Supabase connectivity/migration: `LIVE_VALIDATED`; service repository wiring vẫn là internal `STAGING_ONLY`.
- Telephony, maps business truth, backup/PITR/retention, Redis decision và payment: `EXTERNAL_BLOCKED`.
- LiveKit migration: React → Room → AgentSession → native tools → persistence đã
  implement tới Phase 3. Known issue thỉnh thoảng bỏ sót lượt nói/không có final
  transcript trong noise phải được đo ở Phase 4. Legacy chỉ giữ để rollback/A/B cho
  tới cutover gate.

Các blocker chi tiết và cách verify nằm duy nhất trong `mustdo.md`.
