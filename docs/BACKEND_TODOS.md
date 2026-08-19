# AloSM Voice AI — Backend TODOs

**Owner:** Backend Engineer
**Timeline:** 6 tuần
**Mốc:** MVP hết Week 3 → Demo Day hardening/expansion Week 4–6

---

# 0. Backend Mission

Backend chịu trách nhiệm biến AI Voice Agent thành một hệ thống có thể chạy ổn định:

```text
Voice Input
    ↓
Voice Gateway / API
    ↓
Session + Agent State
    ↓
LangGraph
    ↓
Tools / External APIs
    ↓
Booking / Trip / Handoff
    ↓
Persistence + Observability
```

Ba mục tiêu chính:

1. **Correctness:** không booking sai, không mất state.
2. **Reliability:** API/voice/network lỗi không làm mất cuộc gọi.
3. **Scalability:** kiến trúc có thể mở rộng sau MVP mà không phải rewrite.

Architecture đã chốt FastAPI + LangGraph ở AI Core, Redis + PostgreSQL cho data, ASR/TTS riêng và Alo SM APIs cho nghiệp vụ. fileciteturn2file1L208-L230

---

# 1. Tech Stack

| Layer         | MVP                          | Demo Day                          | Mục đích                |
| ------------- | ---------------------------- | --------------------------------- | -------------------------- |
| Backend       | FastAPI                      | FastAPI + multiple replicas       | Async API/realtime gateway |
| Agent         | LangGraph                    | LangGraph + policy layer          | Stateful agent             |
| Cache/session | Redis 7                      | Redis + TTL + locking/idempotency | Session/recovery           |
| DB            | PostgreSQL 15                | PostgreSQL + indexes              | Persistent data/audit      |
| Queue         | Celery                       | Celery worker pool                | Background jobs            |
| Voice         | WebRTC/WebSocket gateway     | Streaming + reconnect             | Realtime audio             |
| ASR           | Whisper/Vietnamese ASR       | Streaming ASR + benchmark         | Speech recognition         |
| TTS           | Vietnamese Neural TTS        | Streaming TTS + cache             | Speech synthesis           |
| Maps          | Google Maps/Places/Geocoding | Timeout/retry/cache               | Location resolution        |
| Booking       | Mock/Alo SM API              | Resilient adapter                 | Booking                    |
| FAQ           | ChromaDB nếu kịp           | RAG + evaluation                  | FAQ                        |
| Container     | Docker Compose               | Docker + deploy                   | Reproducibility            |
| Monitoring    | Structured logs              | Metrics + dashboard + alerts      | Observability              |

Architecture hiện tại ghi nhận Redis 7.x, PostgreSQL 15, ChromaDB, Docker Compose và FastAPI Python 3.11. fileciteturn2file1L360-L366 fileciteturn2file1L480-L492

---

# 2. Folder Structure

Đề xuất **modular monolith** cho 6 tuần: đủ sạch để scale nhưng không over-engineer microservices.

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── calls.py
│   │       ├── sessions.py
│   │       ├── bookings.py
│   │       ├── trips.py
│   │       ├── handoffs.py
│   │       └── health.py
│   │
│   ├── controllers/
│   │   ├── call_controller.py
│   │   ├── session_controller.py
│   │   ├── booking_controller.py
│   │   ├── trip_controller.py
│   │   └── handoff_controller.py
│   │
│   ├── services/
│   │   ├── call_service.py
│   │   ├── session_service.py
│   │   ├── booking_service.py
│   │   ├── trip_service.py
│   │   ├── geocoding_service.py
│   │   ├── handoff_service.py
│   │   └── summary_service.py
│   │
│   ├── agent/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── nodes/
│   │   │   ├── intent.py
│   │   │   ├── collect.py
│   │   │   ├── confirm.py
│   │   │   ├── booking.py
│   │   │   ├── trip_status.py
│   │   │   └── handoff.py
│   │   ├── tools/
│   │   │   ├── geocode.py
│   │   │   ├── booking.py
│   │   │   ├── trip_status.py
│   │   │   └── faq.py
│   │   └── policies/
│   │       └── handoff_policy.py
│   │
│   ├── integrations/
│   │   ├── redis_client.py
│   │   ├── postgres.py
│   │   ├── maps_client.py
│   │   ├── booking_client.py
│   │   ├── trip_client.py
│   │   ├── asr_client.py
│   │   └── tts_client.py
│   │
│   ├── schemas/
│   │   ├── call.py
│   │   ├── session.py
│   │   ├── booking.py
│   │   ├── trip.py
│   │   ├── handoff.py
│   │   └── common.py
│   │
│   ├── models/
│   │   ├── call.py
│   │   ├── booking.py
│   │   ├── handoff.py
│   │   └── event.py
│   │
│   ├── repositories/
│   │   ├── call_repository.py
│   │   ├── booking_repository.py
│   │   ├── handoff_repository.py
│   │   └── event_repository.py
│   │
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks.py
│   │
│   └── observability/
│       ├── logging.py
│       ├── metrics.py
│       └── tracing.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── migrations/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

