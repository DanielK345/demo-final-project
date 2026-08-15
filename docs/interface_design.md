# Interface Design — F1+F2: Đặt xe bằng giọng nói

**Phiên bản:** 0.1 · **Trạng thái:** Proposed · **Owner:** Backend Lead  
**PRD nguồn:** [`PRD_AloSM_Voice.md`](PRD_AloSM_Voice.md) · **Architecture nguồn:** [`architecture_diagram.md`](architecture_diagram.md)

> Đây là Interface Design **chỉ cho Feature F1+F2 — Đặt xe bằng giọng nói**. Interface của F3 (Tra cứu chuyến), F4 (FAQ) sẽ được bổ sung khi từng feature được breakdown và bắt đầu làm task.

---

## 1. Scope và nguyên tắc

Tài liệu chỉ thiết kế contract phục vụ hero flow của F1+F2: **nhận cuộc gọi → nghe & hiểu ý định → thu thập điểm đón/đến → xác nhận → đặt xe → chuyển tổng đài viên khi cần**. Auth dùng chung nhưng contract đăng nhập nằm ngoài phạm vi tài liệu này.

F3 — Tra cứu chuyến xe, F4 — Hỏi đáp FAQ sẽ có Interface Design riêng khi feature tương ứng đi vào implementation. Contract phải được chốt trong task trước khi Frontend và Backend code.

- Base path: `/v1`; health check không version hóa.
- Payload dùng JSON; audio stream dùng WebSocket; thời gian dùng ISO 8601 UTC; ID dùng UUID.
- Auth dùng OAuth2 Bearer Token giữa các service nội bộ.
- Request thành công và lỗi đều trả `request_id`, trừ response `204`.
- Thêm optional field là backward-compatible; breaking change tạo `/v2`.

## 2. Consumers và trust boundary

| Consumer | Được phép | Không được phép |
|---|---|---|
| Telephony Gateway | Tạo session cuộc gọi, stream audio | Tự gọi Booking API |
| AI Agent Core | Gọi Tool APIs (Geocoding, Booking, Handoff) | Bỏ qua bước xác nhận của khách (BR-001) |
| Alo SM Backend | Nhận lệnh đặt xe, trả booking status | Truy cập Redis/PostgreSQL của Voice Agent |
| Agent Desktop CRM | Nhận tóm tắt handoff context | Thay đổi session voice đang hoạt động |

Authorization luôn kiểm tra ở API; kịch bản thoại không được coi là biện pháp bảo mật.

## 3. Shared contract

### 3.1 Error envelope

```json
{
  "error": {
    "code": "CONFIRMATION_REQUIRED",
    "message": "Cần xác nhận trước khi đặt xe.",
    "request_id": "req_01J...",
    "details": {}
  }
}
```

`message` dùng để hiển thị; Voice Engine rẽ nhánh theo `code`, không parse nội dung message.

### 3.2 Trạng thái dùng chung

| Type | Values |
|---|---|
| `SessionStatus` | `active`, `collecting`, `pending_confirmation`, `booking_dispatched`, `completed`, `handoff`, `failed` |
| `ConfirmationStatus` | `unconfirmed`, `confirmed`, `rejected` |
| `HandoffReason` | `USER_REQUEST`, `ASR_FAILED_TWICE`, `OUT_OF_SCOPE`, `BACKEND_ERROR` |
| `BookingStatus` | `pending`, `driver_assigning`, `confirmed`, `cancelled`, `failed` |

## 4. Endpoint map

| Method | Endpoint | Actor | Mục đích | Success |
|---|---|---|---|---|
| `POST` | `/v1/voice/sessions` | Telephony Gateway | Tạo session cuộc gọi mới | `201` |
| `POST` | `/v1/voice/sessions/{id}/interact` | Voice Gateway | Gửi transcript từ ASR để AI xử lý | `200` |
| `POST` | `/v1/bookings` | AI Agent | Đặt xe (cần Idempotency-Key) | `201` |
| `POST` | `/v1/voice/sessions/{id}/handoff` | AI Agent | Chuyển sang tổng đài viên | `200` |
| `GET` | `/health/live` | Platform | Process sống | `200` |
| `GET` | `/health/ready` | Platform | Dependencies sẵn sàng | `200/503` |

