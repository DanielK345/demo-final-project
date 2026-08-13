# Core Agent Implementation Plan — GSM-08

Tài liệu này là kế hoạch kỹ thuật để **một developer** tiếp tục triển khai toàn
bộ Core Agent cho đề tài GSM-08 sau khi F1 (Core & Routing) và F5 (Human
Handoff) đã có baseline.

Đọc kèm:

- [`README.md`](README.md): shared contracts và source of truth của track.
- [`AGENTS.md`](AGENTS.md): nguyên tắc bắt buộc khi sửa code.
- [`VOICE_AGENT_DESIGN.md`](VOICE_AGENT_DESIGN.md): kiến trúc và kết quả
  nghiên cứu framework.

Tài liệu này tập trung vào **cách triển khai tiếp theo**. Nếu có xung đột,
shared contracts và yêu cầu đã được xác nhận trong `README.md` được ưu tiên.

---

## 1. Mục tiêu sản phẩm

Core Agent là decision engine cho tổng đài giọng nói đặt xe và tra cứu dịch vụ.
Mỗi lần được gọi, Agent nhận `AgentInput` cùng `AgentState`, sau đó trả đúng một
`AgentAction`:

```text
AgentInput + AgentState
          ↓
       Core Agent
          ↓
      AgentAction
```

Core Agent phải hỗ trợ:

1. hiểu ý định và dữ liệu người dùng nói bằng tiếng Việt;
2. duy trì workflow nhiều lượt;
3. thu thập, xác minh và cho phép sửa thông tin;
4. yêu cầu Backend gọi tool;
5. xử lý `ToolResult` ở lượt tiếp theo;
6. trả lời FAQ có grounding;
7. handoff khi không thể tiếp tục an toàn;
8. tạo câu trả lời ngắn, tự nhiên và phù hợp TTS.

Core Agent không xử lý audio, WebRTC, VAD, barge-in, STT/TTS lifecycle,
PostgreSQL hay API thật.

---

## 2. Kiến trúc đích

```text
React Web Call
      │ audio
      ▼
Voice Runtime (WebRTC/WebSocket, VAD, STT, TTS, barge-in)
      │ transcript + confidence
      ▼
FastAPI Backend / Agent Gateway
      ├── load/persist AgentState
      ├── validate identity/session
      └── execute AgentAction
              │
              │ AgentInput + AgentState
              ▼
┌─────────────────────────────────────────────────┐
│                  CORE AGENT                     │
│                                                 │
│  Input validation / session isolation           │
│                  ↓                              │
│  Global policy (confidence, retry, emergency)   │
│                  ↓                              │
│  Router: resume active workflow / classify      │
│                  ↓                              │
│  Deterministic business workflow                │
│      ├── Ride Booking                           │
│      ├── Trip Lookup                            │
│      ├── FAQ + RAG                              │
│      └── Human Handoff                          │
│                  ↓                              │
│  Tool-call builder / response policy            │
│                  ↓                              │
│              AgentAction                        │
└─────────────────────────────────────────────────┘
      │
      ▼
FastAPI Backend / Action Executor
      ├── ASK_USER / RESPOND → TTS
      ├── CALL_TOOL → Maps/Booking/Trip/Knowledge
      ├── HANDOFF → operator/transfer service
      └── END_SESSION → session lifecycle
```

### Boundary bắt buộc

```text
Agent quyết định; Backend thực thi.
```

Agent phát `CALL_TOOL` rồi kết thúc turn. Backend gọi service thật và gửi
`ToolResult` trở lại trong một invocation mới. Không chạy vòng tool tự động bên
trong Core Agent.

---

## 3. Pattern chọn lọc từ các framework

Không copy toàn bộ framework vào project. Chỉ áp dụng pattern phù hợp boundary.

### Rasa CALM

Áp dụng mô hình hybrid:

- LLM/NLU hiểu lời nói và sinh dữ liệu có cấu trúc;
- flow/state machine thực thi business logic deterministic;
- correction, cancel, repeat và clarification là conversation-repair events;
- LLM không được tự quyết định rule đặt xe quan trọng.

### Vocode

Áp dụng action lifecycle:

```text
ToolCall → Backend executor → ToolResult → workflow tiếp tục
```

Khác Vocode, executor của dự án luôn nằm ngoài `src/agents/`.

### LiveKit Agents

Áp dụng:

- workflow nhỏ, có completion condition;
- typed tool arguments;
- handoff có context;
- text-mode behavioral tests;
- câu trả lời ngắn, tối ưu cho speech.

