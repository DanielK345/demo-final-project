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

## 2. Core Agent hiện tại

Core Agent giữ một luồng xử lý xuyên suốt:

```text
AgentInput("Tôi muốn đặt xe")
    → LLMAgent.handle()
    → AgentRouter.route()
    → RideBookingWorkflow.handle()
    → AgentAction(ASK_USER, "Bạn muốn đón ở đâu?")
```

Implementation hiện có:

- Shared input/output/state/tool contracts bằng Pydantic.
- Agent entrypoint và workflow registry.
- Router deterministic kết hợp structured understanding cho bốn workflow.
- `BaseWorkflow` và `BaseTool` interfaces.
- Bốn workflow nhiều lượt với typed business state và conversation repair.
- Tool builders chỉ validate và tạo `ToolCall`.
- Grounded FAQ/RAG, production guardrails và versioned readiness evaluation.
- Adapter giữ tương thích với API `ainvoke` của starter template.
- Unit/smoke tests chạy offline, không cần API key.

F1–F8 của Core Agent đã được triển khai. External executors, production
persistence, knowledge ingestion và Voice Runtime vẫn thuộc Backend/Voice; xem
trạng thái và ranh giới hoàn thành tại [`docs/CORE_AGENT_STATUS.md`](docs/CORE_AGENT_STATUS.md).

## 3. Cấu trúc source và trách nhiệm

```text
src/agents/
├── README.md                 # Tài liệu chung của track
├── agent.py                  # Entrypoint và workflow registry
├── graph.py                  # Adapter/graph composition
├── router.py                 # Intent và workflow routing
├── schemas.py                # Shared input/output/tool contracts
├── state.py                  # Conversation state contract
├── state_store.py            # Store abstraction và optimistic concurrency
├── history.py                # Typed history/delivery reducers
├── context.py                # Sanitized bounded context projection
├── repair.py                 # Dialogue repair và workflow interruption
├── guardrails.py             # Cross-cutting output/state/tool invariants
├── policy.py                 # Central retry/deadline/budget policy
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
│   ├── booking.py            # estimate_fare/create_booking/cancel_booking
│   ├── trip.py               # lookup_trip
│   ├── knowledge.py          # retrieve_knowledge
│   └── handoff.py            # create_handoff
├── rag/
│   ├── retriever.py          # Retrieval interface/result
│   ├── knowledge_base.py     # Knowledge document contract
│   └── answer_generator.py   # Grounded answer generation port/fallback
├── understanding/            # Rule/OpenAI understanding và contextual rewrite
├── eval/                     # Versioned datasets, evaluator và readiness gates
└── prompts/
    ├── system.py             # System-level rules
    ├── routing.py            # Routing instructions
    └── workflows.py          # Workflow instructions

tests/test_agents/             # Unit, contract và deterministic multi-turn tests
tests/integration/             # Real-provider tests, explicit opt-in
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
    turn_id="turn-001",
    transcript="Tôi muốn đặt xe",
    stt_confidence=0.98,
    tool_result=None,
)
```

| Field | Ý nghĩa |
|---|---|
| `session_id` | Định danh phiên; bắt buộc và không rỗng |
| `turn_id` | ID ổn định do Backend/Voice tạo cho một input turn; bắt buộc và giữ nguyên khi retry |
| `transcript` | Nội dung STT; có thể rỗng nếu lượt này chứa tool result |
| `stt_confidence` | Độ tin cậy STT trong khoảng 0–1 |
| `tool_result` | Kết quả Backend trả về sau một `CALL_TOOL` |

Ít nhất một trong `transcript` hoặc `tool_result` phải có dữ liệu.
Nếu cả hai cùng có mặt, correlated `tool_result` được xử lý trước; Backend phải
gửi transcript thành turn riêng nếu vẫn cần xử lý nội dung đó.

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
| `conversation_summary` | Bản tóm tắt typed của history cũ; không thay business state |
| `interrupted_workflow` | Single resumable workflow frame; không chứa business payload |
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