**Nguyên tắc:** Controller mỏng → Service xử lý business logic → Repository xử lý DB → Integration adapter gọi external service.

---

# 3. API Endpoints

## 3.1 Call / Voice

### `POST /api/v1/calls`

Tạo call session.

**Request**

```json
{
  "customer_phone": "0901234567"
}
```

**Response**

```json
{
  "call_id": "call_123",
  "session_id": "sess_123",
  "status": "active"
}
```

### `WS /api/v1/calls/{call_id}/stream`

Realtime audio stream.

Responsibilities:

- nhận audio chunks
- forward ASR
- nhận TTS audio
- heartbeat
- disconnect/reconnect

---

# 4. Session API

### `GET /api/v1/sessions/{session_id}`

Lấy Booking State.

### `PATCH /api/v1/sessions/{session_id}`

Cập nhật state nếu cần từ frontend/operator.

### `POST /api/v1/sessions/{session_id}/resume`

Resume session sau disconnect.

---

# 5. Booking API

### `POST /api/v1/bookings`

Tạo booking sau khi Agent đã nhận confirmation.

Headers:

```text
Idempotency-Key: <uuid>
```

**Request**

```json
{
  "session_id": "sess_123",
  "pickup": {
    "name": "Vincom Đồng Khởi",
    "lat": 10.77,
    "lng": 106.70
  },
  "destination": {
    "name": "Landmark 81",
    "lat": 10.79,
    "lng": 106.72
  },
  "vehicle_type": "4_seat"
}
```

**Rule:** endpoint phải reject nếu `confirmation_status != confirmed`.

---

# 6. Trip API

### `GET /api/v1/trips/status`

Query theo session/customer identity.

```text
GET /api/v1/trips/status?session_id=sess_123
```

Response:

```json
{
  "trip_id": "trip_123",
  "status": "driver_arriving",
  "eta_minutes": 5
}
```

PRD yêu cầu chỉ cung cấp thông tin chuyến đúng với số điện thoại/phiên gọi của khách. fileciteturn2file0L123-L127

---

# 7. Handoff API

### `POST /api/v1/handoffs`

Tạo yêu cầu handoff.

```json
{
  "session_id": "sess_123",
  "reason": "asr_failure",
  "summary": "Khách muốn đặt xe...",
  "pending_action": "Xác nhận điểm đến"
}
```

### `GET /api/v1/handoffs?status=pending`

Operator dashboard lấy các handoff đang chờ.

### `POST /api/v1/handoffs/{handoff_id}/accept`

Tổng đài viên nhận cuộc gọi.

---

# 8. Health / Observability API

### `GET /health`

### `GET /ready`

Kiểm tra:

- PostgreSQL
- Redis
- external dependencies nếu cần.

---

# 9. DTOs

## CreateCallDTO

```python
class CreateCallDTO(BaseModel):
    customer_phone: str
```

## SessionDTO