Không đưa `AgentSession`, audio lifecycle hoặc external API execution vào Core.

### Pipecat

Áp dụng typed event, correlation, ordering và latency tracing ở integration
boundary. Audio frame, interruption và pipeline processor thuộc Voice Runtime.

### OpenAI Agents SDK

Áp dụng structured output, guardrails, tracing/evaluation và model abstraction.
Không dùng SDK runner để tự thực thi tool loop hoặc thay shared contracts.

### LangGraph

LangGraph là **orchestration implementation**, không phải public contract và
không phải nơi sở hữu một bản business state thứ hai.

```text
AgentState = business source of truth
LangGraph = cách compose các bước xử lý một turn
```

Trong MVP, graph chỉ cần chạy tới khi tạo được đúng một `AgentAction` rồi dừng.
Checkpoint/persistence thật vẫn do Backend quyết định. Chỉ bật LangGraph
checkpointer khi đã thống nhất rõ mapping với `AgentState`.

---

## 4. Một turn chuẩn

```text
1. Backend load AgentState bằng session_id.
2. Backend tạo AgentInput.
3. Agent validate session isolation và input schema.
4. Global policy kiểm tra emergency, handoff, confidence, retry.
5. Nếu có current_workflow, tiếp tục workflow đó.
6. Nếu chưa có workflow, router classify intent.
7. Workflow xử lý transcript hoặc ToolResult.
8. Workflow trả đúng một AgentAction.
9. Backend validate/apply state_updates và persist state.
10. Backend thực thi action.
11. Nếu CALL_TOOL, ToolResult quay lại ở turn sau.
```

Các bước 1, 9 và 10 không nằm trong Core Agent.

---

## 5. Thiết kế state

State hiện tại là baseline:

```text
session_id
current_workflow
current_step
collected_data
pending_tool_call_id
retry_count
```

F2 cần mở rộng tối thiểu nhưng không thiết kế riêng cho Booking. Mọi thay đổi
`AgentState` là thay đổi shared contract và phải cập nhật README cùng tests.

### Fields đề xuất

```text
session_id: str
current_workflow: WorkflowType | None
current_step: str | None
collected_data: dict
pending_tool_call_id: str | None
pending_tool_name: ToolName | None
retry_count: int
confirmation: ConfirmationState
conversation_history: list[ConversationMessage]
last_stt_confidence: float | None
state_version: int
```

`pending_tool_name` giúp correlate cả `call_id` và loại tool. `confirmation`
không nên chỉ là boolean vì cần phân biệt chưa hỏi, đang chờ và đã xác nhận.

```text
NOT_REQUESTED
AWAITING_CONFIRMATION
CONFIRMED
REJECTED
```

History chỉ lưu dữ liệu cần thiết, có giới hạn số turn và policy redaction PII.
Không coi raw transcript history là business state.

### State ownership

- Workflow tạo `state_updates` dạng partial update.
- `AgentState.apply()` validate toàn bộ state sau update.
- Backend persist state đã apply.
- Workflow không mutate state trực tiếp.
- Không có module-level/session-local mutable state.
- `state_version` dành cho optimistic concurrency khi Backend tích hợp.

### Conversation repair

Correction phải được biểu diễn bằng transition rõ ràng. Khi user sửa pickup,
destination, phone, vehicle hoặc dữ liệu ảnh hưởng giá:

```text
update collected_data
→ clear resolved value nếu query thay đổi
→ confirmation = NOT_REQUESTED
→ clear fare/route phụ thuộc dữ liệu cũ
→ quay lại bước resolve tương ứng
```

---

## 6. Tool lifecycle (F6)

F6 nên hoàn thành trước các workflow thật vì F3, F4 và F7 đều phụ thuộc nó.

### Call ID

Call ID phải unique và deterministic/correlatable trong session:

```text
{session_id}:{workflow}:{tool_name}:{operation}:{sequence}
```

Không dùng một ID cố định như `session:knowledge`, vì retry có thể tạo cùng ID
cho hai operation khác nhau. Backend vẫn phải dùng idempotency key riêng cho
side effect như `create_booking`.

### Khi phát CALL_TOOL

Action phải đồng thời update:

```text
current_step = WAITING_FOR_<TOOL_RESULT>
pending_tool_call_id = ToolCall.call_id
pending_tool_name = ToolCall.tool_name
```

### Khi nhận ToolResult

Trước khi workflow diễn giải business payload, phải kiểm tra:

1. có active workflow;
2. state đang ở bước chờ tool;
3. `call_id == pending_tool_call_id`;
4. `tool_name == pending_tool_name`;
5. schema `data` đúng theo tool/status.

