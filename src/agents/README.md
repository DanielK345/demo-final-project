# Agentic AI — Development Guide

Tài liệu này là source of truth cho track Agentic AI của hệ thống Voice AI
Ride-Hailing. Thành viên nhận feature phải đọc tài liệu này trước khi sửa code.

## 1. Mục tiêu của Agent

Agent nhận transcript và trạng thái hội thoại, sau đó quyết định bước tiếp theo.
Agent **không gọi API thật và không tạo side effect**. Mọi hành động bên ngoài đều
được mô tả bằng `AgentAction` để Backend thực thi.

```text
Voice/STT
   │ transcript, confidence
   ▼
Backend ── AgentInput + AgentState ──► LLMAgent
                                         │
                                         ▼
                                      Router
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  ▼                      ▼                      ▼
              Booking               Trip Lookup          FAQ/Handoff
              Workflow               Workflow             Workflow
                  │                      │                      │
                  └──────────────────────┼──────────────────────┘
                                         ▼
                                     AgentAction
                                         │
                                         ▼
                                      Backend
                          ASK/TTS, call API, handoff, end
```

Khi Backend thực thi một `CALL_TOOL`, kết quả được gửi lại ở lượt tiếp theo dưới
dạng `ToolResult`. Workflow đã yêu cầu tool chịu trách nhiệm diễn giải kết quả.

## 2. Walking skeleton hiện tại

Walking skeleton đã cung cấp một luồng chạy xuyên suốt:

```text
AgentInput("Tôi muốn đặt xe")
    → LLMAgent.handle()
    → AgentRouter.route()
    → RideBookingWorkflow.handle()
    → AgentAction(ASK_USER, "Bạn muốn đón ở đâu?")
```

Skeleton hiện có:

- Shared input/output/state/tool contracts bằng Pydantic.
- Agent entrypoint và workflow registry.
- Router deterministic tối thiểu cho bốn workflow.
- `BaseWorkflow` và `BaseTool` interfaces.
- Bốn workflow có hành vi mock tối thiểu.
- Tool builders chỉ validate và tạo `ToolCall`.
- RAG interfaces và prompt constants.
- Adapter giữ tương thích với API `ainvoke` của starter template.
- Unit/smoke tests chạy offline, không cần API key.

Skeleton chưa phải implementation hoàn chỉnh. Intent classifier, session
persistence, business workflow, tool-result lifecycle, RAG, guardrails và eval
là phần việc của F1–F8.

## 3. Cấu trúc source và trách nhiệm

```text
src/agents/
├── README.md                 # Tài liệu chung của track
├── agent.py                  # Entrypoint và workflow registry
├── graph.py                  # Adapter/graph composition
├── router.py                 # Intent và workflow routing
├── schemas.py                # Shared input/output/tool contracts
├── state.py                  # Conversation state contract
├── workflows/
│   ├── base.py               # Interface chung cho workflow
│   ├── booking.py            # F3 Ride Booking
│   ├── trip_lookup.py        # F4 Trip Lookup
│   ├── faq.py                # F7 FAQ
│   └── handoff.py            # F5 Human Handoff
├── tools/
│   ├── base.py               # Interface tạo tool call
│   ├── schemas.py            # Params của từng tool
│   ├── maps.py               # search_place
│   ├── booking.py            # create_booking
│   ├── trip.py               # lookup_trip
│   ├── knowledge.py          # retrieve_knowledge
│   └── handoff.py            # create_handoff
├── rag/
│   ├── retriever.py          # Retrieval interface/result
│   └── knowledge_base.py     # Knowledge document contract
└── prompts/
    ├── system.py             # System-level rules
    ├── routing.py            # Routing instructions
    └── workflows.py          # Workflow instructions

tests/test_agents/
├── test_graph.py             # Compatibility/graph tests
├── test_smoke.py             # End-to-end walking skeleton
├── test_router.py            # Routing tests
├── test_state.py             # State contract tests
└── test_tools.py             # Tool contract tests
```

Feature owner thêm test vào `tests/test_agents/`. Không đặt test production vào
`src/agents/`.

## 4. Shared contracts

Các contract nằm trong `schemas.py` và `state.py`. Đây là API nội bộ giữa Agent,
Backend và tất cả workflow. Không tự ý đổi tên field hoặc semantics.

### 4.1 `AgentInput`

Input của một lượt xử lý:

```python
AgentInput(
    session_id="session-001",
    transcript="Tôi muốn đặt xe",
    stt_confidence=0.98,
    tool_result=None,
)
```

