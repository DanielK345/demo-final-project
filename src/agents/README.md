# Core Agent

Core Agent nhận transcript/state, quyết định câu trả lời hoặc yêu cầu Backend
thực hiện tool. Nó không sở hữu Voice runtime, HTTP client, database hay side
effect.

## Runtime

```text
Voice ── transcript ─► Backend ── AgentInput + AgentState ─► LLMAgent
                                                               │
                                            instructions + typed state + tools
                                                               │
                                            ┌──────────────────┴─────────────┐
                                            ▼                                ▼
                                      reply/ask                    semantic tool
                                                                             │
                                                               deterministic policy
                                                                             │
                                                                         AgentAction
                                                                             │
Backend ◄──────────────────────────── ToolCall / state_updates ───────────────┘
   │
   └── execute API/DB ──► ToolResult ──► Core Agent
```

Ba nguyên tắc:

1. LLM điều khiển hội thoại và chọn semantic tool.
2. `AgentState` cùng typed business data là nguồn facts duy nhất.
3. Policy và guardrail deterministic bảo vệ validation, confirmation và side
   effect.

## Cấu trúc

```text
src/agents/
├── agent.py              # public entrypoint; production path dễ đọc
├── turn_adapter.py       # stateless adapter cho Backend API hiện có
├── contracts/
│   ├── schemas.py        # AgentInput, AgentAction, ToolCall, ToolResult
│   ├── state.py          # AgentState và conversation message contracts
│   ├── state_types.py    # enum/value objects của state
│   └── store.py          # state-store protocol/optimistic concurrency
├── core/
│   ├── agent.py          # model/tool loop duy nhất (~100 dòng)
│   ├── registry.py       # đăng ký semantic tool/result reducer
│   ├── session.py        # typed working state cho một turn
│   ├── instructions.py   # service-agent instructions
│   ├── model.py          # model port + OpenAI adapter
│   ├── tools.py          # semantic tools dành cho LLM
│   ├── guardrails.py     # invariant cuối trước khi trả action
│   ├── history.py        # conversation history reducer
│   ├── policy.py         # retry/deadline/budget dùng chung
│   ├── turn_policy.py    # confidence/pending/replay checks trước LLM
│   ├── booking_types.py
│   ├── phone_policy.py
│   └── booking/          # typed booking state/messages/action builders
├── capabilities/         # từng năng lực độc lập, không có router/FSM chung
│   ├── booking.py        # booking policy + backend-result reducers
│   ├── trip_lookup.py    # typed lookup và multi-match selection
│   ├── faq.py            # grounded retrieval/freshness/citations
│   ├── common.py         # respond và handoff context
│   └── registry.py       # composition root của capability
├── tools/                # external tool contracts, không thực thi I/O
│   ├── builders.py       # toàn bộ typed ToolCall builders
│   ├── schemas.py        # tool params/results
│   ├── lifecycle.py      # correlation/pending/result parsing
│   └── call_id.py        # deterministic call identity
├── rag/                  # knowledge interfaces dùng chung với backend
├── eval/                 # conversation evaluation datasets/runners
├── legacy/               # router/FSM/NLU/repair cũ, lazy-loaded cho tests
└── docs/                 # architecture và integration contracts
```

`nodes/`, placeholder `prompts/`, fake FAQ tool và các tool-builder file một lớp
đã bị xóa. Prompt thật nằm cạnh agent trong `core/instructions.py`; mọi builder
nằm trong `tools/builders.py`.

## Contract với Backend

```python
action = await LLMAgent().handle(agent_input, state)
```

Action hợp lệ:

- `ASK_USER`: hỏi thêm thông tin.
- `RESPOND`: trả lời không cần external work.
- `CALL_TOOL`: Backend phải thực thi `tool_call` rồi gửi `ToolResult` trở lại.
- `HANDOFF`: chuyển người thật.
- `END_SESSION`: kết thúc phiên.

Backend phải apply `state_updates`, persist state và execute tool. Agent chỉ tạo
tool description; không được import Backend service hoặc gọi API trực tiếp.

Chi tiết payload/correlation/idempotency nằm tại
[`docs/BACKEND_INTEGRATION.md`](docs/BACKEND_INTEGRATION.md).

## Booking safety

- Không dùng lời chào hoặc câu ngoài phạm vi làm địa chỉ.
- Location có typed resolution status; chỉ candidate do Backend/place provider
  trả về mới được coi là `RESOLVED`.
- Không tự tạo `place_id`, vehicle option, fare, ETA hoặc booking ID.
- Khi khách sửa location/vehicle/needs, fare và lựa chọn phụ thuộc phải bị reset.
- `create_booking` chỉ được policy tạo sau bản tóm tắt đang chờ xác nhận.
- `cancel_booking` có một bước xác nhận riêng.
- External tool params được dựng từ typed state, không copy trực tiếp từ output
  tự do của model.
- Guardrail đối chiếu side-effect params với state lần cuối.
- Booking draft chỉ bị xóa sau explicit confirmation; lời nói mơ hồ có thể được
  đính chính mà không mất memory.
- Lỗi conversation model tạm thời giữ nguyên state và cho phép thử lại; chỉ
  handoff sau khi lỗi lặp đến ngưỡng policy.

## Configuration

Runtime model-driven:

```env
AGENT_LLM_ENABLED=true
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
AGENT_LLM_MODEL=openai/gpt-5.6-luna-pro
AGENT_LLM_BASE_URL=https://openrouter.ai/api/v1
```

`AGENT_LLM_ENABLED=false` hiện kích hoạt `legacy/agent.py` cho regression tests. Đây là
compatibility seam tạm thời, không phải kiến trúc đích.

## Test

```bash
.venv/bin/pytest -q tests/test_agents
.venv/bin/pytest -q tests/test_backend/test_session_agent_integration.py
.venv/bin/ruff check src/agents tests/test_agents
```

Conversation tests của runtime mới nằm trong
`tests/test_agents/test_model_driven_booking.py` và dùng fake model: không cần API
key, nhưng vẫn kiểm tra booking, lookup, FAQ, handoff và vòng
`AgentAction -> ToolResult -> model response`.

## Tài liệu còn hiệu lực

- [`docs/MODEL_DRIVEN_AGENT.md`](docs/MODEL_DRIVEN_AGENT.md)
- [`docs/BACKEND_INTEGRATION.md`](docs/BACKEND_INTEGRATION.md)
- [`docs/VOICE_AGENT_DESIGN.md`](docs/VOICE_AGENT_DESIGN.md)
- [`docs/CORE_AGENT_STATUS.md`](docs/CORE_AGENT_STATUS.md)
- [`docs/INTEGRATION_CONTRACT_HARDENING.md`](docs/INTEGRATION_CONTRACT_HARDENING.md)
