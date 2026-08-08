# AloSM Voice AI — MVP Plan (3 tuần)

## 0. Mục tiêu MVP

MVP phải chứng minh được hành trình end-to-end:

**Khách gọi → nói nhu cầu → ASR → Agent hiểu & thu thập thông tin → Geocoding → xác nhận → Booking / Tra cứu chuyến → TTS trả lời → Handoff nếu cần.**

PRD chốt 3 tính năng **Must**: F1 Đặt xe bằng giọng nói, F2 Chuyển tổng đài viên kèm tóm tắt, F3 Tra cứu trạng thái chuyến. F4 FAQ là **Should**, có thể triển khai sau khi F1–F3 ổn định. PRD cũng yêu cầu 100% booking phải có xác nhận bằng lời nói trước khi gọi API, và 100% out-of-scope/thất bại 2 lần phải được handoff kèm tóm tắt.

> **Nguồn:** PRD v0.4 và architecture v1.0 của nhóm. PRD định nghĩa F1–F3 là Must, F4 là Should và Definition of Done là hoàn thành hành trình gọi → hiểu → xác nhận → đặt xe hoặc handoff. fileciteturn2file0L60-L74 fileciteturn2file0L153-L155

---

# 1. MVP Scope

## Must-have

### F1 — Đặt xe bằng giọng nói

Flow tối thiểu:

1. Nhận audio tiếng Việt.
2. ASR → transcript + confidence.
3. Agent xác định intent `booking`.
4. Thu thập:
   - pickup
   - destination
   - vehicle type nếu flow sản phẩm yêu cầu.
5. Geocode/resolve địa điểm.
6. Nếu địa điểm mơ hồ → hỏi người dùng chọn.
7. Đọc lại thông tin chuyến đi.
8. Chờ xác nhận bằng lời nói.
9. Chỉ sau khi xác nhận → gọi Booking API/mock API.
10. Trả booking ID / kết quả bằng TTS.

PRD yêu cầu AI phải nhớ thông tin giữa các lượt, không tự suy diễn thông tin chưa được cung cấp, xử lý địa điểm mơ hồ và dùng idempotency key để tránh booking trùng. fileciteturn2file0L76-L96

### F2 — Human Handoff + Context Transfer

Các trigger MVP:

- ASR thất bại 2 lần liên tiếp.
- Intent ngoài phạm vi.
- Người dùng yêu cầu gặp tổng đài viên.
- Backend/Booking API lỗi nghiêm trọng.

Handoff package tối thiểu:

```json
{
  "call_id": "...",
  "reason": "asr_failure | out_of_scope | api_failure | user_request",
  "intent": "booking",
  "pickup": "...",
  "destination": "...",
  "vehicle": "...",
  "summary": "...",
  "pending_action": "..."
}
```

PRD yêu cầu tóm tắt phải có lý do chuyển, thông tin đã thu thập và nội dung trao đổi chính; tổng đài viên phải nhận được summary trên Agent Desktop. fileciteturn2file0L98-L113

### F3 — Tra cứu trạng thái chuyến

Flow:

```text
User hỏi trạng thái
→ Agent xác định trip-status intent
→ Trip Status API
→ trả ETA/status
→ TTS
```

Thông tin chuyến phải được giới hạn theo đúng session/số điện thoại của khách. fileciteturn2file0L115-L127

---

# 2. Frontend / UX UI — yêu cầu tối thiểu

MVP không cần xây app mobile hoàn chỉnh. Có thể dùng web dashboard để mô phỏng hai vai trò: **khách hàng** và **tổng đài viên**.

## Customer UI

### Bắt buộc

- Nút Start/End Call.
- Microphone permission.
- Trạng thái kết nối: `Connecting / Listening / Processing / Speaking / Disconnected`.
- Hiển thị transcript realtime hoặc transcript gần realtime để debug.
- Hiển thị Booking State:
  - Pickup
  - Destination
  - Vehicle
  - Fare/ETA nếu có.
- Hiển thị confirmation trước booking.
- Thông báo rõ khi handoff.

### UX nguyên tắc

