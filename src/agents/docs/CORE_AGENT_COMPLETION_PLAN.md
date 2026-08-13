# Core Agent Completion Plan — From Baseline to Production-Ready

Tài liệu này là kế hoạch triển khai tiếp theo cho Core Agent GSM-08 sau khi
walking skeleton và baseline F1–F8 đã hoàn thành.

Đọc kèm:

- [`README.md`](../README.md): shared contracts và trạng thái implementation hiện tại.
- [`AGENTS.md`](AGENTS.md): nguyên tắc bắt buộc khi sửa code Agentic AI.
- [`CORE_AGENT_IMPLEMENTATION_PLAN.md`](CORE_AGENT_IMPLEMENTATION_PLAN.md): kế
  hoạch xây baseline ban đầu.
- [`VOICE_AGENT_DESIGN.md`](VOICE_AGENT_DESIGN.md): boundary giữa Agent, Backend
  và Voice Runtime.
- [`BACKEND_INTEGRATION.md`](BACKEND_INTEGRATION.md): contract tích hợp Backend.

Tài liệu này thay thế vai trò roadmap tiếp theo của
`CORE_AGENT_IMPLEMENTATION_PLAN.md`, nhưng không thay shared contracts trong
`README.md`. Nếu có xung đột, requirement cụ thể đã được lead duyệt và
`README.md` được ưu tiên.

---

## 1. Trạng thái baseline hiện tại

Core Agent hiện đã có:

- `AgentInput + AgentState -> AgentAction` bằng Pydantic;
- deterministic router và workflow registry;
- state/version validation và in-memory store cho test;
- typed tool call/result lifecycle và correlation;
- Ride Booking, Trip Lookup, FAQ/RAG và Human Handoff workflows;
- global guardrails và offline evaluator;
- LangGraph one-turn adapter không sở hữu persistence;
- rule-based understanding và OpenAI structured understanding opt-in;
- multi-turn text tests offline.

Baseline này chứng minh kiến trúc và các happy path chính, nhưng chưa phải một
voice agent production hoàn chỉnh.

Khoảng trống lớn nhất là conversation memory. `AgentState` có
`conversation_history`, nhưng history hiện mới là contract và helper; chưa được
nối vào turn lifecycle, chưa phản ánh nội dung TTS user thực sự nghe và chưa
được đưa vào language understanding.

Nói cách khác:

```text
Agent hiện nhớ business step
nhưng chưa thực sự nhớ cuộc nói chuyện.
```

---

## 2. Kiến trúc đích

```text
Final STT transcript + delivery/tool events
                    ↓
          Backend loads AgentState
                    ↓
       Conversation History Lifecycle
                    ↓
          Conversation Context Builder
                    ↓
       Contextual User Message Rewriter
                    ↓
       Structured Language Understanding
                    ↓
       Global Policy / Conversation Repair
                    ↓
           Router / Active Workflow
                    ↓
        Deterministic Business Workflow
                    ↓
               AgentAction
                    ↓
   Backend persists state before execution
                    ↓
     Tool / TTS / Handoff / End Session
```

Boundary bắt buộc vẫn giữ nguyên:

```text
Agent quyết định; Backend thực thi; Voice Runtime quản lý audio.
```

Core Agent không trực tiếp gọi Maps, Booking, Trip, Knowledge, TTS, telephony
hoặc database production.

---

## 3. Phân loại state và ownership

Không gộp mọi dữ liệu vào một history tự do. Hệ thống cần phân biệt:

| Loại dữ liệu | Mục đích | Source of truth / owner |
|---|---|---|
| Business state | Workflow, step, slots, confirmation, pending tool | `AgentState`, Backend persist |
| Recent conversation context | User đã nói gì, assistant đã thực sự nói gì | Backend/Voice events, Agent đọc |
| Conversation summary | Nén phần history cũ cho context | Agent tạo có kiểm soát, Backend persist |
| Audit/event history | Tool events, latency, lỗi, trace | Backend observability |
| Long-term user memory | Preferences qua nhiều session | Ngoài MVP trước mắt; Backend/user profile |

Nguyên tắc:

- Business state luôn có quyền ưu tiên hơn conversation summary.
- Raw transcript không tự động trở thành business fact.
- Raw tool payload không được đưa vào conversation history hoặc model context.
- History không thay thế audit log.
- Long-term memory không được namespace chỉ bằng `session_id`; phải dựa trên
  authenticated user và consent/policy phù hợp.

