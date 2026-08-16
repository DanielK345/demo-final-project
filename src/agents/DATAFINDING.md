# DATAFINDING — dữ liệu production cho AloSM Agent

Cập nhật: **2026-08-16**. Phạm vi: Core Agent, Voice AI, booking, map/fleet, pricing,
promotion, RAG, handoff và evaluation. Đây là bản đối chiếu trực tiếp với code hiện tại; không coi
dữ liệu deterministic/demo là dữ liệu thật.

Tài liệu tổng điều phối nằm tại `docs/PROJECT_SOURCE_OF_TRUTH.md`; catalog máy đọc được nằm tại
`data/catalog.json`. Khi trạng thái trong tài liệu cũ mâu thuẫn, code/test hiện hành và hai nguồn này
được ưu tiên.

## 0. Quản trị và chuỗi phụ thuộc dữ liệu

Mỗi record production phải truy được chuỗi `owner -> source/provider -> schema -> version ->
effective time/TTL -> runtime consumer -> evidence`. Trạng thái chỉ dùng taxonomy `IMPLEMENTED`,
`LIVE_VALIDATED`, `DEMO`, `STAGING_ONLY`, `EXTERNAL_BLOCKED`, `RELEASE_GATED`, `HISTORICAL`.

Thứ tự phụ thuộc chuẩn:

```text
Identity/consent
  -> Session + AgentState
  -> Place resolution
  -> Route snapshot
  -> Fleet + vehicle catalog
  -> Quote + promotion eligibility
  -> Explicit confirmation
  -> Idempotent booking
  -> Trip/dispatch
  -> TTS-confirmed output hoặc Handoff
  -> Audit/evaluation/retention
```

Không triển khai lớp sau bằng dữ liệu tự suy diễn khi lớp trước chưa có provenance. Đặc biệt:
frontend không tự tính quote/voucher; Agent không tạo place/fare/ETA/booking ID; TTS không được nói
booking thành công trước backend state; eval artifact không tự trở thành business truth.

## 1. Kết luận nhanh

| Miền dữ liệu | Hiện trạng trong repo | Mức sẵn sàng | Owner cần cung cấp |
|---|---|---:|---|
| Địa điểm | `place_names.json`, không tọa độ; địa chỉ lạ bị echo thành candidate | Demo | Engineering + Maps vendor |
| Route/ETA | khoảng cách sinh từ hash trong `pricing_service.py` | Demo | Maps vendor |
| Fleet/xe gần | marker và ETA tĩnh trong `RideBookingExperience.tsx`; trip sinh từ hash | Demo | Dispatch/Fleet |
| Giá | bảng giá hard-code, route không thật | Demo | Product/Ops/Finance |
| Voucher | ba voucher hard-code ở frontend, chưa có Promotion API | Demo | Growth/Finance |
| Booking/trip | idempotency có, nhưng service chính còn process-memory | Staging-only | Engineering + DB owner |
| FAQ/RAG | sáu tài liệu tự soạn, keyword retriever | Prototype | Legal/Product/Support |
| Voice | ASR/TTS adapter có; chưa có telephony/SIP production | Staging-only | Voice/Telephony owner |
| Handoff | reason code/priority/queue/lifecycle đã có; chưa có operator/telephony thật | Staging-only | Support Ops |
| Eval | offline deterministic, chưa có transcript pilot đã ẩn danh | Prototype | QA + Data/Legal |
| LLM | model-driven, typed tools/guardrails; quyền model/key phụ thuộc account | Code-ready | Platform owner |

P0 về dữ liệu là: địa điểm + route thật, bảng giá được duyệt, fleet availability, policy corpus và
operator queues. Không có năm nhóm này thì UI có thể giống ứng dụng gọi xe nhưng không được mô tả
là production-real.

## 2. Hợp đồng dữ liệu chuẩn

### 2.1 Place

```json
{
  "place_id": "provider-stable-id",
  "display_name": "Tên dễ đọc",
  "formatted_address": "Địa chỉ chuẩn hóa",
  "latitude": 10.0,
  "longitude": 106.0,
  "types": ["address", "poi"],
  "serviceable": true,
  "provider": "...",
  "provider_payload_version": "..."
}
```

Yêu cầu: stable trong phiên, có provenance, không coi free-form text là `RESOLVED`, kiểm tra vùng
phục vụ và không ghi log tọa độ/địa chỉ đầy đủ ngoài mục đích đã duyệt.

### 2.2 Route và quote

```json
{
  "route_id": "...",
  "pickup_place_id": "...",
  "destination_place_id": "...",
  "distance_meters": 8500,
  "duration_seconds": 1380,
  "polyline": "...",
  "traffic_timestamp": "...",
  "provider": "..."
}
```