- Câu trả lời ngắn, dễ nghe; PRD đặt giới hạn ≤ 30 từ cho phản hồi AI.
- Không tự suy diễn địa chỉ.
- Luôn xác nhận trước hành động có tác động thực tế.
- Khi mất mạng phải hiển thị trạng thái reconnecting thay vì reset màn hình.

PRD xác định persona chính là người lớn tuổi/ít quen công nghệ/bận tay và yêu cầu câu trả lời ngắn, tốc độ vừa phải, xác nhận rõ ràng. fileciteturn2file0L43-L58 fileciteturn2file0L142-L151

## Operator UI

MVP dashboard chỉ cần:

- Danh sách cuộc gọi đang chờ handoff.
- Call ID.
- Lý do handoff.
- Pickup/destination/vehicle đã thu thập.
- Summary.
- Pending action.
- Nút `Accept Handoff`.

---

# 3. Backend & Data — yêu cầu tối thiểu

## Stack

- **FastAPI + Python 3.11** — API/realtime gateway.
- **Redis 7.x** — session state + counters + idempotency.
- **PostgreSQL 15** — persistent call/booking/audit data.
- **Celery** — chưa cần phức tạp ở tuần 1; dùng cho external tools khi bắt đầu cần async/background execution.
- **Docker Compose** — local development.

Architecture hiện tại đã chốt FastAPI + LangGraph, Redis + PostgreSQL và Docker Compose. fileciteturn2file1L480-L492

## MVP data

Redis phải lưu được tối thiểu:

```json
{
  "call_id": "...",
  "customer_phone_masked": "090*****89",
  "intent": "booking",
  "pickup": {...},
  "dropoff": {...},
  "vehicle": "4_seat",
  "confirmation_status": "pending",
  "failed_count": 0,
  "booking_id": null,
  "handoff_triggered": false
}
```

Architecture đã định nghĩa session Redis chứa call ID, intent, pickup, dropoff, confirmation, booking ID và handoff state; TTL 30 phút sau khi ngắt máy. fileciteturn2file1L360-L385

PostgreSQL MVP lưu:

- Call record.
- Booking record.
- Handoff record.
- Structured event/audit log.
- Transcript đã được xử lý theo yêu cầu privacy.

Không cần tối ưu database cho 1.000 concurrent calls ở MVP; ưu tiên schema sạch và API đúng.

---

# 4. ASR / TTS — yêu cầu tối thiểu

## ASR

- Whisper hoặc Vietnamese ASR.
- Input: audio PCM/chunk.
- Output:
  - transcript
  - confidence score nếu model/provider hỗ trợ.
- Có cơ chế nhận diện thất bại.
- Sau 2 lần thất bại → handoff.

Architecture đã xác định ASR là Whisper/Vietnamese ASR và output gồm text + confidence. fileciteturn2file1L343-L348

## TTS

- Neural Vietnamese TTS.
- Có thể bắt đầu bằng non-streaming TTS để đạt MVP.
- Cache các câu static:
  - greeting
  - confirmation mẫu
  - handoff message
  - error message.

PRD khuyến nghị cache audio TTS tĩnh và tối ưu speech computing bằng VAD/early stream termination. fileciteturn2file0L142-L150

---

# 5. LLM / Agentic System — yêu cầu tối thiểu

## Agent State

Dùng **LangGraph** để quản lý state machine/hội thoại có vòng lặp.

```text
START
  ↓
Receive ASR
  ↓
Intent
  ↓
Collect missing information
  ↓
Resolve location
  ↓
Confirm
  ↓
Tool call
  ↓
Respond
```

Agent phải hỗ trợ loop:

```text
Thiếu pickup → hỏi pickup
Thiếu destination → hỏi destination
Địa chỉ mơ hồ → hỏi chọn
User sửa thông tin → update state
ASR fail → retry
Out-of-scope → handoff
```

Architecture đã chọn LangGraph thay vì Sequential Chain vì bài toán có vòng lặp hỏi lại/sửa thông tin. fileciteturn2file1L519-L526

## Tool tối thiểu

- `geocode_location`
- `book_ride`
- `get_trip_status`
- `handoff`