---

## 4. Thứ tự triển khai

Trạng thái hiện tại:

```text
P1 History Contract                         implemented
P2 Turn History Lifecycle                   pending
P3 Context Builder + Rewrite + Understanding pending
P4–P8                                       pending
```

```text
P1 History Contract
        ↓
P2 Turn History Lifecycle
        ↓
P3 Context Builder + LLM Rewrite + Understanding
        ↓
P4 Conversation Repair
        ↓
P5 Ride Booking Completion
        ↓
P6 Trip Lookup + FAQ/RAG Completion
        ↓
P7 Production Hardening + Integration Contract
        ↓
P8 Evaluation + Readiness Validation
```

P1–P3 tạo thành milestone **Conversation Memory**. Không nên triển khai P4–P6
trước khi lifecycle và context contract ổn định, nếu không các workflow sẽ phải
được sửa lại khi history được kết nối.

Mỗi phase phải là một change set có thể review độc lập, có docs, tests và không
trộn refactor ngoài scope.

---

## 5. P1 — Conversation History Contract

### Mục tiêu

Chốt dữ liệu hội thoại nào được lưu, ai tạo, ai xác nhận và dữ liệu nào được
phép đưa vào model context.

### Contract đề xuất

Mở rộng `ConversationMessage` theo hướng backward-compatible:

```text
message_id: str
turn_id: str
role: USER | ASSISTANT | TOOL
content: str
message_type: USER_TRANSCRIPT | ASSISTANT_SPEECH |
              TOOL_SUMMARY | CONVERSATION_SUMMARY
delivery_status: FINAL | PENDING | DELIVERED | INTERRUPTED | FAILED
stt_confidence: float | None
created_at: datetime | None
```

`AgentState` dự kiến có:

```text
conversation_history: list[ConversationMessage]
conversation_summary: ConversationSummary | None
```

Không thêm field chỉ vì framework khác có. Field chỉ được thêm khi có consumer
rõ ràng trong P2 hoặc P3.

### Ownership

- Final user transcript được tạo từ Backend/Voice input event.
- Agent có thể đề xuất assistant speech ở trạng thái `PENDING`.
- Backend/Voice xác nhận `DELIVERED`, `INTERRUPTED` hoặc `FAILED` sau TTS.
- Nếu bị barge-in, history không được giả định toàn bộ message đã được nghe.
- Tool result chỉ được biểu diễn bằng safe semantic summary khi thật sự cần cho
  conversation context.
- Raw audio, credentials, provider payload, stack trace và PII không cần thiết
  không được lưu trong history.

### State versioning

Không gọi `append_message()` nhiều lần làm mỗi logical turn tăng version nhiều
lần. History phải được merge vào cùng validated state update của turn hoặc một
delivery acknowledgement transaction riêng có `expected_version`.

### Files dự kiến

- `src/agents/state.py`
- `src/agents/schemas.py` nếu `AgentInput` cần `turn_id`
- `src/agents/README.md`
- `src/agents/BACKEND_INTEGRATION.md`
- `tests/test_agents/test_state.py`
- `tests/test_agents/test_history.py`

### Tests bắt buộc

1. Typed message validation.
2. Backward compatibility với state cũ.
3. Bounded history.
4. Duplicate `message_id`/`turn_id` policy.
5. Session isolation.
6. Invalid delivery transition bị reject.
7. PII/tool-payload policy.
8. State version tăng đúng theo transaction semantics.

### Definition of Done

- Contract và ownership được tài liệu hóa đầy đủ.
- Contract tests pass.
- Chưa cần thay đổi business behavior.
- Backend/Voice lead có thể xác nhận cách gửi delivery acknowledgement.

### Contract impact

Cao. Đây là shared-contract change và cần lead review trước khi merge.

---

## 6. P2 — Turn History Lifecycle

### Mục tiêu

Kết nối history vào one-turn lifecycle để `conversation_history` không còn là
dead field.

### Luồng chuẩn