## 5. Contract theo hero flow

### 5.1 Tạo session cuộc gọi — `POST /v1/voice/sessions`

Khi khách gọi 1555, Telephony Gateway tạo session:

| Field | Type | Required | Rule |
|---|---|---|---|
| `call_id` | string | Có | UUID từ SIP Gateway |
| `customer_phone` | string | Có | SĐT khách, mã hóa khi lưu |
| `started_at` | datetime | Có | ISO 8601 UTC |

Response `201`:

```json
{
  "session_id": "sess-88123-uuid",
  "call_id": "call-v2-99812-uuid",
  "status": "active",
  "initial_prompt": "Xin chào, em là trợ lý ảo của Alo SM. Em giúp gì ạ?",
  "request_id": "req_01J..."
}
```

### 5.2 Gửi lượt thoại — `POST /v1/voice/sessions/{id}/interact`

Mỗi câu khách nói, ASR chuyển thành văn bản và gửi vào AI Agent:

```json
{
  "transcript": "Tôi muốn đặt xe từ Vincom Đồng Khởi về Landmark 81",
  "asr_confidence": 0.94,
  "turn_number": 1
}
```

Response `200`:

```json
{
  "session_id": "sess-88123-uuid",
  "intent": "booking",
  "entities": {
    "pickup": {
      "raw": "Vincom Đồng Khởi",
      "display": "Vincom Center Đồng Khởi, Q.1, TP.HCM",
      "lat": 10.7781,
      "lng": 106.7022
    },
    "dropoff": {
      "raw": "Landmark 81",
      "display": "Landmark 81, Bình Thạnh, TP.HCM",
      "lat": 10.7951,
      "lng": 106.7218
    }
  },
  "missing_slots": [],
  "confirmation_status": "unconfirmed",
  "response_text": "Đặt xe từ Vincom Đồng Khởi đến Landmark 81, đúng không ạ?",
  "action": "WAIT_FOR_CONFIRMATION",
  "request_id": "req_01J..."
}
```

Khi thiếu thông tin, `missing_slots` sẽ chứa `["dropoff"]` và `action` là `"ASK_SLOT"`. AI hỏi khách bổ sung.

### 5.3 Đặt xe — `POST /v1/bookings`

Chỉ được gọi khi `confirmation_status == confirmed` (BR-001).

Request (Header: `Idempotency-Key: idemp-hash`):

```json
{
  "customer_phone": "0901234567",
  "pickup": {
    "display": "Vincom Center Đồng Khởi, Q.1, TP.HCM",
    "lat": 10.7781,
    "lng": 106.7022
  },
  "dropoff": {
    "display": "Landmark 81, Bình Thạnh, TP.HCM",
    "lat": 10.7951,
    "lng": 106.7218
  },
  "vehicle_type": "car_4_seater"
}
```

Response `201`:

```json
{
  "booking_id": "bk-20260807-9912",
  "status": "driver_assigning",
  "estimated_arrival_minutes": 3,
  "fare_estimate": {
    "amount": 65000,
    "currency": "VND"
  },
  "request_id": "req_01J..."
}
```

Gọi lại cùng `Idempotency-Key` trả `200` với kết quả cũ, không tạo booking trùng.

### 5.4 Chuyển tổng đài viên — `POST /v1/voice/sessions/{id}/handoff`

Kích hoạt khi ASR thất bại 2 lần (BR-003), ngoài phạm vi (BR-004), hoặc khách yêu cầu:

```json
{
  "reason_code": "ASR_FAILED_TWICE"
}
```

Response `200`:

```json
{
  "session_id": "sess-88123-uuid",
  "handoff_status": "initiated",
  "context_summary": {
    "reason": "ASR_FAILED_TWICE",
    "collected": {
      "pickup": "Vincom Center Đồng Khởi",
      "dropoff": null
    },
    "summary": "Khách muốn đặt xe từ Vincom nhưng AI nghe điểm đến không rõ 2 lần."
  },
  "request_id": "req_01J..."
}
```