Result mismatch/stale/duplicate không được làm workflow tiến tiếp. Policy mặc
định: trả `HANDOFF` hoặc controlled error theo mức độ an toàn; không đoán result.

### Result schemas cần có

- `SearchPlaceResult`: zero/one/many candidates;
- `CreateBookingResult`: booking ID, status và dữ liệu Backend thực sự trả;
- `LookupTripResult`: found/not-found, status, ETA nếu có;
- `RetrieveKnowledgeResult`: documents, score, source metadata;
- normalized error: retryable/critical, code, safe message.

Không để workflow đọc dictionary tùy ý mà không validate.

### Retry

- Retry read-only tool có thể cho phép theo policy.
- `create_booking` không phát lại nếu đã có success result.
- Backend chịu timeout, network retry và idempotency.
- Workflow chịu business retry và quyết định hỏi lại/handoff.

---

## 7. Ride Booking workflow (F3)

### State machine

```text
COLLECT_PICKUP
→ RESOLVE_PICKUP
→ WAITING_FOR_PICKUP_RESULT
→ SELECT_PICKUP_CANDIDATE (nếu nhiều kết quả)
→ COLLECT_DESTINATION
→ RESOLVE_DESTINATION
→ WAITING_FOR_DESTINATION_RESULT
→ SELECT_DESTINATION_CANDIDATE (nếu nhiều kết quả)
→ COLLECT_PHONE (nếu Backend chưa có)
→ COLLECT_VEHICLE (nếu MVP yêu cầu)
→ CONFIRM
→ CREATE_BOOKING
→ WAITING_FOR_BOOKING_RESULT
→ COMPLETE
```

### Quy tắc

- Có thể extract pickup và destination từ cùng một transcript.
- Query địa điểm và resolved place phải là hai field khác nhau.
- Zero candidate: hỏi lại, tăng retry.
- One candidate: lưu resolved place và tiếp tục.
- Many candidates: đọc tối đa vài lựa chọn dễ phân biệt và yêu cầu user chọn.
- Không tự chọn candidate khi chưa đủ chắc chắn.
- Không tạo booking trước explicit confirmation.
- User sửa dữ liệu critical phải reset confirmation.
- Booking ID, giá và ETA chỉ lấy từ ToolResult.
- Sau booking success, duplicate transcript/result không được phát booking lại.

### LLM/NLU boundary

LLM có thể trả structured extraction:

```text
intent
pickup_query
destination_query
phone_number
vehicle_type
confirmation_intent: CONFIRM | REJECT | UNCLEAR
corrections
```

State machine quyết định transition. LLM không quyết định trực tiếp
`CREATE_BOOKING`.

### Voice UX

- hỏi một thông tin chính mỗi turn;
- đọc lại địa chỉ đã resolve bằng tên dễ nghe;
- confirmation phải nêu pickup, destination và thông tin quan trọng;
- không đọc place ID, call ID hoặc metadata;
- câu trả lời ưu tiên ngắn để giảm latency và hỗ trợ barge-in.

---

## 8. Trip Lookup workflow (F4)

```text
COLLECT_IDENTIFIER
→ LOOKUP_TRIP
→ WAITING_FOR_TRIP_RESULT
→ PROCESS_RESULT
→ COMPLETE / RETRY / HANDOFF
```

Quy tắc:

- identifier là booking ID hoặc phone;
- không gọi tool khi thiếu cả hai;
- validate/normalize phone trước khi gọi;
- `not_found` khác tool error;
- chỉ nói status/ETA từ ToolResult;
- nếu có nhiều chuyến, yêu cầu user chọn bằng thông tin an toàn;
- không đọc toàn bộ số điện thoại hoặc PII trong câu trả lời/log.

---

## 9. FAQ + Agentic RAG workflow (F7)

```text
RECEIVE_QUESTION
→ RETRIEVE_KNOWLEDGE
→ WAITING_FOR_KNOWLEDGE_RESULT
→ VALIDATE_RESULT
   ├── đủ score/source → GROUNDED_RESPONSE → COMPLETE
   └── thiếu bằng chứng → FALLBACK / HANDOFF
```

Quy tắc:

- luôn retrieve cho câu hỏi knowledge/service;
- validate `call_id`, tool name và result schema;
- dùng threshold có cấu hình, không hard-code rải rác;
- response chỉ dựa trên documents được trả về;
- source metadata phục vụ trace/UI, không đọc URL dài qua TTS;
- không có nguồn phù hợp thì nói không chắc và đưa phương án hỗ trợ;
- tool result đã xử lý không được gây vòng `CALL_TOOL` vô hạn.