Conversation history dùng typed contracts trong `state.py`:

- `ConversationMessage` có deterministic `message_id`, `turn_id`, role, type,
  content và delivery status;
- final user transcript dùng trạng thái `FINAL`;
- assistant speech bắt đầu ở `PENDING`, sau đó Backend/Voice xác nhận
  `DELIVERED`, `INTERRUPTED` hoặc `FAILED` bằng `AssistantDeliveryEvent`;
- `spoken_content` biểu diễn phần thực sự đã phát khi cần đồng bộ barge-in;
- `ConversationSummary` nén history cũ nhưng không được override validated slots;
- `history.py` cung cấp pure reducers, không tự persist và không gọi Voice/TTS.

`turn_id` là idempotency identity của input turn, không thay thế `call_id` của
tool hoặc idempotency key của side effect. Core Agent tự động merge sanitized
user transcript, safe tool summary và pending assistant speech vào cùng
`state_updates` với business transition. Backend persist toàn bộ update một lần
trước khi execute action. Workflow không được tự sửa `conversation_history` hoặc
`conversation_summary`.

`CALL_TOOL` không tạo assistant speech vì Backend chỉ dispatch tool. Một
tool-result-only turn tạo `TOOL_SUMMARY` chỉ gồm tool name/status để correlate và
deduplicate turn; raw payload và error không được lưu. Recent history được prune
theo complete turn trong giới hạn cấu hình. P3 đưa history vào language
understanding qua projection typed, sanitized và bounded: chỉ dùng user
transcript cùng assistant speech thực sự đã phát, loại pending/failed speech và
arbitrary collected data. Deterministic gate chỉ gọi contextual rewriter khi có
reference cùng evidence phù hợp; workflow nhận effective text, còn history luôn
ghi raw transcript.

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
- `ASK_USER`, `RESPOND`, `HANDOFF` và `END_SESSION` bắt buộc có message không rỗng.

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

`graph.py` hiện compose một turn bằng LangGraph:

```text
normalize_input → invoke_core_agent → format_output
```

Graph không có checkpointer và không sở hữu business state. Nó chỉ là adapter
orchestration giữ API `ainvoke` của starter template; Backend vẫn truyền
`AgentState`, apply/persist `state_updates` và thực thi `AgentAction`. Graph không
tự gọi tool và kết thúc sau đúng một action.

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

