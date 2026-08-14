# Voice Agent Design — AloSM Ride-Hailing

Tài liệu này giải thích **Core Agent** trong hệ thống Voice AI Ride-Hailing:
Agent là gì, nằm ở đâu trong hệ thống, xử lý một lượt hội thoại như thế nào, học
gì từ các framework Voice Agent phổ biến và vì sao kiến trúc của dự án không sao
chép nguyên mẫu của bất kỳ framework nào.

Đọc kèm:

- [`README.md`](README.md): shared contracts, cấu trúc source và feature F1–F8.
- [`AGENTS.md`](AGENTS.md): nguyên tắc bắt buộc khi sửa code Agentic AI.

---

## 1. Agent trong dự án này là gì?

Core Agent là **decision engine** của cuộc hội thoại. Với mỗi lượt, Agent nhận:

- transcript từ STT hoặc text fallback;
- độ tin cậy của STT;
- `session_id`;
- conversation state hiện tại;
- `ToolResult` nếu Backend vừa thực thi một tool.

Agent đọc dữ liệu đó rồi trả về **một quyết định có cấu trúc** (`AgentAction`).

Agent trả lời câu hỏi:

> Với trạng thái hội thoại hiện tại, hệ thống nên làm gì tiếp theo?

Agent không trả lời câu hỏi:

> API thật phải được gọi như thế nào, lưu Redis/PostgreSQL ra sao, hay cuộc gọi
> SIP được chuyển bằng cơ chế nào?

Những phần đó thuộc Backend và Voice Gateway.

---

## 2. Vị trí trong kiến trúc Voice AI

```text
Customer
   │ voice
   ▼
Voice Gateway
   │ audio
   ▼
STT
   │ transcript + confidence
   ▼
Backend / Agent Gateway
   │ AgentInput + AgentState
   ▼
Core Agent
   │ AgentAction
   ▼
Backend / Action Executor
   ├── ASK_USER / RESPOND ──► TTS ──► Customer
   ├── CALL_TOOL ───────────► External service
   ├── HANDOFF ─────────────► Operator / Voice transfer
   └── END_SESSION ─────────► Session lifecycle
```

Voice Gateway chịu trách nhiệm realtime transport, audio streaming, interruption,
disconnect/reconnect và STT/TTS lifecycle. Core Agent chỉ làm việc với text,
confidence, state và structured actions.

Boundary này giúp:

- test Agent hoàn toàn bằng text, offline và deterministic;
- thay STT/TTS/telephony mà không viết lại business workflow;
- thay LLM mà không thay API thực thi booking;
- ngăn LLM trực tiếp tạo side effect nguy hiểm;
- retry và idempotency được Backend kiểm soát.

---

## 3. Nguyên tắc cốt lõi

### 3.1 Agent quyết định; Backend thực thi

Agent tuyệt đối không trực tiếp:

- gọi Maps/Places API;
- gọi Route/Pricing API;
- tạo booking thật;
- đọc hoặc ghi Redis/PostgreSQL;
- chuyển cuộc gọi;
- gửi notification;
- tự tạo booking ID, giá, ETA hoặc trạng thái chuyến.

Khi cần dữ liệu hoặc side effect, Agent trả:

```json
{
  "action_type": "CALL_TOOL",
  "tool_call": {
    "tool_name": "search_place",
    "call_id": "sess_001:search_place:1",
    "params": {
      "query": "Times City"
    }
  }
}
```

Backend thực thi rồi gửi result lại:

```json
{
  "tool_name": "search_place",
  "call_id": "sess_001:search_place:1",
  "status": "SUCCESS",
  "data": {
    "candidates": []
  }
}
```

### 3.2 State là single source of truth

Agent không giữ một bản state bí mật trong process. Mọi thông tin cần để tiếp tục
hội thoại phải nằm trong `AgentState` đã validate.

```text
Turn N
AgentInput + State(v5)
        ↓
AgentAction + state_updates
        ↓
Backend validate/persist State(v6)
        ↓
Turn N+1
```

Nhờ vậy session có thể resume sau disconnect hoặc được xử lý ở instance khác.

### 3.3 Workflow quyết định business step

Router chỉ chọn hoặc tiếp tục workflow. Workflow mới quyết định:

- field nào còn thiếu;
- có cần hỏi user không;
- có cần gọi tool không;
- tool result có ý nghĩa gì;
- cần retry, hoàn thành hay handoff.

### 3.4 Business-critical rules phải deterministic