```text
1. Voice gửi final transcript cùng turn_id.
2. Backend load AgentState.
3. Agent xử lý transcript và trả AgentAction.
4. History reducer tạo:
   - USER_TRANSCRIPT / FINAL;
   - ASSISTANT_SPEECH / PENDING nếu action có message.
5. Backend apply state_updates và persist atomic.
6. Backend thực thi action/TTS.
7. Voice báo delivered/interrupted/failed.
8. Backend apply delivery acknowledgement bằng message_id/turn_id.
```

Tool-result-only turn không tạo user transcript rỗng. `CALL_TOOL` không append
raw result vào history.

### Thành phần dự kiến

```text
ConversationHistoryReducer
append_turn_messages()
acknowledge_assistant_delivery()
deduplicate_turn()
prune_history()
```

Reducer phải là pure function. Nó không đọc/ghi database và không giữ mutable
session state trong process.

### Idempotency

- Mỗi input turn cần stable `turn_id` do Backend/Voice cung cấp.
- Retry cùng `turn_id` không được append transcript lần hai.
- Delivery event phải tham chiếu đúng `message_id` hoặc `turn_id`.
- Version conflict phải được xử lý trước khi action được execute.

### Files dự kiến

- `src/agents/history.py` mới
- `src/agents/agent.py`
- `src/agents/guardrails.py`
- `src/agents/state.py`
- `examples/core_agent_demo.py`
- `tests/test_agents/test_history.py`
- `tests/test_agents/test_integration_scenarios.py`

### Tests bắt buộc

1. User transcript append đúng một lần.
2. Assistant message bắt đầu ở `PENDING`.
3. Delivery acknowledgement hợp lệ.
4. Barge-in đánh dấu `INTERRUPTED` và không giả định full message đã nghe.
5. Failed TTS không xuất hiện như delivered context.
6. Duplicate turn/event không tạo message mới.
7. Tool-result-only turn không tạo user message rỗng.
8. Raw tool payload không bị lưu.
9. Version conflict không tạo history nửa vời.
10. Demo multi-turn lưu history đúng.

### Definition of Done

- Mọi text turn có deterministic history transition.
- Backend có thể persist một cách atomic trước execution.
- History phản ánh được trạng thái delivery của lời assistant.

---

## 7. P3 — Context Builder, Contextual Rewrite và Understanding

### Mục tiêu

Cho Agent hiểu các phát ngôn phụ thuộc ngữ cảnh mà vẫn giữ business transition
deterministic.

### Pipeline

```text
raw transcript
    ↓
ConversationContextBuilder
    ↓
ContextualUserMessageRewriter
    ↓
LanguageUnderstandingPort
    ↓
UnderstandingResult
    ↓
Router / Workflow
```

### 7.1 Conversation Context Builder

Builder nhận:

- active workflow và step;
- validated business snapshot;
- pending tool identity;
- last assistant question;
- recent delivered/interrupted messages;
- recent candidate list;
- conversation summary;
- raw current transcript.

Builder trả context tối thiểu cần thiết cho model:

```text
recent_messages
last_assistant_question
active_business_snapshot
available_candidates
conversation_summary
known_fields
```

Chính sách:

- Budget theo token/character, không chỉ số message.
- Ưu tiên message gần nhất và liên quan active workflow.
- Không đưa message `FAILED` vào model context.
- Với message `INTERRUPTED`, chỉ dùng phần được xác nhận đã phát nếu có.
- Mask phone trong conversational text khi structured slot đã tồn tại.
- Không đưa raw tool payload hoặc provider error.
- Summary không được override validated business state.

### 7.2 Contextual LLM rewrite cho user message

Đây là bước được bổ sung từ review. Rewriter dùng history và current state để
làm rõ phát ngôn ngắn, đại từ hoặc tham chiếu.

Ví dụ:

```text
Assistant: Tôi tìm thấy Hồ Gươm và Phố đi bộ Hồ Gươm. Bạn chọn số mấy?
Raw user: Cái thứ hai.
Rewritten: Người dùng chọn Phố đi bộ Hồ Gươm làm điểm đón.
```

```text
Raw user: Đổi chỗ lúc nãy sang Times City.
Rewritten: Người dùng muốn đổi điểm đón hiện tại sang Times City.
```

Output đề xuất:

```text
original_text
rewritten_text
resolved_references[]
ambiguities[]
changed
confidence
```

Mỗi resolved reference nên chứa:

```text
original_phrase
resolved_value
source_turn_id
```

### Safety rules cho rewrite