```json
{
  "estimate_id": "...",
  "pricing_version": "2026-08-01",
  "vehicle_option_id": "...",
  "base_fare": 0,
  "distance_fare": 0,
  "time_fare": 0,
  "surcharge": 0,
  "discount": 0,
  "total": 0,
  "currency": "VND",
  "expires_at": "..."
}
```

`estimate_id`, pricing version và hạn quote phải đi xuyên suốt tới `create_booking`; backend phải
reject quote hết hạn hoặc không khớp state đã xác nhận.

#### Catalog DEMO hiện hành (2026-08-16)

- Nguồn runtime duy nhất: `data/pricing/hanoi_demo_2026-08-16.yaml`; loader fail-closed tại
  `src/backend/services/pricing_catalog.py`.
- Provenance: file người dùng cung cấp có SHA-256
  `6AFF08BD3DAFD6C8833F423D9CEC6DAE1F74E60932EA3696B3096C6B97315718`; dữ liệu tham khảo
  GreenSM công khai, khu vực Hà Nội, tuyệt đối không phải bảng giá AloSM đã được Finance duyệt.
- Loại xe: `MOTORBIKE`, `CAR_4`, `CAR_7`, `LUXURY`. `CAR_7` là mức suy diễn; giá Bike mở cửa
  và chính sách hủy chưa được xác minh đủ; tất cả vẫn mang `status/data_quality=DEMO`.
- Công thức runtime: giá mở cửa bao phủ `base_km`, phần vượt ngưỡng tính progressive tiers và áp
  `min_fare`. Không tự áp `per_minute` hoặc surcharge vì route demo không chứng minh thời gian chờ,
  khung giờ, ngày lễ, điểm dừng hay đổi điểm đến.
- `distance_km`/ETA vẫn là deterministic DEMO cho tới khi có routing provider thật. Quote có TTL 300
  giây nhưng production còn phải dùng quote store dùng chung và kiểm tra hết hạn nguyên tử khi đặt xe.

### 2.3 Fleet availability

```json
{
  "vehicle_id": "opaque-id",
  "vehicle_type": "CAR_4",
  "latitude": 10.0,
  "longitude": 106.0,
  "heading": 120,
  "availability": "AVAILABLE",
  "eta_seconds": 240,
  "observed_at": "..."
}
```

Frontend chỉ nên nhận vị trí làm mờ/aggregate trước khi ghép chuyến; không phát trực tiếp định danh
và tọa độ chính xác của tài xế chưa được assign. Cần TTL ngắn và loại record stale.

### 2.4 Promotion

```json
{
  "promotion_id": "...",
  "code": "...",
  "version": "...",
  "eligible": true,
  "saving_amount": 30000,
  "currency": "VND",
  "reason_if_ineligible": null,
  "stackable": false,
  "expires_at": "..."
}
```

“Voucher hời nhất” phải do backend xếp hạng trên danh sách eligible với cùng quote và customer;
frontend không tự tạo rule hoặc tự áp mã. Tie-break cần business phê duyệt, ví dụ saving lớn nhất,
sau đó expiry gần nhất, sau đó priority campaign.

### 2.5 Knowledge/RAG

Mỗi chunk phải có: `document_id`, `version`, `effective_from`, `effective_to`, `owner`, `source`,
`jurisdiction`, `content_hash`, `content`, `approved_at`. Retriever không được trả tài liệu hết hiệu
lực; câu trả lời phải giữ citation trong metadata nhưng không đọc URL/ID kỹ thuật qua TTS.

### 2.6 Handoff

Handoff hiện đã có `reason_code`, `priority`, `severity`, `queue`, `summary`, `pending_tool`,
`requires_immediate_transfer`, lifecycle `pending -> accepted`. Production cần bổ sung operator ID
thật, SLA timestamps, transfer outcome và disposition. Summary phải redacted; transcript/audio đầy
đủ chỉ mở theo RBAC và audit.

## 3. Nguồn địa điểm và routing

| Phương án | Ưu điểm | Rủi ro/điều kiện | Khuyến nghị |
|---|---|---|---|
| Nominatim + OSRM tự host | kiểm soát hạ tầng, không tính phí/request | cần vận hành dữ liệu OSM, update, capacity và attribution | tốt cho prototype/private stack có DevOps |
| Mapbox Geocoding v6 + Directions v5 | forward/reverse geocode, traffic route, tài liệu/quota rõ | token, billing; điều khoản lưu dữ liệu; autocomplete tính theo request | ứng viên managed dễ tích hợp |
| Google Geocoding/Places + Routes | hệ sinh thái lớn, place ID/route/traffic | billing, quota, field mask, điều khoản lưu/cache | ứng viên managed nếu business đã dùng Google |
| Goong/VietMap | định hướng dữ liệu Việt Nam | cần benchmark coverage, SLA, license và hợp đồng trực tiếp | chạy bake-off bằng bộ địa chỉ thật |