```python
class SessionDTO(BaseModel):
    session_id: str
    call_id: str
    intent: str | None
    pickup: LocationDTO | None
    destination: LocationDTO | None
    vehicle_type: str | None
    confirmation_status: str
    failed_count: int
    booking_id: str | None
    handoff_triggered: bool
```

## LocationDTO

```python
class LocationDTO(BaseModel):
    name: str
    lat: float
    lng: float
    place_id: str | None = None
```

## BookingRequestDTO

```python
class BookingRequestDTO(BaseModel):
    session_id: str
    pickup: LocationDTO
    destination: LocationDTO
    vehicle_type: str
```

## BookingResponseDTO

```python
class BookingResponseDTO(BaseModel):
    booking_id: str
    status: str
    eta_minutes: int | None
```

## HandoffDTO

```python
class HandoffDTO(BaseModel):
    session_id: str
    reason: str
    summary: str
    pending_action: str | None
```

---

# 10. Controller Responsibilities

## CallController

```text
start call
stream audio
end call
```

Không chứa AI/business logic.

## SessionController

```text
get session
resume session
update session
```

## BookingController

```text
validate confirmation
validate idempotency
call BookingService
```

## TripController

```text
validate session identity
call TripService
```

## HandoffController

```text
create handoff
get pending handoffs
accept handoff
```

---

# 11. Database Schema

## `calls`

```text
calls
-------------------------
id UUID PK
customer_phone_hash TEXT
started_at TIMESTAMP
ended_at TIMESTAMP
status TEXT
final_intent TEXT
handoff BOOLEAN
created_at TIMESTAMP
```

Không lưu raw phone trong structured logs.

## `bookings`

```text
bookings
-------------------------
id UUID PK
call_id UUID FK
external_booking_id TEXT
pickup_name_encrypted TEXT
pickup_lat NUMERIC
pickup_lng NUMERIC
destination_name_encrypted TEXT
destination_lat NUMERIC
destination_lng NUMERIC
vehicle_type TEXT
status TEXT
idempotency_key TEXT UNIQUE
created_at TIMESTAMP
```

## `handoffs`

```text
handoffs
-------------------------
id UUID PK
call_id UUID FK
reason TEXT
summary TEXT
pending_action TEXT
status TEXT
operator_id TEXT NULL
created_at TIMESTAMP
accepted_at TIMESTAMP NULL
```

## `conversation_events`

```text
conversation_events
-------------------------
id BIGSERIAL PK
call_id UUID FK
event_type TEXT
intent TEXT NULL
action TEXT NULL
metadata JSONB
created_at TIMESTAMP
```

Ví dụ event:

```json
{
  "event_type": "tool_call",
  "action": "geocode_location",
  "metadata": {
    "latency_ms": 421,
    "success": true
  }
}
```

---

# 12. Redis Session Schema

Key:

```text
session:{session_id}
```

Value:

```json
{
  "call_id": "call_123",
  "customer_phone_masked": "090*****89",
  "status": "collecting",
  "intent": "booking",
  "pickup": {
    "name": "Vincom Đồng Khởi",
    "lat": 10.77,
    "lng": 106.70
  },
  "destination": null,
  "vehicle_type": "4_seat",
  "confirmation_status": "pending",
  "failed_count": 1,
  "last_action": "collect_destination",
  "booking_id": null,
  "handoff_triggered": false,
  "updated_at": "..."
}
```

TTL MVP:

```text
30 minutes after disconnect
```

Đây phù hợp với architecture đã chốt. fileciteturn2file1L360-L385

---

# 13. LangGraph State

```python
class AgentState(TypedDict):
    session_id: str
    intent: str | None
    pickup: Location | None
    destination: Location | None
    vehicle_type: str | None
    confirmation_status: str
    asr_confidence: float | None
    failed_count: int
    last_user_text: str | None
    last_action: str | None
    tool_result: dict | None
    handoff_candidate: bool
    handoff_reason: str | None
```

Flow MVP:

```text
ASR
 ↓
Intent
 ↓
Collect
 ↓
Geocode
 ↓
Confirm
 ↓
Tool
 ↓
Response
```