Owner table dưới đây là thông tin quản lý sprint, không biểu diễn trạng thái
implementation. Trạng thái kỹ thuật nằm trong `docs/CORE_AGENT_STATUS.md`.

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
→ COLLECT_VEHICLE
→ ESTIMATE_FARE
→ COLLECT_PHONE (nếu cần)
→ CONFIRM
→ CREATE_BOOKING
→ COMPLETE
```

**Phải làm:**

- Thu thập và resolve pickup/destination.
- Xử lý zero/one/multiple place candidates.
- Thu thập loại xe và phone theo policy.
- Lấy giá dự kiến từ Backend rồi đọc lại tuyến, loại xe và giá để xác nhận.
- Chỉ phát `create_booking` sau xác nhận rõ ràng.
- Reject pickup/destination trùng nhau sau resolve.
- Invalidate fare khi pickup, destination hoặc vehicle thay đổi.
- Xử lý retry, stale/duplicate result, unknown outcome và reconciliation.
- Hủy chuyến đã đặt chỉ sau một confirmation riêng.

**Không làm:**

- Không gọi Maps/Booking API trực tiếp.
- Không tạo booking ID, giá hoặc ETA.
- Không booking khi chưa confirm.

**Definition of Done:** happy path, multiple candidates, reject/change
confirmation, tool error và retry-limit tests đều pass.

**Implementation hiện tại (P5 complete):** Booking state được validate bằng
`BookingData` và lưu dưới `collected_data["booking"]`. Workflow resolve
pickup/destination qua `search_place`, thu thập `vehicle_type`, gọi
`estimate_fare`, thu thập phone rồi mới yêu cầu confirmation. `create_booking`
nhận fare estimate ID và stable idempotency key; guardrail đối chiếu toàn bộ
params với state đã xác nhận. Search/fare lỗi retryable được retry có giới hạn;
create/cancel timeout hoặc stale result giữ pending side effect và đi
reconciliation. Result success replay được xử lý idempotent. Booking hoàn tất có
thể đi qua confirmation riêng để phát `cancel_booking`.

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

**Implementation hiện tại (P6):** Trip lookup data được validate bằng
`TripLookupData`. Các câu nối tiếp như “xe của tôi tới đâu rồi?” hoặc “còn bao
lâu?” tự dùng booking vừa lookup/đặt trong state, không bắt user đọc lại ID.
`lookup_trip` hỗ trợ một hoặc nhiều `TripMatch`; nếu nhiều chuyến, Agent chỉ đọc
customer-safe pickup/destination label và cho chọn theo thứ tự, không đọc booking
ID hay full phone. Sau khi chọn, Agent lookup lại booking đã chọn để lấy status
và ETA mới nhất. Mọi status/ETA vẫn chỉ đến từ typed Backend result.
Stale callback không phá pending lookup hiện tại, completed result replay được
xử lý idempotent, và status code từ Backend được trình bày bằng tiếng Việt.

FAQ hỗ trợ câu hỏi nối tiếp bằng grounded topic trước đó. Knowledge documents có
thể mang citation/version/effective/expiry; source cũ, chưa hiệu lực, điểm thấp
hoặc chứa prompt injection bị loại trước answer generation. Citation được lưu làm
metadata, không trộn vào câu đọc cho người dùng.

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

**Implementation hiện tại:** FAQ state được validate bằng `FAQData` và lưu dưới
`collected_data["faq"]`. Workflow phát `retrieve_knowledge`, validate lifecycle
và typed documents, sau đó lọc theo configurable score threshold/top-k.
`GroundedAnswerGenerator` là provider-independent port; mặc định dùng
`ExtractiveAnswerGenerator` deterministic nên chỉ có thể trả retrieved content.
Không có source đủ điểm thì trả fallback trung thực; retrieval error critical,
mismatched hoặc invalid result được handoff. Vector store, ingestion và dữ liệu
chính sách thật thuộc Backend/Knowledge Service.

### F8 — Prompt, Guardrails & Evaluation

**Mục tiêu:** kiểm soát hành vi xuyên suốt và đo chất lượng agent.

**Chỉnh sửa chính:**

- `src/agents/prompts/system.py`
- `src/agents/prompts/routing.py`
- `src/agents/prompts/workflows.py`
- `eval/`
- Guardrail/evaluation tests trong `tests/test_agents/`.

Readiness evaluation deterministic:

```bash
.venv/bin/python -m examples.evaluate_core_agent
```

Lệnh trên dùng versioned dataset và mock tool results. Thêm `--real-model` để
đánh giá adapter LLM đã cấu hình mà không gọi Booking Backend thật.

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

**Implementation hiện tại:** `AgentGuardrails` hậu kiểm mọi workflow action,
validate state transition, pending tool identity, message length và cấm
`create_booking` khi confirmation chưa rõ. Diagnostic reason và handoff summary
được redact phone; confidence gần nhất được đưa vào validated state update.
`AgentPolicy` gom threshold/retry dùng chung. `BehaviorEvaluator` chạy scenario
offline và báo action/workflow/tool accuracy, schema validity, pass rate cùng
Agent latency. Evaluation không gọi LLM hay external service thật.

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

Không branch từ `main` nếu Core Agent mới nhất chỉ có ở
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

## 11. Trạng thái Core Agent MVP

Core Agent MVP đã hoàn thành:

```text
F1 Core & Routing                 implemented
F2 State & Memory                 implemented
F3 Ride Booking                   implemented
F4 Trip Lookup                    implemented
F5 Human Handoff                  implemented
F6 Tool Calling Lifecycle         implemented
F7 FAQ + grounded RAG             implemented
F8 Guardrails & Offline Eval      implemented
LangGraph one-turn orchestration  implemented
Multi-turn integration scenarios implemented
OpenAI structured understanding      implemented (opt-in)
```

Validation command:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m compileall -q src tests examples
git diff --check
```