FAQ/RAG là **Should**, chỉ implement sau khi F1–F3 ổn định.

---

# 6. Kế hoạch 3 tuần MVP

| Tuần | Mục tiêu | Output | Ưu tiên |
|---|---|---|---|
| **Week 1** | Skeleton + happy path | Backend chạy được, Redis/Postgres, API contract, Agent state, ASR/TTS basic | P0 |
| **Week 2** | Hoàn thiện F1–F3 | Booking, geocoding, trip status, confirmation, basic handoff | P0 |
| **Week 3** | Integration + UAT | Voice end-to-end, operator dashboard, error handling, demo-ready | P0 |

## Week 1 — Backend Foundation

### P0

- Tạo FastAPI project.
- Docker Compose.
- PostgreSQL connection.
- Redis connection.
- Session CRUD.
- Booking/Call/Handoff schema.
- API contract.
- LangGraph state skeleton.
- Mock ASR/TTS integration.
- Mock Booking API.

### P1

- Structured logging.
- Basic authentication giữa frontend/backend.
- Health check.

### Definition of Done

```text
Frontend
  ↓
FastAPI
  ↓
LangGraph
  ↓
Redis/Postgres
```

chạy end-to-end với mock speech và mock booking.

---

## Week 2 — Business Features

### P0

- F1 booking flow.
- Geocoding.
- Address ambiguity handling.
- Confirmation.
- Idempotency key.
- F3 trip status.
- F2 handoff trigger.
- Handoff summary.

### P1

- Timeout/retry cơ bản.
- Error mapping.
- Basic metrics.

### Definition of Done

Có thể demo:

```text
"Đặt xe từ A đến B"
→
AI hỏi thông tin thiếu
→
Geocode
→
Confirm
→
Booking
```

và:

```text
ASR fail x2
→
Summary
→
Operator Dashboard
```

---

## Week 3 — Integration & MVP Hardening

### P0

- Kết nối voice pipeline thật.
- Streaming audio cơ bản.
- TTS playback.
- Operator dashboard.
- Full handoff flow.
- Error handling.
- Session persistence.
- End-to-end test.
- Demo script.

### P1

- Heartbeat/reconnect cơ bản.
- TTS cache.
- Structured logging.
- Latency measurement.

### MVP Demo Scenarios

1. Happy path booking.
2. Thiếu pickup.
3. Địa chỉ mơ hồ.
4. User sửa destination.
5. User nói không muốn đặt nữa.
6. ASR fail 2 lần.
7. Out-of-scope.
8. Trip status.
9. Handoff summary.
10. Booking API failure.

---

# 7. MVP Definition of Done

MVP được coi là hoàn thành khi:

- [ ] F1 hoạt động end-to-end.
- [ ] F2 hoạt động end-to-end.
- [ ] F3 hoạt động end-to-end.
- [ ] Booking luôn có verbal confirmation.
- [ ] Địa chỉ mơ hồ được hỏi lại.
- [ ] ASR fail 2 lần → handoff.
- [ ] Out-of-scope → handoff.
- [ ] Handoff có summary.
- [ ] Session được lưu Redis.
- [ ] Call/booking/handoff được lưu PostgreSQL.
- [ ] Có basic monitoring/logging.
- [ ] Có demo voice end-to-end.

Mục tiêu pilot của PRD: Booking Completion Rate ≥80%, Unassisted Automation Rate ≥65%, và 100% out-of-scope/failure 2 lần được handoff kèm summary. fileciteturn2file0L32-L41

---

# 8. Những thứ KHÔNG được phép làm trước MVP

- Không xây microservices phức tạp.
- Không tối ưu Kubernetes.
- Không tự viết voice infrastructure nếu có thể dùng provider.
- Không fine-tune ASR/TTS khi baseline chưa được đo.
- Không xây multi-agent system phức tạp.
- Không làm payment/refund.
- Không làm driver dispatch/matching.
- Không làm complaint/tai nạn trong AI.

PRD đã loại payment/refund, complaint/accident và driver dispatch khỏi MVP. fileciteturn2file0L60-L70