Architecture hiện tại cũng mô hình hóa Agent như state machine với collect → confirm → booking/trip/FAQ → handoff. fileciteturn2file1L300-L337

---

# 14. Handoff Decision Layer

**Không dùng một Agent riêng để quyết định handoff.**

Planner Agent chỉ đưa ra `handoff_candidate`; backend policy layer quyết định cuối cùng.

## MVP policy

```python
if asr_failed_count >= 2:
    handoff("asr_failure")

elif intent not in SUPPORTED_INTENTS:
    handoff("out_of_scope")

elif user_requested_human:
    handoff("user_request")

elif critical_tool_failure:
    handoff("tool_failure")

else:
    continue_agent()
```

PRD hiện tại xác định ASR fail 2 lần, out-of-scope và user request là các trigger chính; architecture cũng ghi nhận rule-based + LLM vì business rules cần deterministic. fileciteturn2file0L98-L113 fileciteturn2file1L519-L526

---

# 15. Giai đoạn 1 — MVP / Week 1–3

## Week 1 — Foundation

### P0 / Dễ–Trung bình

- [ ] Setup FastAPI.
- [ ] Setup PostgreSQL.
- [ ] Setup Redis.
- [ ] Docker Compose.
- [ ] SQLAlchemy/Alembic.
- [ ] Define DTOs.
- [ ] Define DB schemas.
- [ ] Define Redis session schema.
- [ ] Implement `/calls`.
- [ ] Implement session service.
- [ ] Implement health endpoints.

### P0 / Trung bình

- [ ] LangGraph state.
- [ ] Basic Agent Gateway.
- [ ] Mock ASR adapter.
- [ ] Mock TTS adapter.
- [ ] Mock Booking API.

### P1 / Dễ

- [ ] Structured logging.
- [ ] Unit tests.
- [ ] `.env.example`.

### Week 1 checkpoint

```text
Frontend
 ↓
FastAPI
 ↓
LangGraph
 ↓
Redis + PostgreSQL
 ↓
Mock tools
```

---

# 16. Week 2 — Business Features

## P0 / Trung bình

- [ ] `GeocodingService`.
- [ ] Google Maps adapter.
- [ ] Booking adapter.
- [ ] Trip Status adapter.
- [ ] Confirmation enforcement.
- [ ] Idempotency key.
- [ ] F1 booking.
- [ ] F3 trip status.

## P0 / Trung bình–Khó

- [ ] Handoff Service.
- [ ] Handoff DTO.
- [ ] Summary generation.
- [ ] Operator dashboard API.

## P1

- [ ] Timeout.
- [ ] Retry.
- [ ] Error mapping.

### Week 2 checkpoint

Happy path:

```text
ASR
 ↓
Agent
 ↓
Geocode
 ↓
Confirm
 ↓
Booking
```

Handoff path:

```text
ASR fail x2
 ↓
Policy
 ↓
Summary
 ↓
Operator
```

---

# 17. Week 3 — Voice Integration + MVP Hardening

## P0 / Khó

- [ ] WebRTC/WebSocket integration.
- [ ] Audio chunk handling.
- [ ] ASR real integration.
- [ ] TTS real integration.
- [ ] End-to-end voice flow.
- [ ] Handoff flow.
- [ ] Operator dashboard integration.

## P0 / Trung bình

- [ ] Session persistence.
- [ ] Error recovery.
- [ ] Booking duplicate prevention.
- [ ] E2E tests.
- [ ] Demo scenarios.

## P1

- [ ] Basic heartbeat.
- [ ] Basic reconnect.
- [ ] TTS static cache.
- [ ] Latency metrics.

### Week 3 Definition of Done

```text
CALL
 ↓
ASR
 ↓
AGENT
 ↓
GEOCODING
 ↓
CONFIRM
 ↓
BOOKING
 ↓
TTS
```

hoặc:

```text
CALL
 ↓
FAIL / OOS
 ↓
SUMMARY
 ↓
HUMAN
```

---

# 18. Giai đoạn 2 — Demo Day / Week 4–6