| Field | Ý nghĩa |
|---|---|
| `session_id` | Định danh phiên; bắt buộc và không rỗng |
| `transcript` | Nội dung STT; có thể rỗng nếu lượt này chứa tool result |
| `stt_confidence` | Độ tin cậy STT trong khoảng 0–1 |
| `tool_result` | Kết quả Backend trả về sau một `CALL_TOOL` |

Ít nhất một trong `transcript` hoặc `tool_result` phải có dữ liệu.

### 4.2 `AgentState`

State là single source of truth của hội thoại:

| Field | Ý nghĩa |
|---|---|
| `session_id` | Phiên sở hữu state |
| `current_workflow` | Workflow đang chạy |
| `current_step` | Bước hiện tại bên trong workflow |
| `collected_data` | Dữ liệu nghiệp vụ đã thu thập |
| `pending_tool_call_id` | Tool call mà workflow đang chờ |
| `pending_tool_name` | Loại tool tương ứng với pending call |
| `confirmation` | Trạng thái xác nhận nghiệp vụ có cấu trúc |
| `retry_count` | Số lần retry hiện tại |
| `last_stt_confidence` | Confidence gần nhất dùng cho policy nhiều lượt |
| `conversation_history` | Lịch sử typed, giới hạn và không thay business state |
| `state_version` | Version tăng sau mỗi validated transition |

Agent không được dùng state có `session_id` khác input. State được cập nhật bằng
partial `state_updates` trong action; Backend hoặc state layer chịu trách nhiệm
lưu state mới.

Ví dụ:

```python
state.apply(
    {
        "current_workflow": WorkflowType.RIDE_BOOKING,
        "current_step": "COLLECT_PICKUP",
    }
)
```

`state.apply()` re-validate toàn bộ state. Không update trực tiếp bằng dictionary
không kiểm tra.

`session_id` và `state_version` là protected fields, workflow không được sửa qua
`state_updates`. `pending_tool_call_id` và `pending_tool_name` phải được set hoặc
clear cùng nhau. History được giới hạn để state không tăng vô hạn; raw tool
payload và PII không được tự động đưa vào history.

`StateStore` trong `state_store.py` định nghĩa lifecycle create/get/update/delete.
`InMemoryStateStore` chỉ dùng cho test/local development. PostgreSQL/Redis và
retention policy thật thuộc Backend. Store dùng `expected_version` để từ chối
stale update và trả state copy nhằm tránh mutation ngoài validation.

### 4.3 `AgentAction`

Agent chỉ được trả một trong năm action:

| Action | Backend thực hiện |
|---|---|
| `ASK_USER` | Gửi message sang TTS và chờ user |
| `RESPOND` | Phát câu trả lời qua TTS |
| `CALL_TOOL` | Gọi tool/API được mô tả trong `tool_call` |
| `HANDOFF` | Chuyển sang tổng đài viên |
| `END_SESSION` | Kết thúc phiên |

```python
AgentAction(
    action_type=ActionType.ASK_USER,
    message="Bạn muốn đón ở đâu?",
    state_updates={"current_step": "COLLECT_PICKUP"},
    reason="Pickup is missing.",
)
```

Quy tắc:

- `CALL_TOOL` bắt buộc có `tool_call`.
- Action khác không được chứa `tool_call`.
- `state_updates` là partial update, không phải toàn bộ state.
- `reason` phục vụ debug/evaluation, không đọc cho khách.
- Text nói với khách phải nằm trong `message`.

### 4.4 `ToolCall`

```python
ToolCall(
    tool_name=ToolName.SEARCH_PLACE,
    call_id="session-001:search-pickup:1",
    params={"query": "Times City"},
)
```

Agent tạo contract này rồi dừng. Backend mới là bên gọi Maps, Booking, Trip,
Knowledge hoặc Handoff service.

### 4.5 `ToolResult`

```python
ToolResult(
    tool_name=ToolName.SEARCH_PLACE,
    call_id="session-001:search-pickup:1",
    status=ToolStatus.SUCCESS,
    data={"candidates": []},
)
```

Quy tắc:

- `call_id` dùng để correlate request/result.
- Result lỗi bắt buộc có `error`.
- Result thành công không được chứa `error`.
- Workflow yêu cầu tool chịu trách nhiệm xử lý result.
- Không tự tạo dữ liệu khi tool không trả về.

Tool error giữ safe `error` message và có thể kèm `error_code`, `retryable` để
workflow áp dụng business retry policy. Success result không được chứa error
metadata. Payload thành công phải validate qua result model tương ứng trong
`tools/schemas.py` trước khi workflow sử dụng.