RAG retriever thật thuộc Backend/knowledge service. `src/agents/rag/` chỉ chứa
contract, grounding policy và các implementation offline cần cho test nếu được
scope cho phép.

---

## 10. Guardrails và evaluation (F8)

Guardrail được chia thành nhiều lớp:

```text
Pydantic schema
→ session/tool correlation
→ deterministic workflow rules
→ configurable policy
→ prompt instructions
→ behavioral tests/evaluation
```

Prompt không được là lớp bảo vệ duy nhất.

### Guardrails bắt buộc

- không booking trước confirmation;
- không tự chọn địa chỉ mơ hồ;
- không tạo booking ID/price/ETA/status;
- không dùng state session khác;
- không xử lý stale/mismatched ToolResult;
- không vượt retry/turn/tool-call limit;
- FAQ không trả ngoài grounded context;
- emergency/complaint/user request được handoff;
- PII không xuất hiện trong `reason`, trace hoặc handoff summary quá mức cần thiết.

### Evaluation dimensions

- intent/workflow routing accuracy;
- slot extraction accuracy cho tiếng Việt;
- action accuracy;
- tool name/argument accuracy;
- workflow completion rate;
- correction success rate;
- confirmation safety violation rate;
- hallucination/grounding violation rate;
- handoff precision/recall;
- schema validity;
- Agent latency không gồm STT/tool/TTS.

### Scenario suite tối thiểu

1. Booking happy path.
2. Thiếu pickup/destination.
3. Hai địa điểm trong một câu.
4. Zero/one/many place candidates.
5. User sửa địa chỉ trước và sau confirmation.
6. Confirmation rõ ràng, phủ định và mơ hồ.
7. Duplicate/stale/mismatched tool result.
8. Booking timeout/error/success replay.
9. Lookup bằng booking ID và phone.
10. Trip not found/tool error.
11. FAQ có và không có grounded source.
12. User yêu cầu người thật.
13. Complaint/emergency.
14. Low STT confidence và retry limit.
15. Session isolation/resume/end.
16. PII redaction trong trace/handoff.

Unit tests phải offline và deterministic. LLM extraction tests dùng fake/stub
model adapter hoặc fixtures, không gọi provider thật.

---

## 11. Model abstraction

Không gọi provider SDK trực tiếp trong router/workflow. Dùng một interface nhỏ:

```python
class LanguageUnderstandingPort(Protocol):
    async def understand(
        self,
        transcript: str,
        context: UnderstandingContext,
    ) -> UnderstandingResult: ...
```

`UnderstandingResult` phải typed và validate. Implementation có thể dùng OpenAI,
model khác hoặc deterministic fake. Provider adapter nằm ngoài domain workflow.

Router deterministic hiện tại có thể tiếp tục là fast path. LLM fallback chỉ
dùng khi rule không đủ chắc chắn. Điều này giảm latency và chi phí.

---

## 12. LangGraph integration

Không rewrite ngay toàn bộ `LLMAgent`. Triển khai incrementally:

### Giai đoạn 1 — giữ orchestrator hiện tại

Hoàn thiện F2 và F6 bằng contracts thuần Python/Pydantic. Workflow vẫn implement
`BaseWorkflow.handle()` để tests không phụ thuộc LangGraph.

### Giai đoạn 2 — graph composition

Khi workflow contracts ổn định, `graph.py` compose các node dùng chung:

```text
validate_input
→ apply_global_policy
→ resolve_workflow
→ invoke_workflow
→ validate_action
```

Node `invoke_workflow` gọi đúng workflow registry hiện có. Không duplicate
business state machine trong graph và workflow.

### Giai đoạn 3 — chỉ thêm graph riêng khi có giá trị

Booking có thể được biểu diễn thành subgraph nếu giúp quan sát transition, nhưng
mỗi node vẫn phải trả structured transition/action và dừng tại `CALL_TOOL` hoặc
`ASK_USER`.

### Không làm

- không để LangGraph tự gọi Maps/Booking API;
- không để checkpointer trở thành state store thứ hai;
- không để graph node đọc/ghi database;
- không phụ thuộc LangGraph trong domain schemas;
- không phá API `LLMAgent.handle(input, state) -> AgentAction`.

---

## 13. Observability và PII

Mỗi turn nên tạo trace metadata có cấu trúc:

```text
trace_id
session_id_hash
workflow
step_before
step_after
action_type
tool_name
call_id
decision_latency_ms
retry_count
handoff_reason
```