Mục tiêu không phải thêm thật nhiều feature, mà **biến MVP thành hệ thống đáng tin cậy để demo và nghiên cứu**.

Các ưu tiên chính:

1. Network reliability.
2. Concurrency/scalability.
3. Latency.
4. Observability.
5. Handoff quality.
6. AI evaluation.

---

# 19. Week 4 — Network Reliability

## P0 / Trung bình

### Heartbeat

```text
Client PING
 ↓
Server PONG
```

Nếu timeout:

```text
ACTIVE → SUSPENDED
```

### Graceful Resume

```text
Reconnect
 ↓
Session ID
 ↓
Redis
 ↓
Restore State
 ↓
Continue
```

### Session Lock

Đảm bảo một session không bị hai worker xử lý đồng thời.

## P1

- Redis TTL cleanup.
- Reconnect testing.
- Network interruption simulation.

### Demo scenario

> Tắt WiFi 10 giây giữa cuộc gọi → bật lại → conversation tiếp tục đúng state.

---

# 20. Week 5 — Scalability + Reliability

## P0 / Khó

### Celery Worker Pool

Tách các tác vụ không cần block voice loop:

```text
Agent
 ↓
Celery
 ├── Geocoding
 ├── Trip Status
 └── Booking
```

### Tool timeout

```text
Timeout
 ↓
Retry
 ↓
Exponential Backoff
 ↓
Fallback/Handoff
```

### Concurrency test

Benchmark:

```text
10 calls
50 calls
100 calls
500 calls
1000 calls
```

Theo dõi:

- p50 latency
- p95 latency
- error rate
- queue wait time
- CPU/RAM
- Redis latency

## P1

- DB indexes.
- Connection pooling.
- Redis connection pooling.
- Rate limiting.
- API circuit breaker.

---

# 21. Week 6 — Observability + Demo Day

## P0

### Metrics

- Call success rate.
- Booking completion rate.
- Handoff rate.
- False handoff rate.
- ASR confidence.
- STT latency.
- LLM latency.
- TTS latency.
- Tool latency.
- Booking API error rate.
- Reconnect success rate.

Architecture đặt baseline monitoring gồm p95 end-to-end latency ≤2.5s, ASR confidence ≥0.85, booking success ≥80%, automation ≥65%. Đây là các target để benchmark, không nên coi là đạt được trước khi test thực tế. fileciteturn2file1L507-L515

### Dashboard

```text
Calls
├── Active
├── Completed
├── Handoff
└── Failed

Latency
├── ASR
├── LLM
├── Tool
└── TTS

Reliability
├── Reconnect
├── Timeout
└── Error
```

## P0

- [ ] Full demo rehearsal.
- [ ] Failure injection.
- [ ] Network failure demo.
- [ ] Handoff demo.
- [ ] 100-call load test.
- [ ] Evaluation report.

---

# 22. Reliability Architecture — Demo Day

```text
                         ┌───────────────┐
                         │    Client     │
                         └───────┬───────┘
                                 │
                           WebRTC/WS
                                 │
                    ┌────────────▼────────────┐
                    │   FastAPI Gateway       │
                    └────────────┬────────────┘
                                 │
                     ┌───────────▼───────────┐
                     │    Session Manager     │
                     └──────┬─────────┬───────┘
                            │         │
                         Redis      PostgreSQL
                            │
                    ┌───────▼────────┐
                    │  LangGraph     │
                    │    Agent       │
                    └───────┬────────┘
                            │
                ┌───────────┼────────────┐
                │           │            │
             Geocode     Trip API     Booking
                │           │            │
                └───────────┼────────────┘
                            │
                         Celery
                            │
                     External Workers
                            │
                    ┌───────▼────────┐
                    │ Observability  │
                    └────────────────┘
```

---

# 23. Network Reliability — 3 lớp

## Context Persistence

**Mục tiêu:** không mất state.

```text
BookingState → Redis
```

## Heartbeat

**Mục tiêu:** phát hiện disconnect.

```text
PING → PONG
```

## Graceful Resume