### 4.6 Tool lifecycle

`tools/call_id.py` tạo call ID có cấu trúc:

```text
session:workflow:tool:operation:sequence
```

`tools/lifecycle.py` chịu trách nhiệm:

- mở pending lifecycle bằng `pending_tool_updates()`;
- correlate cả `call_id` và `tool_name`;
- parse success payload thành typed model;
- normalize failure thành `ToolFailure`;
- clear cả pending ID/name bằng `clear_pending_tool_updates()`.

Workflow phải dừng sau khi phát `CALL_TOOL`. Backend thực thi tool rồi gửi
`ToolResult` ở invocation tiếp theo. Result stale, duplicate, sai ID hoặc sai
tool không được làm workflow tiến tiếp. Network retry và idempotency thuộc
Backend; workflow chỉ quyết định business retry/handoff.

## 5. Luồng xử lý chuẩn của một turn

1. Backend tạo `AgentInput` và đọc `AgentState` theo `session_id`.
2. Backend gọi `LLMAgent.handle(agent_input, state)`.
3. Agent kiểm tra input và state cùng session.
4. Nếu state có `current_workflow`, router tiếp tục workflow đó.
5. Nếu chưa có workflow, router xác định intent.
6. Agent lấy workflow từ registry.
7. Workflow đọc input/state và trả đúng một `AgentAction`.
8. Backend apply `state_updates` và lưu state.
9. Backend thực thi action.
10. Nếu là `CALL_TOOL`, Backend gửi `ToolResult` về ở turn tiếp theo.

Router chỉ chọn workflow. Router không thu thập pickup, không xác nhận booking và
không diễn giải tool result.

## 6. Quy tắc chỉnh shared files

Các file sau ảnh hưởng nhiều feature và cần Agentic AI lead review:

```text
src/agents/schemas.py
src/agents/state.py
src/agents/agent.py
src/agents/workflows/base.py
src/agents/tools/base.py
```

Nếu feature cần thay đổi shared contract:

1. Mô tả use case hiện tại không đáp ứng được.
2. Liệt kê feature và Backend contract bị ảnh hưởng.
3. Cập nhật tài liệu này.
4. Thêm hoặc sửa contract tests.
5. Yêu cầu lead review trước khi merge.

Không tạo lại enum/model có cùng ý nghĩa trong file feature riêng.

## 7. Phân chia F1–F8

Điền tên owner trước khi bắt đầu sprint.

| Feature | Owner | Branch đề xuất | Source chính |
|---|---|---|---|
| F1 Core & Routing | `TBD` | `feat/agent-core-routing` | `agent.py`, `router.py`, `graph.py` |
| F2 State & Memory | `TBD` | `feat/conversation-state` | `state.py` |
| F3 Ride Booking | `TBD` | `feat/ride-booking` | `workflows/booking.py` |
| F4 Trip Lookup | `TBD` | `feat/trip-lookup` | `workflows/trip_lookup.py` |
| F5 Human Handoff | `TBD` | `feat/human-handoff` | `workflows/handoff.py` |
| F6 Tool Integration | `TBD` | `feat/agent-tools` | `tools/`, tool contracts |
| F7 FAQ + RAG | `TBD` | `feat/faq-rag` | `workflows/faq.py`, `rag/` |
| F8 Guardrails & Eval | `TBD` | `feat/guardrails-eval` | `prompts/`, `eval/`, tests |

### F1 — Agent Core & Intent Routing

**Mục tiêu:** điều phối một turn, xác định hoặc tiếp tục workflow, route tool
result và trả structured action.

**Chỉnh sửa chính:**

- `src/agents/agent.py`
- `src/agents/router.py`
- `src/agents/graph.py`
- `tests/test_agents/test_router.py`
- Thêm test orchestration/tool-result routing phù hợp.

**Phải làm:**

- Intent classification cho booking, lookup, FAQ, handoff và unknown.
- Ưu tiên `current_workflow` thay vì classify lại mỗi turn.
- Route `ToolResult` về workflow đang chờ.
- Xử lý intent không rõ bằng clarification/fallback policy.
- Registry/injection cho workflow, không hard-code business logic trong router.
- Structured output ổn định và failure handling.

**Không làm:**

- Không xử lý chi tiết booking/lookup/FAQ.
- Không gọi tool/API thật.
- Không sở hữu session persistence.

**Definition of Done:** routing tests, active-workflow tests, tool-result routing
tests, unknown-intent tests và integration test đều pass.