LLM có thể hỗ trợ hiểu ngôn ngữ tự nhiên, nhưng các quy tắc sau phải được kiểm
soát bằng state machine, schema và guardrail:

- không booking trước xác nhận;
- không tự chọn candidate địa điểm khi còn mơ hồ;
- không lookup khi thiếu identifier;
- không bịa giá/ETA/trip status;
- không trả FAQ ngoài retrieved context;
- không vượt retry limit;
- emergency/complaint phải được handoff theo policy.

---

## 4. Shared contracts

Contract chi tiết nằm trong `schemas.py` và `state.py`.

### `AgentInput`

```text
session_id
transcript
stt_confidence
tool_result
```

Một lượt phải có transcript hoặc tool result. `session_id` phải khớp với state.

### `AgentState`

```text
session_id
current_workflow
current_step
collected_data
pending_tool_call_id
retry_count
```

State được mở rộng theo F2 nhưng phải giữ backward compatibility hợp lý và không
được thiết kế chỉ phục vụ riêng Booking.

### `AgentAction`

Agent chỉ trả một trong năm loại:

```text
ASK_USER
RESPOND
CALL_TOOL
HANDOFF
END_SESSION
```

`CALL_TOOL` bắt buộc có `ToolCall`. Các action khác không được chứa tool call.

### `ToolCall` và `ToolResult`

```text
ToolCall:   tool_name + call_id + params
ToolResult: tool_name + call_id + status + data/error
```

`call_id` dùng để chống nhận nhầm, nhận trễ hoặc xử lý lặp kết quả tool.

---

## 5. Một lượt hội thoại được xử lý thế nào?

```text
1. Backend nhận transcript hoặc ToolResult.
2. Backend load AgentState theo session_id.
3. LLMAgent kiểm tra session isolation.
4. Router áp dụng handoff policy tổng quát.
5. Nếu đã có current_workflow, tiếp tục workflow đó.
6. Nếu chưa có workflow, classify intent.
7. Agent lấy workflow từ registry.
8. Workflow đọc input/state và quyết định bước kế tiếp.
9. Workflow trả đúng một AgentAction.
10. Backend apply state_updates, persist và thực thi action.
```

Nếu action là `CALL_TOOL`:

```text
Workflow
  ↓ build ToolCall
AgentAction(CALL_TOOL)
  ↓
Backend executes
  ↓
ToolResult
  ↓ correlate call_id/tool_name
Current Workflow
  ↓
Next AgentAction
```

Workflow gọi tool nào thì workflow đó diễn giải result. Router không diễn giải
Maps candidates, booking result, ETA hay retrieved documents.

---

## 6. Các workflow của AloSM Agent

### Ride Booking

```text
COLLECT_PICKUP
→ RESOLVE_PICKUP
→ SELECT_PICKUP_CANDIDATE (nếu ambiguous)
→ COLLECT_DESTINATION
→ RESOLVE_DESTINATION
→ SELECT_DESTINATION_CANDIDATE (nếu ambiguous)
→ COLLECT_PHONE / VEHICLE (theo contract MVP)
→ ESTIMATE_ROUTE / FARE (nếu được yêu cầu)
→ CONFIRM
→ CREATE_BOOKING
→ COMPLETE
```

Nếu user sửa pickup, destination, vehicle hoặc fare-sensitive data, confirmation
cũ phải được reset theo policy.

### Trip Lookup

```text
COLLECT_IDENTIFIER
→ LOOKUP_TRIP
→ PROCESS_RESULT
→ RESPOND / RETRY / HANDOFF
```

Identifier là booking ID hoặc phone. ETA và trip status chỉ lấy từ tool result.

### FAQ + RAG

```text
RECEIVE_QUESTION
→ RETRIEVE_KNOWLEDGE
→ VALIDATE_SCORE / SOURCE
→ GROUNDED_RESPONSE
   ├── đủ context → RESPOND
   └── thiếu context → FALLBACK / HANDOFF
```

### Human Handoff

Trigger tối thiểu:

- user yêu cầu người thật;
- complaint;
- emergency;
- retry quá giới hạn;
- critical tool error;
- STT confidence thấp theo policy;
- Agent không thể tiếp tục an toàn.

Agent chuẩn bị context có kiểm soát rồi phát `HANDOFF`; Backend và Voice mới thực
hiện chuyển case/cuộc gọi.

---

## 7. Học từ các Voice Agent framework phổ biến

### 7.1 LiveKit Agents