- Luôn giữ `raw_transcript`; không ghi đè lời user.
- Rewrite không phải business source of truth.
- Không tự thêm address, phone, confirmation hoặc intent không có bằng chứng.
- Không tự resolve place hoặc chọn candidate không được user chỉ định.
- Không trực tiếp chọn workflow hoặc phát tool call.
- Nếu thiếu context, giữ nguyên text và trả ambiguity.
- Explicit booking confirmation phải có evidence từ raw user utterance; không
  được dựa duy nhất vào câu do model rewrite.
- Timeout, provider error hoặc invalid structured output phải fallback an toàn.

### Khi nào gọi rewriter

Không gọi LLM rewrite cho mọi turn. Dùng deterministic gate:

- có đại từ/tham chiếu: “ở đó”, “cái kia”, “lúc nãy”;
- câu trả lời ngắn phụ thuộc câu hỏi trước;
- selection bằng số hoặc mô tả tương đối;
- correction mơ hồ;
- user đổi ý hoặc hỏi xen ngang;
- rule-based understanding không đủ confidence.

Fast path không cần rewrite:

```text
Tôi muốn đặt xe từ Hồ Gươm đến Times City.
```

### 7.3 Structured Understanding

Mở rộng `UnderstandingContext` để nhận context được sanitize, không nhận toàn bộ
`AgentState` tùy ý.

`UnderstandingResult` dự kiến bổ sung:

```text
dialogue_act
referenced_candidate_index
cancel_intent
repeat_intent
confidence_by_field
ambiguities
rewrite_evidence
```

LLM chỉ extract semantic data. Router/workflow vẫn quyết định transition.

### Files dự kiến

- `src/agents/context.py` mới
- `src/agents/understanding/models.py`
- `src/agents/understanding/base.py`
- `src/agents/understanding/openai.py`
- `src/agents/understanding/rules.py`
- `src/agents/understanding/service.py`
- `src/agents/agent.py`
- `tests/test_agents/test_context.py`
- `tests/test_agents/test_rewriter.py`
- `tests/test_agents/test_understanding.py`

### Tests bắt buộc

1. Resolve candidate từ câu “cái thứ hai”.
2. Resolve field reference từ “đổi chỗ lúc nãy”.
3. Repeat/reference dựa trên last delivered assistant message.
4. Không dùng assistant message chưa được phát.
5. Không hallucinate field mới.
6. Rewrite không thể bypass booking confirmation.
7. History không override business state.
8. Không lẫn context giữa session.
9. Rewriter chỉ được gọi khi gate yêu cầu.
10. Provider timeout/error fallback về raw text/rules.
11. Tool-result-only turn không gọi rewriter.

### Definition of Done

- Agent xử lý đúng các câu phụ thuộc context đã định nghĩa.
- Raw và rewritten text cùng tồn tại để audit/eval.
- Rewrite failure không làm hỏng cuộc gọi.
- Không có safety rule nào chỉ dựa vào rewritten text.

---

## 8. P4 — Conversation Repair và Workflow Interruption

### Mục tiêu

Cho phép user sửa, hủy, yêu cầu nói lại, hỏi xen ngang, chuyển mục tiêu và quay
lại workflow trước đó.

### Dialogue acts tối thiểu

```text
CONTINUE
REPEAT
CORRECT
CANCEL
START_OVER
HELP
CHANGE_INTENT
PAUSE
RESUME
GOODBYE
```

### Thứ tự xử lý

```text
Global safety policy
→ detect conversation command
→ conversation repair handler
→ resume/switch/cancel workflow
→ normal router
```

### Interrupted workflow

Cần chốt một trong hai contract tối thiểu:

```text
interrupted_workflow: WorkflowSnapshot | None
```

hoặc:

```text
workflow_stack: list[WorkflowFrame]
```

Không đưa full arbitrary state vào stack. Mỗi frame chỉ chứa workflow, step và
namespace business data cần resume.

Ví dụ:

```text
Booking / COLLECT_PHONE
→ user hỏi FAQ về thanh toán
→ pause Booking
→ FAQ retrieve/respond
→ resume Booking / COLLECT_PHONE
```

### Cancel semantics

- Cancel trước side effect: clear active workflow và pending read-only request
  theo policy.
- Cancel trong lúc `create_booking` pending: không được giả định side effect đã
  dừng; cần reconciliation với Backend.