### F2 — Conversation State & Memory

**Mục tiêu:** định nghĩa và quản lý state của từng session một cách nhất quán.

**Chỉnh sửa chính:**

- `src/agents/state.py`
- Phần state-related trong `src/agents/schemas.py` sau khi lead duyệt.
- Thêm `tests/test_agents/test_state.py` và state-store tests.

**Phải làm:**

- Hoàn thiện fields cần dùng chung: workflow, step, collected data, confirmation,
  retry, confidence flags, pending tool và history theo specification đã chốt.
- State transition/reducer có validation.
- Abstraction create/read/update session state.
- In-memory implementation để test nếu persistence thật thuộc Backend.
- Chống đọc/ghi nhầm session.

**Không làm:**

- Không quyết định bước nghiệp vụ.
- Không classify intent.
- Không tự gọi database ngoài abstraction đã thống nhất.

**Definition of Done:** create/read/update tests, transition tests, session
isolation tests và invalid-state tests đều pass.

### F3 — Ride Booking Workflow

**Mục tiêu:** hoàn thiện state machine đặt xe.

**Chỉnh sửa chính:**

- `src/agents/workflows/booking.py`
- Thêm `tests/test_agents/test_booking.py`.
- Consume tool contracts trong `src/agents/tools/`; không thực thi tool.

**Flow bắt buộc:**

```text
COLLECT_PICKUP
→ RESOLVE_PICKUP
→ SELECT_PICKUP_CANDIDATE (nếu cần)
→ COLLECT_DESTINATION
→ RESOLVE_DESTINATION
→ SELECT_DESTINATION_CANDIDATE (nếu cần)
→ COLLECT_PHONE (nếu cần)
→ CONFIRM
→ CREATE_BOOKING
→ COMPLETE
```

**Phải làm:**

- Thu thập và resolve pickup/destination.
- Xử lý zero/one/multiple place candidates.
- Thu thập phone theo policy.
- Đọc lại thông tin và yêu cầu xác nhận.
- Chỉ phát `create_booking` sau xác nhận rõ ràng.
- Xử lý booking tool success/error và retry limit.

**Không làm:**

- Không gọi Maps/Booking API trực tiếp.
- Không tạo booking ID, giá hoặc ETA.
- Không booking khi chưa confirm.

**Definition of Done:** happy path, multiple candidates, reject/change
confirmation, tool error và retry-limit tests đều pass.

### F4 — Trip Lookup Workflow

**Mục tiêu:** tra cứu chuyến bằng booking ID hoặc phone.

**Chỉnh sửa chính:**

- `src/agents/workflows/trip_lookup.py`
- Thêm `tests/test_agents/test_trip_lookup.py`.
- Consume `LookupTripTool`/`ToolResult` contracts.

**Phải làm:**

- Thu thập booking ID hoặc phone.
- Không phát tool call nếu thiếu cả hai.
- Phát `lookup_trip` với params hợp lệ.
- Xử lý found/not-found/error.
- Chỉ trả trạng thái/ETA do tool cung cấp.

**Không làm:**

- Không gọi Trip API trực tiếp.
- Không suy đoán ETA hoặc trạng thái chuyến.

**Definition of Done:** lookup bằng booking ID, lookup bằng phone, missing
identifier, not-found và tool-error tests đều pass.

### F5 — Human Handoff Workflow

**Mục tiêu:** xác định handoff và chuẩn bị đủ context cho tổng đài viên.

**Chỉnh sửa chính:**

- `src/agents/workflows/handoff.py`
- Phần handoff params trong `src/agents/tools/` nếu cần.
- Thêm `tests/test_agents/test_handoff.py`.

**Trigger tối thiểu:**

- User yêu cầu người thật.
- Complaint.
- Emergency.
- Retry vượt giới hạn.
- Critical tool error.
- Low confidence theo policy.

**Phải làm:** tạo reason, summary/context an toàn và phát `HANDOFF` hoặc
`create_handoff` theo contract thống nhất với Backend.

**Không làm:** không tự thực hiện chuyển cuộc gọi và không đưa dữ liệu session
khác vào context.

### F6 — Tool Calling & Integration

**Mục tiêu:** chuẩn hóa tool call/result để Backend thực thi chính xác.

**Chỉnh sửa chính:**

- `src/agents/tools/base.py`
- `src/agents/tools/schemas.py`
- `src/agents/tools/maps.py`
- `src/agents/tools/booking.py`
- `src/agents/tools/trip.py`
- `src/agents/tools/knowledge.py`
- `src/agents/tools/handoff.py`
- Tool-related contract trong `schemas.py` sau khi lead duyệt.
- `tests/test_agents/test_tools.py` và các test mới.