LiveKit tổ chức workflow bằng `AgentSession`, agents, tasks, tools và handoffs.
Agent có thể giữ quyền điều khiển session dài hạn, task biểu diễn công việc hữu
hạn, còn tool cung cấp capability. LiveKit cũng khuyến nghị tách use case phức
tạp thành component nhỏ thay vì nhồi toàn bộ logic vào một prompt.

**Học theo:**

- session lifecycle rõ ràng;
- workflow/task nhỏ, có mục tiêu và completion condition;
- specialist handoff;
- typed tool arguments;
- behavioral tests theo message/tool/handoff;
- simulation cho multi-turn scenarios;
- prompt tối ưu cho TTS: câu ngắn, tự nhiên, không đọc metadata.

**Không copy nguyên:**

LiveKit tools thường có thể gọi external service ngay trong agent runtime. AloSM
Agent chỉ tạo `ToolCall`; Backend executor mới chạy side effect.

Tham khảo:

- [LiveKit workflow concepts](https://docs.livekit.io/agents/logic/workflows/)
- [LiveKit agents and handoffs](https://docs.livekit.io/agents/logic/agents-handoffs/)
- [LiveKit restaurant agent recipe](https://docs.livekit.io/reference/recipes/restaurant-agent/)
- [LiveKit tool-loop design](https://docs.livekit.io/agents/logic/tools/design/)
- [LiveKit prompting guide](https://docs.livekit.io/agents/start/prompting/)
- [LiveKit testing and evaluation](https://docs.livekit.io/agents/start/testing/)
- [LiveKit Agents repository](https://github.com/livekit/agents)
- [LiveKit Python agent examples](https://github.com/livekit-examples/python-agents-examples)

Ví dụ `hotel_receptionist/book_restaurant.py` ban đầu của nhóm có thể được xem
tại [đường dẫn GitHub lịch sử này](https://github.com/livekit/agents/blob/main/examples/hotel_receptionist/book_restaurant.py).
LiveKit đã tái tổ chức examples; tài liệu thay thế hiện hành nên dùng
[Restaurant agent recipe](https://docs.livekit.io/reference/recipes/restaurant-agent/),
trong đó có full source, typed shared state, specialist handoffs và validation
trước transition.

### 7.2 Pipecat

Pipecat mô hình hóa realtime voice thành pipeline của các frame processors:

```text
transport input → STT → context → LLM → TTS → transport output
```

Audio, transcription, control signal và context đều đi qua pipeline dưới dạng
frames có type. Cách này đặc biệt mạnh cho streaming, interruption và quan sát
latency của từng stage.

**Học theo:**

- boundary rõ giữa transport, STT, context, reasoning và TTS;
- event/frame có type thay vì dictionary tùy ý;
- xử lý lifecycle, error và interruption như first-class events;
- correlation/ordering để tránh xử lý nhầm kết quả cũ;
- đo latency theo từng stage.

**Không copy nguyên:**

Core Agent không xử lý audio frames. Pipecat-style realtime pipeline phù hợp hơn
với Voice Gateway; Agent giữ text/state/action contract để độc lập transport.

Tham khảo:

- [Pipecat pipeline and frames](https://docs.pipecat.ai/pipecat/learn/pipeline)
- [Pipecat function calling](https://docs.pipecat.ai/pipecat/learn/function-calling)

### 7.3 Vocode

Vocode mô tả action bằng typed parameters và response, sau đó một worker/factory
thực thi action, đưa result trở lại agent để tiếp tục conversation. Pattern này
gần với AloSM nhất về vòng đời action/result.

**Học theo:**

- action request và action result có schema;
- executor tách khỏi agent reasoning;
- execution có queue/worker boundary;
- result được đưa lại làm context cho lượt sau;
- cấu hình được việc agent có cần nói trước/sau action hay không.

**Điểm AloSM siết chặt hơn:**

Vocode action worker có thể nằm trong cùng voice-agent system; AloSM đặt executor
ở Backend để quản lý validation, credentials, persistence và idempotency.

Tham khảo:

- [Vocode agents with actions](https://docs.vocode.dev/open-source/agents-with-actions)

### 7.4 OpenAI Agents SDK

OpenAI Agents SDK dùng các primitive nhỏ: agent, tools, handoffs, guardrails,
sessions và structured output. SDK hỗ trợ cả manager-style orchestration và
handoff sang specialist. Voice pipeline tách STT → workflow → TTS.

**Học theo:**

- typed structured output;
- input/output/tool guardrails;
- manager/orchestrator giữ quyền điều khiển khi cần policy chung;
- specialist workflow có instructions hẹp;
- session/memory rõ ràng;
- giới hạn turn/tool loop;
- tracing và evaluation.

**Không copy nguyên:**

SDK runner có thể tự chạy tool loop. AloSM dừng sau `AgentAction` để Backend thực
thi, rồi tiếp tục ở request kế tiếp khi có `ToolResult`.

Tham khảo:

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [Voice pipeline](https://openai.github.io/openai-agents-python/voice/pipeline/)
- [Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
- [Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [Guardrails](https://openai.github.io/openai-agents-python/guardrails/)

---

## 8. Kiến trúc AloSM chọn lọc từ các pattern trên

| Nhu cầu | Pattern học được | Cách AloSM áp dụng |
|---|---|---|
| Realtime voice | Pipecat/LiveKit pipeline | Voice Gateway sở hữu audio/STT/TTS |
| Session workflow | LiveKit AgentSession | Backend + `AgentState` duy trì session |
| Specialized flow | LiveKit tasks/handoffs | Router + `BaseWorkflow` implementations |
| Tool schema | LiveKit/OpenAI/Vocode | `ToolCall`, typed params, `ToolResult` |
| Safe side effects | Vocode action worker | Backend Tool Executor, ngoài Agent |
| Structured output | OpenAI Agents SDK | Pydantic `AgentAction` validation |
| Human escalation | LiveKit/OpenAI handoff | Handoff workflow + Backend/Voice execution |
| Streaming/interruption | Pipecat frames | Voice layer; Agent nhận final transcript turn |
| Behavioral testing | LiveKit/OpenAI evals | Offline pytest + scenario/eval suite |

Kết quả là một kiến trúc **hybrid deterministic agent**:

```text
LLM/NLU flexibility
        +
Typed contracts
        +
Deterministic state machine
        +
Backend-controlled side effects
```

---

## 9. Voice-specific design rules

Voice Agent không giống chatbot thuần text. Implementation phải chú ý:

### Response ngắn và dễ nghe

- mỗi turn chỉ hỏi một hoặc hai thông tin liên quan;
- tránh đọc JSON, ID kỹ thuật, URL hoặc source metadata;
- đọc lại địa chỉ/giá trước confirmation bằng câu tự nhiên;
- không đưa `reason` hoặc internal state vào `message`;
- tránh câu quá dài khiến user khó ngắt lời.

### STT không hoàn hảo

- sử dụng `stt_confidence` theo policy;
- xác nhận dữ liệu critical như địa chỉ và phone;
- không coi transcript confidence thấp là sự thật đã xác nhận;
- sau nhiều lần không hiểu phải handoff, không lặp vô hạn.

### Interruption và duplicate turn

- `call_id` phải unique/correlatable;
- Backend chịu idempotency cho booking;
- workflow không được phát lại side effect khi đã có successful result;
- result không khớp pending tool phải bị reject hoặc xử lý theo policy;
- confirmation state phải rõ để user interruption không tạo booking ngoài ý muốn.

### Latency

- router và deterministic transition không cần gọi LLM khi state đã rõ;
- chỉ retrieve/call model khi cần;
- message trả TTS nên được tạo nhanh và ngắn;
- đo riêng STT, Agent, tool và TTS latency;
- không đưa background analytics vào realtime path.

---

## 10. Guardrails bắt buộc

| Rủi ro | Guardrail |
|---|---|
| Booking ngoài ý muốn | Confirmation state + idempotency key |
| Sai địa điểm | Candidate resolution + explicit user selection |
| Giá/ETA giả | Chỉ dùng ToolResult |
| FAQ hallucination | Retrieval threshold + source metadata |
| Tool result sai turn | `pending_tool_call_id` correlation |
| Lẫn dữ liệu khách | Session ID validation/isolation |
| Loop vô hạn | Retry/turn/tool-call limits |
| Emergency bị giữ ở bot | Deterministic handoff policy |
| Prompt injection | Structured contracts + business-rule enforcement |

Prompt là một lớp guardrail, không phải lớp duy nhất. Validation, state machine,
Backend policy và tests mới bảo đảm business-critical behavior.

---

## 11. Testing strategy

### Contract tests

- invalid input/state/action bị reject;
- action/tool payload đúng schema;
- session isolation;
- state update được validate.

### Workflow tests

- happy path;
- missing fields;
- ambiguous data;
- user correction/rejection;
- tool success/not-found/error;
- retry/handoff;
- duplicate or mismatched tool result.

### Behavioral scenarios

Các scenario MVP tối thiểu:

```text
1. Happy-path booking
2. Missing pickup/destination
3. Ambiguous pickup/destination
4. User changes confirmed information
5. User rejects fare
6. Tool timeout/error
7. Trip lookup by booking ID/phone
8. FAQ with and without grounded source
9. User asks for human
10. Emergency/complaint
11. Low STT confidence
12. Session resume/end
```

Ưu tiên text-mode tests vì nhanh, rẻ và deterministic. Full audio pipeline tests
thuộc integration giữa Voice, Backend và Agent.

---

## 12. Feature roadmap

Trạng thái Core Agent hiện tại:

- F1–F8: implemented.
- Conversation history/context/rewrite: implemented.
- Conversation repair và workflow interruption: implemented.
- Booking/Trip/FAQ production hardening phía Core: implemented.
- Offline readiness evaluation: implemented.

Các integration còn lại thuộc Backend/Voice:

```text
external tool executors
→ production persistence/knowledge ingestion
→ Voice Runtime/STT/TTS/telephony
→ Backend/Voice integration and audio E2E
```

Chi tiết trạng thái và acceptance boundary nằm tại `CORE_AGENT_STATUS.md`.

---

## 13. Definition of Done cho Core Agent

Core Agent sẵn sàng tích hợp khi:

- mọi input/output validate qua shared contracts;
- active workflow luôn được tiếp tục đúng;
- tool result được correlate và route đúng workflow;
- booking không thể xảy ra trước confirmation;
- trip/price/ETA chỉ lấy từ tool result;
- FAQ chỉ trả lời từ context đủ tin cậy;
- handoff context an toàn và đủ dùng;
- không có external API execution trong `src/agents/`;
- test offline/deterministic pass;
- lint, compile và contract checks pass;
- Backend và Voice có thể tích hợp chỉ dựa trên documented contract.

---

## 14. Tài liệu tham khảo

Các link dưới đây là tài liệu chính thức được dùng khi nghiên cứu. Link được rà
soát ngày **2026-08-11**. API/framework có thể thay đổi, vì vậy khi implement cần
ưu tiên documentation hiện hành hơn source example cũ.

### LiveKit Agents

- [LiveKit Agents documentation](https://docs.livekit.io/agents/)
- [Workflows: agents, tasks and tools](https://docs.livekit.io/agents/logic/workflows/)
- [Agents and handoffs](https://docs.livekit.io/agents/logic/agents-handoffs/)
- [Tool definition and loop design](https://docs.livekit.io/agents/logic/tools/design/)
- [Pipeline nodes and lifecycle hooks](https://docs.livekit.io/agents/logic/nodes/)
- [Voice-agent prompting guide](https://docs.livekit.io/agents/start/prompting/)
- [Testing and evaluation](https://docs.livekit.io/agents/start/testing/)
- [Restaurant agent recipe](https://docs.livekit.io/reference/recipes/restaurant-agent/)
- [LiveKit Agents source repository](https://github.com/livekit/agents)
- [Runnable Python examples](https://github.com/livekit-examples/python-agents-examples)
- [Original hotel receptionist example](https://github.com/livekit/agents/blob/main/examples/hotel_receptionist/book_restaurant.py)

### Pipecat

- [Pipecat overview](https://docs.pipecat.ai/pipecat/learn/overview)
- [Pipeline and frame processing](https://docs.pipecat.ai/pipecat/learn/pipeline)
- [Frames reference](https://docs.pipecat.ai/api-reference/server/frames/overview)
- [System frames and lifecycle events](https://docs.pipecat.ai/api-reference/server/frames/system-frames)
- [Function calling](https://docs.pipecat.ai/pipecat/learn/function-calling)
- [Pipecat source repository](https://github.com/pipecat-ai/pipecat)

### Vocode

- [Vocode documentation](https://docs.vocode.dev/)
- [Adding actions to agents](https://docs.vocode.dev/open-source/agents-with-actions)
- [Vocode source repository](https://github.com/vocodedev/vocode-core)

### OpenAI Agents SDK

- [OpenAI Agents SDK documentation](https://openai.github.io/openai-agents-python/)
- [Agent definitions and structured output](https://openai.github.io/openai-agents-python/agents/)
- [Running agents and the agent loop](https://openai.github.io/openai-agents-python/running_agents/)
- [Agent orchestration patterns](https://openai.github.io/openai-agents-python/multi_agent/)
- [Tools](https://openai.github.io/openai-agents-python/tools/)
- [Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [Guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [Voice pipeline](https://openai.github.io/openai-agents-python/voice/pipeline/)
- [OpenAI Agents SDK source repository](https://github.com/openai/openai-agents-python)