- Start over phải clear đúng workflow namespace và confirmation.
- Goodbye trả `END_SESSION` nếu không có side effect chưa xác định kết quả.

### Files dự kiến

- `src/agents/repair.py` mới
- `src/agents/state.py`
- `src/agents/router.py`
- `src/agents/agent.py`
- `src/agents/understanding/models.py`
- workflows liên quan
- `tests/test_agents/test_conversation_repair.py`

### Tests bắt buộc

1. Repeat lời assistant thực sự đã phát.
2. Cancel booking trước confirmation.
3. Cancel trong khi booking outcome unknown.
4. Start over clear đúng namespace.
5. Correction reset confirmation.
6. FAQ xen giữa Booking rồi resume đúng step.
7. Change intent có explicit confirmation khi cần.
8. Goodbye phát `END_SESSION` an toàn.
9. Không tạo workflow-stack loop.
10. Retry/low-confidence policy vẫn có quyền ưu tiên.

### Definition of Done

Active workflow không còn nuốt mọi phát ngôn của user. Các repair event có
transition rõ ràng và test deterministic.

---

## 9. P5 — Hoàn thiện Ride Booking

### Mục tiêu

Đưa Booking từ happy-path MVP thành workflow đầy đủ và recoverable.

### Phạm vi

- Correction cho phone.
- Vehicle type nếu product contract yêu cầu.
- Route/fare estimate nếu Backend cung cấp tool contract.
- Cancel booking.
- Candidate presentation/selection policy nhất quán.
- Retryable place-search errors.
- Confirmation parsing an toàn hơn keyword substring.
- Supersede pending search khi user đổi địa chỉ.
- Duplicate/stale booking result.
- Timeout/unknown booking outcome và reconciliation.
- Không phát lại `create_booking` sau success.

### Dependency reset rules

```text
pickup hoặc destination đổi
→ clear resolved place tương ứng
→ clear route/fare phụ thuộc
→ reset confirmation
→ resolve lại
```

```text
phone hoặc vehicle đổi
→ reset confirmation
→ giữ resolved locations
```

### Tool additions có thể cần

Chỉ thêm sau khi Backend contract được duyệt:

```text
estimate_route
estimate_fare
cancel_booking
reconcile_booking
```

`call_id` vẫn chỉ dùng correlation. Side-effect idempotency key thuộc Backend.

### Files dự kiến

- `src/agents/workflows/booking.py`
- `src/agents/workflows/booking_models.py`
- `src/agents/tools/schemas.py`
- tool builders liên quan
- `src/agents/policy.py`
- `tests/test_agents/test_booking.py`
- `tests/test_agents/test_integration_scenarios.py`

### Tests bắt buộc

1. Full happy path.
2. Zero/one/many candidates.
3. Phone/address/vehicle correction.
4. Confirmation reject/unclear/confirm.
5. No booking before explicit confirmation.
6. Retryable and critical search errors.
7. Duplicate `ToolResult`.
8. Booking timeout with unknown outcome.
9. Successful replay không tạo booking mới.
10. Cancel trước/sau side-effect boundary.

### Definition of Done

Mọi critical transition có invariant/test; không có đường nào phát
`create_booking` trước explicit confirmation.

---

## 10. P6 — Hoàn thiện Trip Lookup và FAQ/RAG

### 10.1 Trip Lookup

Phạm vi:

- Contextual follow-up: “ETA bao lâu?”, “tài xế tới đâu rồi?”.
- Nhiều chuyến khớp cùng phone.
- Safe selection không đọc full PII.
- Duplicate/stale result.
- Shared retry policy.
- Map backend status sang câu tiếng Việt tự nhiên.
- Không đưa status/ETA ngoài validated tool result.

### 10.2 FAQ/RAG

Phạm vi:

- Contextual query rewriting từ recent history.
- Multi-turn FAQ follow-up.
- Natural grounded answer generator.
- Source/citation metadata tách khỏi TTS text.
- Knowledge freshness/version/effective date.
- Retrieved-content prompt-injection filtering.
- Citation correctness.
- Fallback hoặc handoff theo loại câu hỏi/rủi ro.

`GroundedAnswerGenerator` có thể dùng model adapter, nhưng output phải được kiểm
tra chỉ dựa trên supplied documents. Deterministic extractive generator tiếp tục
được dùng cho unit tests/fallback.