**Mục tiêu:** reconnect không bắt đầu lại.

```text
Reconnect → SessionID → Redis → Resume
```

Ba cơ chế bổ trợ nhau, không phải ba lựa chọn thay thế.

Architecture đã quy định session Redis tồn tại 30 phút sau disconnect và có state machine Active → Collecting → Confirming → Booking/Handoff → Done. fileciteturn2file1L388-L404

---

# 24. Background Jobs

Không đưa tất cả tác vụ vào Celery.

## Không nên queue

- Audio streaming.
- User response cần realtime.
- Agent turn chính.

## Có thể queue

- Geocoding retry.
- Trip status polling nếu cần.
- Booking API retry.
- Generate long-form summary.
- Analytics.
- Async persistence.

Nguyên tắc:

> **Voice loop phải ngắn; tác vụ có thể chậm thì đưa ra worker.**

---

# 25. Tool Reliability

Mỗi external tool nên có adapter:

```text
Agent
 ↓
Tool Interface
 ↓
Service
 ↓
External Client
```

Ví dụ:

```python
class GeocodingClient:
    async def search(self, query: str): ...
```

Không để Agent biết HTTP details.

---

# 26. Timeout / Retry Policy

MVP:

```text
Timeout
 ↓
Retry 1–2 lần
 ↓
Fail
 ↓
Handoff / fallback
```

Demo Day:

- exponential backoff
- retry only transient errors
- không retry 4xx business errors
- idempotency cho booking
- circuit breaker nếu cần.

---

# 27. Idempotency

Booking là operation nguy hiểm nhất.

Request:

```text
Idempotency-Key: uuid
```

Backend:

```text
Request
 ↓
Check Redis/DB
 ↓
Already processed?
 ├── YES → return old result
 └── NO → create booking
```

PRD yêu cầu mỗi booking request có idempotency key để tránh tạo booking trùng. fileciteturn2file0L87-L96

---

# 28. Observability Event Model

Mọi action quan trọng tạo event:

```json
{
  "call_id": "call_123",
  "event": "tool_call",
  "tool": "geocode",
  "latency_ms": 423,
  "success": true,
  "timestamp": "..."
}
```

Các event quan trọng:

```text
call_started
asr_result
intent_detected
state_updated
tool_started
tool_completed
confirmation_requested
booking_requested
booking_completed
handoff_candidate
handoff_completed
call_disconnected
call_resumed
call_completed
```

PRD yêu cầu structured JSON logging với timestamp, intent, entities, action và handoff reason, đồng thời không để raw phone/address trong log. fileciteturn2file0L142-L151

---

# 29. Research Questions

## RQ1 — Human Handoff

> Làm thế nào để giảm unnecessary human handoff nhưng vẫn duy trì task completion cao?

Metrics:

- Handoff rate.
- False handoff rate.
- Missed handoff rate.
- Task completion rate.

---

## RQ2 — Context Recovery

> Context persistence có giúp giảm task restart rate khi mạng không ổn định không?

Experiment:

```text
Control: không resume
Treatment: Redis + resume
```

Metrics:

- successful resume rate
- repeated information count
- completion rate

---

## RQ3 — Streaming vs Non-streaming

> Streaming audio có giảm voice-to-voice latency đủ đáng kể để cải thiện UX không?

So sánh:

```text
Batch ASR → LLM → TTS
```

vs

```text
Streaming ASR → LLM → Streaming TTS
```

Metric:

- p50/p95 latency.
- user interruption.
- abandonment.

---

## RQ4 — Rule-based vs LLM Handoff

> Policy deterministic có giảm false handoff và tăng tính ổn định so với để LLM tự quyết định không?

Khuyến nghị kiến trúc:

```text
LLM
 ↓
Handoff Candidate
 ↓
Deterministic Policy
 ↓
Decision
```

Không dùng một Agent thứ hai chỉ để quyết định handoff.

---

## RQ5 — Concurrency

> Kiến trúc FastAPI + Redis + Celery chịu được bao nhiêu concurrent calls trước khi p95 latency vượt SLA?

