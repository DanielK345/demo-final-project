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

Một turn phải có transcript hoặc `tool_result`:

```json
{
  "session_id": "session-001",
  "transcript": "Tôi muốn đặt xe",
  "stt_confidence": 0.96,
  "tool_result": null
}
```

Tool-result turn:

```json
{
  "session_id": "session-001",
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

Backend không đọc `reason` cho khách. `reason` chỉ dành cho diagnostic/evaluation
và vẫn phải qua access-controlled logging.

## 6. Tool dispatch

Mapping tối thiểu:

| `tool_name` | Backend integration |
|---|---|
| `search_place` | Mapbox/Google Places adapter |
| `create_booking` | Booking service |
| `lookup_trip` | Trip service/PostgreSQL-backed service |
| `retrieve_knowledge` | Knowledge/RAG service |
| `create_handoff` | Operator/case service nếu action này được sử dụng |

Backend phải validate params bằng contract tương ứng trước khi gọi provider.
Không đổi `call_id` khi tạo `ToolResult`.

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

## 8. Idempotency and duplicate delivery

`call_id` dùng cho correlation, không thay thế idempotency key của side effect.

Đặc biệt với `create_booking`:

- Backend tạo/reuse idempotency key ổn định từ session và logical operation;
- lưu kết quả trước khi acknowledge;
- duplicate dispatch phải trả cùng business result, không tạo chuyến mới;
- duplicate/stale `ToolResult` không được tự ý gắn vào pending call khác;
- timeout không đồng nghĩa booking thất bại; Backend phải reconcile trước retry.

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
- `stt_confidence` nằm trong khoảng 0–1.
- Barge-in, partial transcript, interruption và audio cancellation thuộc Voice.
- Voice có thể phát `message`; không phát `reason`, source URL hay tool metadata.
- Khi `HANDOFF`, Voice/Backend thực hiện transfer; Core Agent chỉ chuẩn bị action.

## 12. Acceptance checklist

- [ ] Backend load state theo authenticated session.
- [ ] State update dùng validation và optimistic concurrency.
- [ ] Persist thành công trước khi execute action.
- [ ] Tool dispatch giữ nguyên `call_id`.
- [ ] Tool success/error payload đúng schema.
- [ ] `create_booking` có idempotency và reconciliation.
- [ ] PII không xuất hiện trong log mặc định.
- [ ] Handoff truyền safe context.
- [ ] Integration tests cover timeout, duplicate và version conflict.
- [ ] Voice chỉ đọc customer-facing `message`.