Ràng buộc đã xác minh:

- Public Nominatim không phù hợp làm autocomplete production dung lượng lớn; phải tuân thủ usage
  policy, caching và identification: https://operations.osmfoundation.org/policies/nominatim/
- OSRM cung cấp HTTP routing service và phù hợp self-host:
  https://project-osrm.org/docs/v26.4.0/http
- Mapbox Geocoding v6 có forward/reverse geocoding; autocomplete mặc định có thể tạo một request
  cho mỗi ký tự và điều khoản lưu kết quả phụ thuộc chế độ:
  https://docs.mapbox.com/api/search/geocoding/
- Mapbox Directions v5 hỗ trợ driving/driving-traffic và công bố giới hạn request:
  https://docs.mapbox.com/api/navigation/directions/
- Google Routes trả route/legs/steps, distance/duration và yêu cầu chọn field cần dùng:
  https://developers.google.com/maps/documentation/routes/understand-route-response

### Bake-off bắt buộc trước khi chọn provider

Dùng ít nhất 500 query đã ẩn danh: địa chỉ số nhà/hẻm, POI, tên cũ/mới, không dấu, lỗi ASR,
reverse-geocode và query sát biên vùng phục vụ. Đo top-1/top-3 accuracy, p50/p95 latency, no-result,
false-resolved, chi phí/booking và điều khoản cache. Không chọn theo cảm nhận vài địa danh nổi tiếng.

## 4. Giá, fleet và promotion

Ba miền này không thể “tìm trên Internet” để biến thành sự thật AloSM:

- Product/Ops/Finance phê duyệt pricing version và case đối soát.
- Fleet/Dispatch phát availability qua stream/API có timestamp, service area và privacy filter.
- Growth/Finance phát eligible promotions từ backend và chịu trách nhiệm budget/anti-abuse.

Khi chưa có dữ liệu, code phải gắn `data_quality=DEMO` hoặc `estimated=true`; UI không dùng câu
“xe đang ở gần bạn” hay “đã áp voucher” nếu chỉ là mảng hard-code. Dữ liệu thị trường công khai chỉ
được dùng benchmark và phải ghi nguồn/ngày, không copy thành chính sách AloSM.

## 5. OpenAI, voice và model data

Code nên ưu tiên một model ID cấu hình được, typed function tools và structured validation. Catalog
OpenAI chính thức ngày kiểm tra liệt kê GPT-5.6 Sol/Terra/Luna, hỗ trợ qua Responses API; model ID,
giá, quota và quyền account phải kiểm tra lại lúc deploy:
https://developers.openai.com/api/docs/models

Không ghi “có key nên API chắc chắn hoạt động”. Readiness production cần canary thật ở staging:
model access, tool calling, schema adherence, timeout, rate-limit, retry, cost/turn và fallback. Voice
cần đo riêng VAD, STT, Agent, tool và TTS; transcript cuối turn không đồng nghĩa streaming realtime.

Dữ liệu voice cần thu từ pilot có consent, sau đó ẩn danh:

- giọng Bắc/Trung/Nam, tốc độ nói, tiếng ồn, code-switch;
- địa chỉ/POI dễ nhận sai, số điện thoại/mã chuyến;
- interruption, self-correction, phủ định và xác nhận;
- emergency, complaint, lost-item, payment dispute và explicit human request.

Đối với Transcript Rewriter, mỗi sample được phê duyệt cần tối thiểu:

- `audio_id` dạng pseudonym, provider/model/version và điều kiện noise/accent;
- transcript ASR thô, transcript ground-truth và transcript sau rewrite;
- span annotation cho địa danh, số điện thoại, mã chuyến, tiền, thời gian, phủ định,
  confirmation và cancellation;
- reviewer/annotation version nhưng không chứa danh tính khách;
- metric WER/CER, entity error rate, false-correction rate, semantic-flip rate, latency và cost.

Gate an toàn bắt buộc: semantic flip cho confirmation/cancellation/negation bằng 0; placeholder PII
bị thêm/xóa/đổi bằng 0. Chỉ số cải thiện WER không được bù cho vi phạm hai gate này.
Không dùng audio/transcript thật làm eval nếu chưa có retention, consent và quyền truy cập rõ ràng.

## 6. RAG và policy truth

Hiện `knowledge_service.py` có sáu FAQ tự soạn; một số khẳng định như bảo hiểm, phí hủy hoặc AloSM
Pay chưa có nguồn business chính thức. Trước production:

1. chuyển policy thành file/data source có version thay vì string trong code;
2. legal/product approve từng document;
3. ingest, checksum, effective-date filter và rollback;
4. dùng keyword retriever làm fallback; chỉ thêm embedding/vector DB khi corpus đủ lớn;
5. eval groundedness, citation correctness, stale-policy rejection và prompt injection.

Không hạ threshold chỉ để tăng answer rate. Khi không có nguồn đủ tin cậy, Agent phải nói chưa có
dữ liệu xác thực hoặc handoff đúng policy.

## 7. Evaluation dataset và observability

Bộ readiness hiện là scenario tự soạn, chưa đại diện traffic thật. Dataset production cần:

- split train/dev/test theo conversation, không rò cùng customer/template;
- golden annotations: intent/capability, slots, tool, args, confirmation, outcome, handoff reason;
- hard negatives cho greeting, bare intent, garbage, prompt injection và địa chỉ mơ hồ;
- version hóa annotation guideline và inter-annotator agreement;
- slice metrics theo accent, provider, intent, noise, latency và reason code.

Chỉ số gate đề xuất:

| Chỉ số | Gate ban đầu |
|---|---:|
| Booking side-effect trước explicit confirmation | 0 |
| Duplicate create/cancel | 0 |
| Emergency/safety handoff recall | 100% trên bộ approved |
| PII leakage trong speech/log công khai | 0 |
| Tool/schema validity | >= 99% |
| Place false-resolved | <= 0.5% |
| Workflow completion (đủ dữ liệu/provider khỏe) | >= 95% |
| Agent p95 excluding external tool | theo SLO đã duyệt |

Log phải có correlation ID, turn ID, tool call ID, provider latency, data version, reason code và
outcome; không log raw secret/audio/phone/address nếu không cần.

## 8. Lộ trình dữ liệu

### P0 — trước pilot

1. Chọn Maps provider bằng bake-off; triển khai place/route contract và cache đúng license.
2. Nhận pricing/service-area/vehicle catalog bản approved.
3. Thay marker/ETA/voucher hard-code bằng API hoặc gắn nhãn demo rõ ràng.
4. Nhập policy corpus có owner/version/effective date.
5. Cấu hình operator queues và diễn tập emergency handoff.

### P1 — pilot có kiểm soát

1. Fleet availability + dispatch adapter.
2. Promotion eligibility/ranking service.
3. Transcript pilot có consent, anonymization và annotation.
4. Dashboard SLO/cost/quality theo provider và reason code.
5. Staging canary cho OpenAI/STT/TTS/telephony.

### P2 — production hardening

1. Multi-instance persistence, queue, backup/restore và replay/idempotency test.
2. Drift detection cho maps, pricing, policy và ASR.
3. Red-team voice/prompt injection, pentest và load test.
4. Data deletion/export workflow và audit RBAC.

## 9. Definition of Done

Một nguồn dữ liệu chỉ được coi là production-ready khi có owner, contract/schema, provenance,
version/effective date, credential qua secret manager, license được duyệt, cache/TTL, timeout/retry,
fallback, privacy/retention, monitoring/cost alert, golden tests và quy trình rollback. Nếu thiếu một
trong các mục này, trạng thái phải là `DEMO`, `PROTOTYPE` hoặc `STAGING_ONLY`, không ghi “đã thật”.
## 10. Dữ liệu nghiệm thu ZipFormer ASR

Artifact WAV đi kèm model chỉ là gate kỹ thuật, không phải corpus nghiệp vụ. Trước pilot cần dataset audio cuộc gọi
đã consent và ẩn danh, giữ liên kết giữa:

- `audio_id`, codec/sample rate/channel, thời lượng, SNR/noise bucket và thiết bị/telephony provider;
- vùng giọng/ngôn ngữ, transcript nguyên văn do người gán nhãn, guideline version và annotator agreement;
- raw ASR, confidence model-derived, transcript sau LLM rewrite, intent/entity/place resolution và handoff reason;
- model ID/revision, runtime/config, request latency, queue wait, RTF và outcome cuối.

Báo cáo phải có WER/CER tổng và theo slice: Bắc/Trung/Nam, địa chỉ/POI/tên riêng/số điện thoại, không dấu,
code-switching, nhiễu, mất gói và audio 8 kHz được resample. Tách train/tuning/eval theo người gọi để tránh
rò dữ liệu; không lưu raw audio/transcript vượt retention đã duyệt. Owner tối thiểu: Voice ML, QA, Privacy/Legal
và Support Ops. Không được dùng transcript do chính model sinh làm ground-truth.