### Files dự kiến

- `src/agents/workflows/trip_lookup.py`
- `src/agents/workflows/trip_lookup_models.py`
- `src/agents/workflows/faq.py`
- `src/agents/workflows/faq_models.py`
- `src/agents/rag/`
- `src/agents/tools/schemas.py`
- tests tương ứng

### Tests bắt buộc

1. Trip follow-up dùng kết quả validated trước đó.
2. Multiple-trip selection.
3. Không leak phone.
4. FAQ follow-up rewrite đúng query.
5. Grounded answer không thêm unsupported facts.
6. Document prompt injection không thay đổi system behavior.
7. Low-score/stale source fallback.
8. Citation/source metadata đúng document.
9. Retry/error/mismatch không tạo loop.

### Definition of Done

Trip Lookup chỉ nói dữ liệu từ tool; FAQ multi-turn vẫn grounded và có source
metadata kiểm chứng được.

---

## 11. P7 — Production Guardrails và Integration Contract

### Mục tiêu

Hoàn thiện reliability, privacy và contract để Backend/Voice tích hợp production.

### Guardrails

- Central retry policy theo workflow/tool/risk.
- Turn, tool-call và workflow-stack limits.
- Booking reconciliation requirement.
- Tool deadline và stale-result window.
- PII redaction theo từng destination: model context, trace, handoff, storage.
- Spoken response length/style validation.
- Retrieved-content prompt-injection defense.
- Session isolation và authenticated ownership assumptions.
- Safe diagnostic reason, không chứa chain of thought hoặc raw PII.

### Backend/Voice contract

Chốt các event/field:

```text
turn_id
message_id
final_transcript
assistant_delivery_ack
barge_in/truncation
tool_result
disconnect/resume
end_session
```

Backend tiếp tục tuân thủ:

```text
authenticate
→ load state
→ invoke agent
→ validate/apply updates
→ persist with expected_version
→ execute action
```

### Persistence

- Production PostgreSQL/Redis implementation thuộc Backend.
- Atomic compare-and-set bằng `state_version`.
- TTL, retention và deletion policy.
- Encryption in transit/at rest.
- Transcript/recording consent.
- Idempotent turn and delivery events.
- Session resume lấy đúng state mới nhất.

Không bật LangGraph checkpointer nếu chưa loại bỏ nguy cơ có hai state owners.
Nếu sau này dùng checkpointer, phải có mapping và migration plan rõ ràng với
`AgentState`/Backend persistence.

### Observability

Trace tối thiểu:

```text
trace_id
hashed_session_id
turn_id
state_version_before/after
workflow/step before/after
dialogue_act
rewrite_used
action_type
tool_name/call_id
latency breakdown
error_code
handoff_reason
delivery_status
```

### Files dự kiến

- `src/agents/guardrails.py`
- `src/agents/policy.py`
- `src/agents/BACKEND_INTEGRATION.md`
- `src/agents/VOICE_AGENT_DESIGN.md`
- contract/integration tests

### Definition of Done

Backend và Voice có thể implement integration chỉ dựa trên documented contract;
không cần suy đoán state, delivery hoặc retry semantics.

---

## 12. P8 — Evaluation và Readiness Validation

### Mục tiêu

Đo được chất lượng Agent theo hành vi thực tế, không chỉ schema validity và
single-turn action accuracy.

### Metrics

```text
intent accuracy
slot extraction accuracy
context recall accuracy
rewrite accuracy / hallucination rate
action accuracy
tool name/argument accuracy
workflow completion rate
correction success rate
conversation repair success rate
confirmation safety violation rate
duplicate side-effect violation rate
grounding/faithfulness rate
citation correctness
PII leakage rate
handoff precision/recall
average/p50/p95/p99 Agent latency
turn count and retry count
```

### Scenario groups

1. Booking happy and adversarial paths.
2. Missing/ambiguous Vietnamese addresses.
3. STT noise and low confidence.
4. History references and elliptical speech.
5. Contextual rewrite success/failure/hallucination.
6. Barge-in and partially delivered speech.
7. Correction, rejection, cancel and start-over.
8. Workflow interruption/resume.
9. Duplicate input/tool/delivery events.
10. Tool timeout and unknown booking outcome.
11. Trip lookup follow-ups.
12. FAQ grounding, stale source and prompt injection.
13. Emergency/complaint/handoff.
14. Session isolation, reconnect and resume.