**Phải làm:**

- Params schema cho từng tool.
- Unique/correlatable `call_id` policy.
- Success/error result schemas.
- Pending-tool correlation và error normalization.
- Tài liệu contract để Backend implement executor.

**Không làm:**

- Không gọi HTTP/API thật bên trong Agent.
- Không quyết định business step sau tool result; workflow quyết định.

### F7 — FAQ + Agentic RAG

**Mục tiêu:** trả lời FAQ chỉ dựa trên nguồn truy xuất đủ tin cậy.

**Chỉnh sửa chính:**

- `src/agents/workflows/faq.py`
- `src/agents/rag/retriever.py`
- `src/agents/rag/knowledge_base.py`
- `src/agents/tools/knowledge.py`
- Thêm `tests/test_agents/test_faq.py` và RAG tests.

**Phải làm:**

- Knowledge ingestion/chunk representation theo scope dự án.
- Retrieval top-k và score threshold.
- Source metadata/citation.
- Grounded response từ retrieved context.
- Fallback/handoff khi không có nguồn đủ tin cậy.
- Xử lý knowledge tool result mà không lặp `CALL_TOOL` vô hạn.

**Không làm:** không trả lời ngoài retrieved context và không tạo nguồn giả.

### F8 — Prompt, Guardrails & Evaluation

**Mục tiêu:** kiểm soát hành vi xuyên suốt và đo chất lượng agent.

**Chỉnh sửa chính:**

- `src/agents/prompts/system.py`
- `src/agents/prompts/routing.py`
- `src/agents/prompts/workflows.py`
- `eval/`
- Guardrail/evaluation tests trong `tests/test_agents/`.

**Guardrails tối thiểu:**

- Không booking khi chưa confirm.
- Không tạo booking ID, giá hoặc ETA.
- Không dùng dữ liệu session khác.
- FAQ chỉ dựa trên retrieved context.
- Không vượt retry limit.
- Handoff theo complaint/emergency/critical error/low-confidence policy.
- Output luôn validate qua structured contract.

**Evaluation tối thiểu:** intent accuracy, workflow completion, action/tool
accuracy, hallucination/guardrail violation, latency và output-schema validity.

F8 là cross-cutting. Mỗi feature owner vẫn phải viết guardrail test liên quan
đến feature của mình; F8 owner không chịu trách nhiệm viết thay mọi test.

## 8. Quy tắc branch và merge

Track integration branch:

```text
feat/<feature-name>
    → feature/agentic-ai
    → integration test
    → develop
    → main
```

Khi bắt đầu feature:

```bash
git switch feature/agentic-ai
git pull origin feature/agentic-ai
git switch -c feat/<feature-name>
```

Không branch từ `main` nếu walking skeleton mới nhất chỉ có ở
`feature/agentic-ai`.

## 9. Test và kiểm tra trước PR

Chạy từ repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m compileall -q src tests
git diff --check
```

Mọi test phải offline và deterministic. Unit test không gọi OpenAI, Maps,
Booking API, Trip API hoặc vector service thật.

## 10. Pull request checklist

- [ ] PR chỉ chứa phạm vi feature được giao.
- [ ] Đã mô tả state transitions.
- [ ] Không gọi API thật từ Agent.
- [ ] Không tạo dữ liệu booking/trip/FAQ không có nguồn.
- [ ] Không sửa shared contract nếu chưa được lead duyệt.
- [ ] Nếu sửa contract, đã cập nhật README và contract tests.
- [ ] Có happy-path test.
- [ ] Có error/edge-case tests quan trọng.
- [ ] Toàn bộ test cũ và mới đều pass.
- [ ] Ruff và compile check pass.
- [ ] PR target là `feature/agentic-ai`.

## 11. Trạng thái baseline khi giao feature

Baseline hiện được xác nhận bằng:

```text
16 tests passed
Ruff: All checks passed
Python compile: passed
```

Các hành vi skeleton đã chạy:

```text
đặt xe      → ASK_USER / RIDE_BOOKING
tra cứu     → ASK_USER / TRIP_LOOKUP
người thật  → HANDOFF / HUMAN_HANDOFF
FAQ         → CALL_TOOL / RETRIEVE_KNOWLEDGE
```

Khi feature implementation thay đổi hành vi này, owner phải cập nhật test tương
ứng nhưng vẫn giữ đúng shared contracts và nguyên tắc Agent không tạo side effect.