Load test:

```text
10 → 50 → 100 → 500 → 1000 calls
```

---

# 30. Các hướng mở rộng sau Demo Day

## Priority A

- Streaming ASR/TTS tối ưu.
- Barge-in/VAD.
- Graceful reconnect.
- Celery worker scaling.
- Load balancing.
- Circuit breaker.
- Distributed tracing.

## Priority B

- FAQ RAG với ChromaDB.
- Better handoff summarization.
- Agent evaluation framework.
- Automated regression test set.
- Conversation replay.

## Priority C

- Multi-agent architecture.
- Advanced personalization.
- Real-time driver ETA.
- Production telephony/SIP integration.

Không nên chuyển sang multi-agent chỉ để làm hệ thống “agentic” hơn. PRD/architecture hiện tại đã xác định LangGraph state machine + tool orchestration là đủ cho workflow có vòng lặp; reliability và evaluation có giá trị hơn việc thêm agent không cần thiết. fileciteturn2file1L519-L526

---

# 31. Backend Priority Matrix

| Task                   | Priority | Difficulty | Phase |
| ---------------------- | -------: | ---------: | ----- |
| FastAPI skeleton       |       P0 |         ⭐ | MVP   |
| PostgreSQL schema      |       P0 |       ⭐⭐ | MVP   |
| Redis session          |       P0 |       ⭐⭐ | MVP   |
| LangGraph state        |       P0 |     ⭐⭐⭐ | MVP   |
| Booking API            |       P0 |       ⭐⭐ | MVP   |
| Geocoding              |       P0 |       ⭐⭐ | MVP   |
| Trip Status            |       P0 |       ⭐⭐ | MVP   |
| Handoff API            |       P0 |       ⭐⭐ | MVP   |
| Summary                |       P0 |       ⭐⭐ | MVP   |
| Voice WebSocket/WebRTC |       P0 |   ⭐⭐⭐⭐ | MVP   |
| Idempotency            |       P0 |       ⭐⭐ | MVP   |
| Heartbeat              |       P1 |       ⭐⭐ | Demo  |
| Graceful Resume        |       P0 |     ⭐⭐⭐ | Demo  |
| Celery                 |       P1 |     ⭐⭐⭐ | Demo  |
| Timeout/Retry          |       P0 |       ⭐⭐ | Demo  |
| Load testing           |       P0 |     ⭐⭐⭐ | Demo  |
| Observability          |       P0 |     ⭐⭐⭐ | Demo  |
| Circuit breaker        |       P2 |   ⭐⭐⭐⭐ | Demo  |
| Distributed tracing    |       P2 |   ⭐⭐⭐⭐ | Demo  |
| Advanced RAG           |       P2 |     ⭐⭐⭐ | Demo  |

---

# 32. Final Backend Definition of Done

## MVP — Week 3

- [ ] F1 booking end-to-end.
- [ ] F2 handoff end-to-end.
- [ ] F3 trip status end-to-end.
- [ ] Redis session.
- [ ] PostgreSQL persistence.
- [ ] Confirmation before booking.
- [ ] Idempotency.
- [ ] Basic timeout/retry.
- [ ] Basic logging.
- [ ] Voice integration.

## Demo Day — Week 6

- [ ] Session persistence + graceful resume.
- [ ] Heartbeat/disconnect detection.
- [ ] Streaming audio.
- [ ] Celery workers.
- [ ] Tool timeout/retry.
- [ ] Concurrency benchmark.
- [ ] Observability dashboard.
- [ ] Handoff quality evaluation.
- [ ] Failure injection demo.
- [ ] Documented architecture + research results.

---

# 33. Nguyên tắc cuối cùng cho BE

> **Đừng cố xây một backend production-scale ngay từ Week 1.**

Chiến lược:

```text
Week 1–3
Simple + Correct + Demo-able

        ↓

Week 4–6
Reliable + Observable + Scalable
```

MVP cần chứng minh **business flow hoạt động**. Demo Day cần chứng minh **hệ thống có tư duy production**.