### Test layers

```text
1. Pure unit tests
2. Deterministic multi-turn tests
3. Fake-provider structured understanding/rewrite tests
4. Optional real-model evaluation
5. Backend/Voice text integration tests
6. Full audio E2E in integration environment
```

Unit tests không gọi provider thật. Real-model tests phải opt-in, có dataset cố
định và không chứa production PII.

### Readiness gates

Threshold cụ thể được chốt cùng product/lead trước release. Tối thiểu phải có:

- zero booking-before-confirmation violation;
- zero cross-session context leak;
- zero duplicate booking trong replay suite;
- zero unsupported FAQ fact trong deterministic grounding suite;
- all structured outputs schema-valid;
- latency và handoff metrics có report rõ ràng.

### Definition of Done

Có versioned evaluation dataset, regression thresholds và readiness report; kết
quả không chỉ là “pytest passed”.

---

## 13. Những việc chưa làm trong roadmap này

Các phần sau nằm ngoài Core Agent hoặc cần task riêng:

- WebRTC/WebSocket/audio streaming;
- VAD, turn detection và acoustic barge-in implementation;
- STT/TTS provider execution;
- Maps/Booking/Trip executors;
- production vector store/knowledge ingestion;
- PostgreSQL/Redis implementation;
- telephony/SIP transfer;
- frontend call UI;
- user-profile long-term memory qua nhiều session;
- analytics dashboard.

Core Agent chỉ định nghĩa contract cần thiết để các phần trên tích hợp an toàn.

---

## 14. Quy trình thực hiện từng phase

Trước khi code:

1. Confirm phase được duyệt.
2. Đọc lại `README.md`, `AGENTS.md` và files liên quan.
3. Inspect tests và current behavior.
4. Chốt contract impact và assumptions.
5. Đưa implementation plan ngắn theo file.

Trong khi code:

1. Ưu tiên pure functions và typed contracts.
2. Giữ deterministic safety rules ngoài prompt.
3. Không gọi external service trong workflow.
4. Không tạo state owner thứ hai.
5. Thêm test cùng behavior mới.
6. Cập nhật docs ngay khi shared contract đổi.

Sau khi code:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m compileall -q src tests examples
git diff --check
```

Handoff của mỗi phase phải nêu:

- files đã sửa;
- contract/behavior thay đổi;
- state transitions mới;
- tests đã chạy;
- dependency hoặc risk còn lại;
- phase tiếp theo được phép bắt đầu hay chưa.

---

## 15. Milestones

### Milestone A — Conversation Memory

Bao gồm P1–P3.

Hoàn thành khi:

- history được ghi và persist đúng lifecycle;
- history phản ánh actual delivered speech;
- context được prune/redact;
- Agent hiểu contextual references;
- LLM rewrite có structured evidence và safe fallback;
- rewrite không bypass deterministic business rules.

### Milestone B — Natural Workflow Control

Bao gồm P4–P6.

Hoàn thành khi:

- repeat/cancel/correction/interruption/resume hoạt động;
- Booking xử lý đầy đủ correction/recovery;
- Trip và FAQ hỗ trợ grounded follow-up;
- active workflow không nuốt intent xen ngang.

### Milestone C — Production Readiness

Bao gồm P7–P8.

Hoàn thành khi:

- Backend/Voice contracts đầy đủ;
- reliability/privacy/observability policies có test;
- evaluation suite đo multi-turn, context, rewrite, safety và latency;
- readiness gates đạt threshold đã duyệt.

---

## 16. Quy tắc ra quyết định

Khi có nhiều phương án, ưu tiên theo thứ tự:

1. Không tạo booking ngoài ý muốn.
2. Không làm sai hoặc mất business state.
3. Không lẫn session hoặc lộ PII.
4. Conversation context phản ánh điều user thực sự nghe/nói.
5. Deterministic behavior cho business-critical rules.
6. Offline testability.
7. Latency và chi phí voice turn.
8. Framework convenience.

History, LLM rewrite và framework memory chỉ hỗ trợ hiểu hội thoại. Chúng không
được thay thế typed state, confirmation guardrail, tool correlation hoặc Backend
idempotency.