Tóm tắt được push lên Agent Desktop CRM để tổng đài viên đọc trước khi tiếp nhận.

## 6. Error behavior và UI expectation

| Case | HTTP / code | Voice behavior |
|---|---|---|
| Chưa xác thực | `401 UNAUTHENTICATED` | Ngắt kết nối, alert trực ban |
| Không đủ quyền | `403 FORBIDDEN` | Log lỗi, ngắt session |
| Session không tồn tại | `404 RESOURCE_NOT_FOUND` | AI: "Em không tìm thấy thông tin ạ" |
| Chưa xác nhận mà gọi booking | `409 CONFIRMATION_REQUIRED` | AI đọc lại câu xác nhận (BR-001) |
| Booking trùng (idempotent) | `200 DUPLICATE_REQUEST` | Trả kết quả cũ, không tạo đơn mới |
| Địa chỉ mơ hồ | `422 AMBIGUOUS_LOCATION` | AI liệt kê 2 địa điểm cho khách chọn |
| Backend lỗi 5xx | `503 BACKEND_UNAVAILABLE` | AI: "Hệ thống bận, em chuyển tổng đài viên ạ" → Handoff |
| ASR không rõ lần 1 | `200 ASR_LOW_CONFIDENCE` | AI: "Xin lỗi, em chưa nghe rõ, nhắc lại ạ?" |
| ASR không rõ lần 2 | `200 ASR_FAILED_TWICE` | Kích hoạt Handoff (BR-003) |

## 7. Async, timeout và retry

- End-to-end latency target: ≤ 2.5 giây. Khi chờ API > 1s, AI phát: "Dạ, em đang xử lý ạ".
- `POST /v1/bookings` bắt buộc `Idempotency-Key` = `hash(phone + pickup + dropoff + 5min_bucket)`.
- AI không tự retry `POST` booking khi timeout. Chỉ `GET` request được retry tối đa 2 lần với backoff (200ms, 400ms).
- `request_id` được truyền xuyên suốt Gateway → Agent → Backend để tra cứu log.

## 8. Contract verification

| Check | Cách kiểm tra | Gate |
|---|---|---|
| Schema | OpenAPI validation | CI phải pass |
| Backward compatibility | So sánh OpenAPI với bản trên `main` | Breaking change phải tạo `/v2` |
| Idempotency | Gửi 2 request trùng key | Request 2 trả kết quả 1, không tạo booking mới |
| Handoff push | Push payload lên CRM Mock | Agent Desktop hiển thị tóm tắt trong ≤ 500ms |
| Business Rules | Test bỏ qua bước xác nhận | API trả `409 CONFIRMATION_REQUIRED` |

## 9. Interface giữa các nhóm kỹ thuật

### 9.1 Voice Gateway ↔ AI Agent — WebSocket stream

**Contract:** WebSocket tại `wss://voice-agent.alosm.vn/v1/voice/stream`.

Ví dụ gửi audio chunk:

```json
{
  "event": "media_chunk",
  "call_id": "call-v2-99812-uuid",
  "media": {
    "payload_base64": "KkxLS0hISEg...",
    "encoding": "audio/x-mulaw",
    "sample_rate": 8000
  }
}
```

Ví dụ nhận kết quả ASR:

```json
{
  "event": "transcript_update",
  "call_id": "call-v2-99812-uuid",
  "transcript": "Tôi muốn đi Vincom",
  "is_final": true,
  "confidence": 0.89
}
```

### 9.2 AI Agent ↔ Alo SM Backend — REST API

Ví dụ gọi Booking API:

```http
POST /v1/bookings
Host: backend-api.alosm.vn
Authorization: Bearer eyJhbGciOi...
Idempotency-Key: idemp-0901234567-vincom-landmark
Content-Type: application/json

{
  "customer_phone": "0901234567",
  "pickup": {"name": "Vincom Center Đồng Khởi", "lat": 10.7781, "lng": 106.7022},
  "dropoff": {"name": "Landmark 81", "lat": 10.7951, "lng": 106.7218},
  "vehicle_type": "car_4_seater"
}
```