Integration contract cho Backend nằm tại
[`BACKEND_INTEGRATION.md`](docs/BACKEND_INTEGRATION.md). Demo text-mode chạy bằng:

```bash
.venv/bin/python -m examples.core_agent_demo
```

Ngoài scope Core Agent MVP: Maps/Booking/Trip executors, production knowledge
ingestion/vector store, PostgreSQL/Redis persistence,
FastAPI endpoints và Voice Runtime. Các integration này phải giữ nguyên shared
contracts và boundary Agent quyết định/Backend thực thi.

### OpenAI structured language understanding

Core Agent có provider-independent `LanguageUnderstandingPort`. Mặc định
`AGENT_LLM_ENABLED=false` để offline tests và local fallback dùng
`RuleBasedUnderstanding`. Bật OpenAI Responses API structured output bằng:

```env
OPENAI_API_KEY=...
AGENT_LLM_ENABLED=true
AGENT_LLM_PROVIDER=openai
AGENT_LLM_MODEL=gpt-5.6-luna
AGENT_LLM_TIMEOUT_SECONDS=5
AGENT_LLM_REASONING_EFFORT=none
```

OpenAI chỉ extract intent/slots/correction/confirmation. Router, workflow,
confirmation safety và tool execution vẫn deterministic. Provider timeout/error
fallback về rules. Tool-result-only turn không gọi LLM.

Unit tests không gọi provider. Chạy integration test thật có chủ đích:

```bash
RUN_OPENAI_INTEGRATION=1 \
OPENAI_API_KEY="..." \
AGENT_LLM_MODEL="gpt-5.6-luna" \
.venv/bin/python -m pytest -q -m provider tests/integration
```

### Contextual user-message rewrite

P3 cung cấp provider-independent rewrite port, OpenAI structured adapter,
grounding/safety validator và resilient fallback. Rewrite rollout dùng config
riêng với understanding:

```env
AGENT_REWRITE_ENABLED=false
AGENT_REWRITE_PROVIDER=openai
AGENT_REWRITE_MODEL=gpt-5.6-luna
AGENT_REWRITE_TIMEOUT_SECONDS=5
AGENT_REWRITE_REASONING_EFFORT=none
```

Mặc định rewriter là passthrough và không gọi network. Khi bật provider, prompt
không chứa raw session ID; phone/booking identity trong current input chặn
provider call. Output phải giữ nguyên original text, cite source turn và chỉ
resolve value có trong sanitized context. Timeout, invalid hoặc unsafe output
đều fallback về raw text. `LLMAgent` đã nối context, gate, rewrite và
understanding; tool-result/emergency fast path không gọi provider. Confirmation,
phone và booking identity vẫn cần evidence từ raw transcript. Tại bước booking
confirmation hoặc cancel confirmation, workflow luôn đọc raw text để rewrite
không thể tạo side effect.

### Conversation repair

P4.1 đã định nghĩa typed `DialogueActResult` và deterministic
`DialogueActDetector` cho `REPEAT`, `CORRECT`, `CANCEL`, `START_OVER`, `HELP`,
`CHANGE_INTENT`, `PAUSE`, `RESUME`, `GOODBYE` và default `CONTINUE`. Detector
chỉ nhận diện explicit command/evidence và không sửa state.

P4.2 đã nối `REPEAT`, `CANCEL`, `START_OVER` và `GOODBYE` vào `LLMAgent` sau
global safety/tool-result priority và trước rewrite/understanding. Repeat chỉ
dùng assistant speech thực sự đã phát; cancel/start-over reset đúng workflow
namespace; goodbye chỉ end session khi an toàn. Pending side effect
`create_booking`/`cancel_booking`/`create_handoff` được giữ nguyên và chuyển sang
`RECONCILIATION_REQUIRED`, không giả định đã hủy. Các dialogue act còn lại được
tách sang các phase sau.