Không log mặc định:

- raw audio;
- full phone number;
- full transcript chứa PII;
- địa chỉ chi tiết không cần thiết;
- credentials hoặc raw provider payload.

`reason` dùng cho debug/eval nhưng phải safe, ngắn và không chứa chain of thought.
Recording consent, retention và encryption thuộc Backend/Voice/platform policy.

---

## 14. Cấu trúc source dự kiến

Giữ cấu trúc hiện tại và chỉ thêm abstraction khi feature cần:

```text
src/agents/
├── agent.py                  # one-turn entrypoint
├── graph.py                  # optional LangGraph composition/adapter
├── router.py                 # routing, no business details
├── schemas.py                # shared I/O contracts
├── state.py                  # shared state + validated reducer
├── policies/                 # global configurable policies nếu cần
├── understanding/            # LLM/NLU port + provider-independent schemas
├── workflows/
│   ├── booking.py
│   ├── trip_lookup.py
│   ├── faq.py
│   └── handoff.py
├── tools/                    # builders/result schemas, no execution
├── rag/                      # contracts/grounding policy
├── prompts/                  # prompts, not business source of truth
└── eval/                     # scenarios/metrics nếu đặt trong source
```

Không tạo folder mới trước khi có code thực sự sử dụng nó.

---

## 15. Thứ tự triển khai cho một owner

Làm tuần tự để giảm xung đột shared contracts:

### Phase 0 — baseline

- chạy full tests/lint/compile;
- ghi nhận behavior F1/F5;
- không sửa F1/F5 trừ integration bug có test chứng minh.

### Phase 1 — F2 State & Memory

- chốt state fields;
- validated reducer/transitions;
- in-memory state store chỉ để test nếu cần;
- session isolation, version và history policy;
- cập nhật contract docs/tests.

### Phase 2 — F6 Tool Lifecycle

- typed params/results;
- call ID factory;
- pending-tool correlation;
- stale/duplicate/error policy;
- Backend executor contract documentation.

### Phase 3 — F3 Ride Booking

- implement state machine;
- extraction port/fake;
- place resolution;
- correction/confirmation;
- booking result/idempotency behavior;
- full multi-turn tests.

### Phase 4 — F4 Trip Lookup

- reuse extraction/tool lifecycle;
- identifier validation;
- result/error behavior;
- tests.

### Phase 5 — F7 FAQ + RAG

- retrieval result schema;
- threshold/grounding policy;
- response generation abstraction;
- fallback/handoff;
- tests.

### Phase 6 — F8 Guardrails & Evaluation

- gom các cross-cutting policies;
- scenario dataset;
- metrics/reporting;
- regression suite;
- latency and PII checks.

### Phase 7 — LangGraph composition

- chỉ thực hiện sau khi domain behavior ổn định;
- giữ entrypoint/contracts tương thích;
- chứng minh bằng test rằng graph và direct orchestrator cho cùng action.

F8 tests được thêm xuyên suốt từng phase, dù evaluation tổng hợp làm ở Phase 6.

---

## 16. Definition of Done cuối cùng

Core Agent hoàn thành khi:

- `AgentInput + AgentState -> AgentAction` validate ổn định;
- bốn workflow hoạt động nhiều lượt;
- booking không thể xảy ra trước confirmation;
- correction reset đúng dữ liệu phụ thuộc;
- tool result được correlate và route đúng;
- duplicate result không tạo side effect lặp;
- trip/price/ETA/status chỉ dùng dữ liệu tool;
- FAQ chỉ dựa trên context đủ tin cậy;
- low confidence, complaint, emergency và critical error được handoff;
- state không lẫn session và có thể resume;
- không có external API execution trong `src/agents/`;
- model/provider có thể thay qua adapter;
- tests offline, deterministic và bao phủ multi-turn scenarios;
- Agent có trace cần thiết nhưng không lộ PII;
- Backend và Voice tích hợp chỉ qua documented contracts;
- pytest, Ruff, compileall và `git diff --check` đều pass.

---

## 17. Nguyên tắc quyết định khi triển khai

Khi có nhiều cách thực hiện, ưu tiên theo thứ tự:

1. an toàn nghiệp vụ và không tạo booking ngoài ý muốn;
2. shared contract rõ ràng;
3. deterministic behavior cho critical rules;
4. testability offline;
5. boundary Agent/Backend/Voice;
6. latency và chi phí;
7. framework convenience.

Framework phục vụ kiến trúc; kiến trúc không được bẻ cong chỉ để dùng framework.