### 9.3 AI Agent ↔ Voice AI Services (ASR, TTS, LLM) — Adapter pattern

Domain logic không import SDK bên thứ ba. Giao tiếp qua abstract interface:

#### Dependency rule

```text
Domain / LangGraph ──depends on──> SpeechProvider (abstract)
                                        ▲
Infrastructure ──implements─────────────┘
    VietnameseASRAdapter ──uses──> ASR API
    NeuralTTSAdapter ────uses──> TTS API
```

#### Domain contract

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


class VoiceAIError(Exception):
    """Base error for Voice AI provider."""

class ASRConfidenceLowError(VoiceAIError):
    """Confidence below threshold."""

class VoiceServiceUnavailable(VoiceAIError):
    """Transient failure; allows retry."""


@dataclass(frozen=True)
class ASRResult:
    transcript: str
    confidence: float
    is_final: bool

@dataclass(frozen=True)
class TTSResult:
    audio_bytes: bytes
    duration_seconds: float


class ASRProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_chunk: bytes) -> ASRResult:
        """Vietnamese speech → text."""

class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> TTSResult:
        """Text → Vietnamese speech audio."""
```

#### Contract invariants

| Invariant | Rule |
|---|---|
| Confidence | ASR trả `confidence` 0.0–1.0; < 0.60 là low confidence |
| TTS latency | Audio chunk đầu tiên trong ≤ 400ms |
| Ordering | Audio chunk trả về giữ nguyên thứ tự |
| Immutability | `ASRResult` và `TTSResult` là frozen dataclass |

#### Error ownership

| Failure | Adapter trả | Agent xử lý | Session state |
|---|---|---|---|
| Confidence thấp | `ASRConfidenceLowError` | `failed_count += 1` | Nhắc lại hoặc Handoff |
| ASR/TTS timeout | `VoiceServiceUnavailable` | Phát audio tĩnh dự phòng | Giữ session |
| LLM 5xx | `VoiceServiceUnavailable` | Fallback keyword parser | Giữ session |

### 9.4 Backend ↔ DevOps/Platform — runtime contract

DevOps không cần biết nội dung thoại; Backend cung cấp:

| Contract | Ví dụ | Kỳ vọng |
|---|---|---|
| Liveness | `GET /health/live → 200` | Xác nhận process sống |
| Readiness | `GET /health/ready → 200/503` | Check Redis + PostgreSQL; ASR lỗi không ảnh hưởng readiness |
| Config | `REDIS_URL`, `DATABASE_URL`, `AI_API_KEY` | Secret inject qua Vault; startup fail nếu thiếu |
| Migration | `alembic upgrade head` trước rollout | Migration backward-compatible |
| Log | JSON: `timestamp`, `level`, `service`, `request_id`, `call_id`, `error_code` | Không chứa SĐT/địa chỉ raw |

Ví dụ readiness response:

```json
{
  "status": "ready",
  "checks": {
    "redis": "ok",
    "postgresql": "ok"
  }
}
```

Ví dụ structured log:

```json
{
  "timestamp": "2026-08-07T10:15:05Z",
  "level": "info",
  "service": "voice-agent",
  "request_id": "req_01J...",
  "call_id": "call-v2-99812-uuid",
  "intent": "booking",
  "latency_ms": 820
}
```

## 10. Definition of Done và change process

Một interface chỉ được coi là chốt khi:

- Request, response, status code và error code đã có trong OpenAPI.
- Happy path, validation, unauthorized và dependency failure có contract test.
- AI Team và Backend Team cùng review ví dụ payload.
- Dữ liệu nhạy cảm không xuất hiện trong URL hoặc log.
- Thay đổi boundary được phản ánh trong Architecture Design.

Open questions nằm trong PRD; technical decision nằm trong Architecture Design; schema chi tiết chỉ nằm ở Interface Design/OpenAPI. Khi tạo task cho F3–F4, task phải kèm phần cập nhật interface tương ứng trước implementation.