P4.3 đã hoàn thiện correction cho Ride Booking. Agent hỗ trợ sửa pickup,
destination và phone với giá trị ngay trong câu hoặc hỏi riêng field còn thiếu;
“sửa thông tin” chuyển sang bước chọn field. Correction giữ nguyên các booking
field không liên quan, reset confirmation/retry và quay lại `CONFIRM` sau khi
resolve xong. Raw correction được ưu tiên hơn structured understanding và model
correction không grounded bị loại. Correction khi side effect đang pending tiếp
tục đi `RECONCILIATION_REQUIRED`.

P4.4 đã nối `HELP`, `PAUSE`, `RESUME`, `CHANGE_INTENT` và FAQ interruption.
`interrupted_workflow` chỉ giữ workflow, resumable step, confirmation, retry và
reason; business data vẫn ở namespace typed hiện có. Agent hỗ trợ một frame,
chặn nested interruption, không pause/switch khi tool pending, và giữ
side-effect reconciliation. FAQ có thể xen giữa Booking/Trip Lookup, trả lời có
grounding rồi mời user resume; resume restore đúng step và xóa FAQ namespace.
Cancel/goodbye xử lý riêng active và interrupted workflow theo target.

P4.5 đã hoàn tất hardening xuyên lớp. Các location reference chưa grounded như
“nhà”, “ở đó”, “chỗ cũ” phải được hỏi lại và không thể đi tới
`create_booking`; policy được enforce ở workflow, local mock và guardrail cuối.
CLI coi `HANDOFF`/`END_SESSION` là terminal signal và chỉ nhận hội thoại mới sau
`/reset`. Full-flow tests kiểm tra history, FAQ interruption, resume, repeat,
correction, booking completion và session isolation. Provider tests opt-in kiểm
tra ordinal rewrite và không tự bịa địa chỉ nhà. Toàn bộ P4 hiện complete.

### Interactive local test

`examples/core_agent_chat.py` giữ `AgentState` qua nhiều lượt, acknowledge
assistant delivery và tự chạy deterministic mock Backend cho Maps, Booking,
Trip Lookup, Knowledge và Handoff. Understanding/rewrite vẫn dùng provider thật
theo `.env`; mock chỉ thay các business service chưa được nối ở local.

```bash
AGENT_REWRITE_ENABLED=true \
.venv/bin/python -u -m examples.core_agent_chat
```

Các lệnh trong CLI: `/state`, `/history`, `/config`, `/reset`, `/help`, `/quit`.
Sau handoff/end, dùng `/reset` để tạo session và memory mới. CLI không in API key.

Luồng P5 ngắn để test bằng bàn phím:

```text
Tôi muốn đặt xe từ VinUni đến Times City bằng xe 4 chỗ
0901234567
Đổi xe sang xe máy
Đúng, đặt giúp tôi
Hủy chuyến
Đúng
```

CLI sẽ tự mock `search_place`, `estimate_fare`, `get_vehicle_options`,
`create_booking` và `cancel_booking`; LLM understanding, rewrite và vehicle
recommendation vẫn dùng cấu hình `.env`.

Booking hiểu số hành khách, hành lý và ưu tiên xe. Agent không map cứng nhu cầu
sang loại xe: nó gọi `get_vehicle_options`, chỉ nhận catalog/availability/giá từ
Backend, rồi LLM có thể recommend một `option_id` trong đúng danh sách đó. Nếu
LLM tắt, lỗi hoặc không đủ căn cứ, Agent chỉ trình bày các option để user chọn.
LLM không được tạo option, giá hay capacity mới; recommendation vẫn cần user
chọn trước khi đi tiếp.
Số liên hệ đặt xe phải là số di động Việt Nam 10 chữ số với prefix
`03/05/07/08/09`; đầu số cũ như `012` bị hỏi lại.
