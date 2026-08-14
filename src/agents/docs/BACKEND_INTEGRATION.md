# Backend Integration Contract — Core Agent

Tài liệu này mô tả cách Backend tích hợp Core Agent GSM-08. Đây là contract bàn
giao; `src/agents/` không triển khai HTTP endpoint, database hay external API.

## 1. Boundary

```text
Voice/STT
  ↓ transcript + confidence
Backend
  ├── authenticate/authorize session
  ├── load/persist AgentState
  ├── call Core Agent
  └── execute AgentAction
        ↓
Maps / Booking / Trip / Knowledge / Handoff / TTS
```

Core Agent:

- nhận `AgentInput` và `AgentState`;
- trả đúng một `AgentAction`;
- không đọc/ghi database;
- không gọi service thật;
- không sở hữu credentials;
- không tự retry network hoặc tạo side effect.

Language understanding có thể dùng OpenAI khi `AGENT_LLM_ENABLED=true`.
Credential/model được inject qua environment; Backend không gửi API key trong
turn payload. OpenAI chỉ extract structured intent/slots, không thực thi tools.

## 2. Entrypoint

Backend có thể gọi domain API trực tiếp:

```python
action = await LLMAgent().handle(agent_input, state)
```

Hoặc adapter LangGraph:

```python
result = await AgentGraphAdapter().ainvoke(
    {
        "session_id": session_id,
        "turn_id": turn_id,
        "query": transcript,
        "stt_confidence": confidence,
        "state": state.model_dump(mode="json"),
        "tool_result": tool_result,
    }
)
action = AgentAction.model_validate(result["action"])
```

Khuyến nghị Backend dùng một instance lâu dài thay vì tạo instance mới mỗi turn.
Core Agent không giữ mutable session state nên có thể scale horizontally.

## 3. Turn request

Một turn phải có transcript hoặc `tool_result`. Nếu callback được giao cùng
transcript, Core Agent ưu tiên correlate/xử lý `tool_result`; Backend phải gửi
user transcript thành turn riêng nếu cần xử lý tiếp:

```json
{
  "session_id": "session-001",
  "turn_id": "turn-001",
  "transcript": "Tôi muốn đặt xe",
  "stt_confidence": 0.96,
  "tool_result": null
}
```

Tool-result turn:

```json
{
  "session_id": "session-001",
  "turn_id": "turn-002",
  "transcript": "",
  "tool_result": {
    "tool_name": "search_place",
    "call_id": "session-001:ride_booking:search_place:pickup:2",
    "status": "SUCCESS",
    "data": {
      "candidates": [
        {
          "place_id": "provider-place-id",
          "display_name": "Hồ Gươm",
          "address": "Hoàn Kiếm, Hà Nội"
        }
      ]
    }
  }
}
```

`session_id` của input phải khớp state đã load. Backend không được nhận state từ
client như dữ liệu tin cậy; state phải được load bằng identity/session đã xác thực.

Identifier không được rỗng hoặc chỉ chứa khoảng trắng. `state_updates` có field
không thuộc `AgentState` bị reject thay vì âm thầm bỏ qua.

`turn_id` là bắt buộc, do Backend/Voice tạo và phải ổn định khi retry cùng một
input turn. Mỗi user transcript, tool-result turn hoặc event-driven invocation
có một `turn_id` riêng. `turn_id` không thay `call_id` hoặc idempotency key của
side effect.

### 3.1 Conversation history and delivery contract

History phân biệt nội dung Agent dự kiến nói và nội dung Voice thực sự phát:

```text
USER_TRANSCRIPT     → FINAL
ASSISTANT_SPEECH    → PENDING
                    → DELIVERED | INTERRUPTED | FAILED
```

Message ID deterministic:

```text
{turn_id}:user
{turn_id}:assistant
{turn_id}:tool-summary:{sequence}
```

Sau khi thực thi TTS, Voice gửi một `AssistantDeliveryEvent` cho Backend:

```json
{
  "session_id": "session-001",
  "turn_id": "turn-001",
  "message_id": "turn-001:assistant",
  "status": "INTERRUPTED",
  "spoken_content": "Bạn muốn đón"
}
```

Backend dùng pure reducer `acknowledge_assistant_delivery()` và persist state
bằng optimistic concurrency. Delivery event không được route vào business
workflow và không tự tạo một Agent response mới.

Core Agent tự động merge history vào `AgentAction.state_updates`:

- non-empty transcript thành `USER_TRANSCRIPT / FINAL`;
- tool result thành safe `TOOL_SUMMARY / FINAL` chỉ có tool name/status;
- customer-facing message của `ASK_USER`, `RESPOND`, `HANDOFF` hoặc
  `END_SESSION` thành `ASSISTANT_SPEECH / PENDING`;
- `CALL_TOOL` không tạo assistant speech.

Business update và history update được Backend apply/persist trong cùng một
transaction. Workflow không được tự ghi history. Raw tool payload, tool error,
diagnostic `reason` và phone trong conversational text không được lưu vào
history. Phone vẫn có thể tồn tại trong validated business slot cần cho booking.

## 4. Transaction order

Backend xử lý mỗi turn theo thứ tự:

```text
1. Authenticate request/session.
2. Load AgentState.
3. Call Core Agent.
4. Validate AgentAction.
5. Apply state_updates using AgentState.apply().
6. Persist new state using expected state_version.
7. Only after persist succeeds, execute AgentAction.
```

Pseudocode:

```python
state = await store.get(session_id) or AgentState(session_id=session_id)
expected_version = state.state_version

action = await agent.handle(agent_input, state)
new_state = state.apply(action.state_updates)

await store.save(
    new_state,
    expected_version=expected_version,
)
await executor.execute(action, session_id=session_id)
```

Mỗi Agent turn chỉ gọi `state.apply(action.state_updates)` một lần. Delivery
acknowledgement sau TTS là transaction riêng và dùng `expected_version` mới nhất.
Backend phải deduplicate/replay stable `turn_id` trước khi invoke Agent; Core
history reducer cũng reject turn đã xuất hiện trong persisted history.

Persist trước execution giúp lượt `ToolResult` sau luôn thấy pending call. Nếu
save gặp version conflict, không thực thi action; Backend reload và xử lý lại
theo concurrency policy.

## 5. Action execution

| Action | Backend xử lý |
|---|---|
| `ASK_USER` | Gửi `message` sang Voice/TTS và chờ user turn |
| `RESPOND` | Gửi `message` sang Voice/TTS; session vẫn mở nếu policy không đóng |
| `CALL_TOOL` | Dispatch đúng executor, giữ nguyên `call_id`, gửi result về Agent |
| `HANDOFF` | Chuyển case/cuộc gọi cùng safe context trong state |
| `END_SESSION` | Đóng lifecycle và áp retention policy |

Mọi action customer-facing (`ASK_USER`, `RESPOND`, `HANDOFF`, `END_SESSION`)
phải có `message` không rỗng. `CALL_TOOL` không tạo assistant speech.

Backend không đọc `reason` cho khách. `reason` chỉ dành cho diagnostic/evaluation
và vẫn phải qua access-controlled logging.

Mỗi `ToolCall` có `timeout_seconds` do central `AgentPolicy` gắn vào. Executor
phải áp deadline này; timeout của read-only tool có thể trả lỗi retryable, còn
timeout của `create_booking`/`cancel_booking` phải đi qua reconciliation vì kết
quả side effect có thể chưa xác định. `AgentState.tool_call_count` là budget đã
dùng trong session và được Core Agent tăng atomically cùng pending call.

## 6. Tool dispatch

Mapping tối thiểu:

| `tool_name` | Backend integration |
|---|---|
| `search_place` | Mapbox/Google Places adapter |
| `get_vehicle_options` | Vehicle catalog, capacity, availability and pricing |
| `estimate_fare` | Pricing/route estimate service |
| `create_booking` | Booking service |
| `cancel_booking` | Booking cancellation service |
| `lookup_trip` | Trip service/PostgreSQL-backed service |
| `retrieve_knowledge` | Knowledge/RAG service |
| `create_handoff` | Operator/case service nếu action này được sử dụng |

Backend phải validate params bằng contract tương ứng trước khi gọi provider.
Không đổi `call_id` khi tạo `ToolResult`.

Core guardrail cũng validate toàn bộ params lần cuối và chỉ cho phép tool thuộc
active workflow. Field thừa, field thiếu hoặc tool sai workflow bị chặn trước
dispatch.

`lookup_trip` có thể trả một trip hoặc `trips[]` khi phone khớp nhiều chuyến.
Mỗi match phải có internal `booking_id`; `pickup_label`/`destination_label` nếu
có phải là customer-safe short label, không phải full private address. Core
Agent không đọc booking ID hoặc phone khi yêu cầu user chọn chuyến.

## 7. Tool result and errors

Success:

```json
{
  "tool_name": "lookup_trip",
  "call_id": "same-call-id",
  "status": "SUCCESS",
  "data": {
    "found": true,
    "booking_id": "GSM-12345",
    "status": "DRIVER_EN_ROUTE",
    "eta_minutes": 4
  }
}
```

Normalized failure:

```json
{
  "tool_name": "lookup_trip",
  "call_id": "same-call-id",
  "status": "ERROR",
  "data": {},
  "error": "Trip service timed out",
  "error_code": "TIMEOUT",
  "retryable": true
}
```

`error` phải là safe message, không chứa credentials, stack trace hoặc raw
provider payload. Backend map provider-specific errors sang stable error codes.
`error` tối đa 500 ký tự; `error_code` tối đa 64 ký tự và dùng uppercase
`A-Z`, `0-9`, `_` (ví dụ `TIMEOUT`, `UNAVAILABLE`, `UNKNOWN_OUTCOME`).

## 8. Idempotency and duplicate delivery

`call_id` dùng cho correlation, không thay thế idempotency key của side effect.

Đặc biệt với `create_booking` và `cancel_booking`:

- Agent gửi stable logical `idempotency_key`; Backend phải lưu và enforce key đó;
- lưu kết quả trước khi acknowledge;
- duplicate dispatch phải trả cùng business result, không tạo/hủy lần hai;
- duplicate/stale `ToolResult` không được tự ý gắn vào pending call khác;
- timeout không đồng nghĩa operation thất bại; Backend phải reconcile trước retry.

`estimate_fare` phải trả `estimate_id`, `fare_amount`, `currency` và có thể trả
ETA/distance. `create_booking` phải validate `pickup_place_id`,
`destination_place_id`, `vehicle_type` và `fare_estimate_id` vẫn hợp lệ tại thời
điểm tạo chuyến.

`get_vehicle_options` nhận nhu cầu semantic (`passenger_count`, luggage và
preference nếu có) cùng tuyến đã resolve. Backend là nguồn duy nhất của option,
capacity, availability, `estimate_id` và giá. LLM chỉ được trả lại một
`option_id` thuộc result này; Backend vẫn phải validate option khi booking.

## 9. State persistence

Backend persistence implementation phải bảo đảm:

- state được partition theo authenticated `session_id`;
- optimistic concurrency bằng `state_version`;
- atomic compare-and-set;
- TTL/retention theo product policy;
- encryption at rest/in transit;
- không cho client ghi trực tiếp `current_workflow`, confirmation hoặc pending tool;
- session resume load đúng state version mới nhất.

`InMemoryStateStore` trong Agent chỉ dành cho tests/local development, không dùng
production và không an toàn cho multi-process deployment.

## 10. PII and observability

Backend trace tối thiểu nên có:

```text
trace_id
hashed_session_id
turn_id
state_version_before/after
workflow
step_before/after
action_type
tool_name
call_id
latency_ms
error_code
handoff_reason
```

Không log mặc định raw audio, full phone, full address, credentials, raw provider
payload hoặc transcript chứa PII. Recording consent, retention và deletion thuộc
Backend/Voice/platform policy.

## 11. Voice integration notes

- Chỉ final transcript turn được đưa vào Core Agent.
- Mọi invocation phải có stable `turn_id`.
- `stt_confidence` nằm trong khoảng 0–1.
- Barge-in, partial transcript, interruption và audio cancellation thuộc Voice.
- Voice phải acknowledge assistant speech là delivered/interrupted/failed.
- Voice có thể phát `message`; không phát `reason`, source URL hay tool metadata.
- Khi `HANDOFF`, Voice/Backend thực hiện transfer; Core Agent chỉ chuẩn bị action.

## 12. Acceptance checklist

- [ ] Backend load state theo authenticated session.
- [ ] Backend/Voice tạo stable unique `turn_id` cho mỗi input turn.
- [ ] State update dùng validation và optimistic concurrency.
- [ ] Persist thành công trước khi execute action.
- [ ] Tool dispatch giữ nguyên `call_id`.
- [ ] Executor áp đúng `timeout_seconds` và không vượt session tool budget.
- [ ] Tool được dispatch đúng active workflow, params không có field thừa.
- [ ] Tool success/error payload đúng schema.
- [ ] `create_booking`/`cancel_booking` có idempotency và reconciliation.
- [ ] PII không xuất hiện trong log mặc định.
- [ ] Handoff truyền safe context.
- [ ] Integration tests cover timeout, duplicate và version conflict.
- [ ] Voice chỉ đọc customer-facing `message`.
- [ ] Delivery acknowledgement correlate đúng session/turn/message.
