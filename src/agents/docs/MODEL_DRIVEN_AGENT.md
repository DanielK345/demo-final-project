# Model-driven Core Agent

## Kiến trúc đang chạy

```text
Voice runtime                Core Agent                         Backend
STT/VAD/TTS  ── transcript ─► LLM instructions + tools
                             │
                             ├─ update_booking ─► typed BookingData
                             ├─ respond/ask ─────► AgentAction
                             └─ external intent
                                      │
                                      ▼
                              deterministic policy
                              builds validated ToolCall ───────► executor/API/DB
                                                    ◄────────── ToolResult
```

Đây là pattern giống các agent dịch vụ/tool-calling hiện đại: model điều khiển
hội thoại, state typed giữ facts, còn code deterministic bảo vệ nghiệp vụ và side
effect. Core Agent không chứa STT/TTS/WebRTC, không gọi database/API và không tạo
booking trực tiếp.

## Các file cần đọc

- `agent.py`: façade giữ contract `AgentInput + AgentState -> AgentAction`.
- `core/instructions.py`: hành vi của nhân viên đặt xe.
- `core/tools.py`: toàn bộ khả năng model được phép chọn.
- `core/agent.py`: model/tool loop provider-independent, không chứa business dispatch.
- `core/registry.py`, `capabilities/registry.py`: composition bằng tool registry.
- `capabilities/booking.py`: validation/confirmation và booking reducers.
- `capabilities/trip_lookup.py`: lookup state và multi-match selection.
- `capabilities/faq.py`: retrieval grounding, freshness và citations.
- `capabilities/common.py`: typed response và handoff context.
- `core/turn_policy.py`: low-confidence repair, pending-call protection và
  idempotent side-effect replay trước khi gọi model.
- `core/model.py`: port để test bằng fake model và adapter OpenAI thật.
- `contracts/schemas.py`, `contracts/state.py`: contract dùng chung với backend.
- `core/guardrails.py`: lớp bảo vệ cuối trước khi trả action.

## Quyền quyết định

LLM được quyền hiểu lời nói theo ngữ cảnh, nhận thay đổi ở bất kỳ bước nào, chọn
semantic tool và viết câu trả lời ngắn tự nhiên. LLM không được tự tạo place ID,
vehicle option, fare, booking status hoặc params side effect.

Policy chỉ nhận semantic intent rồi dựng tool call từ typed state. Ví dụ model
chọn `confirm_booking`, nhưng policy chỉ tạo `create_booking` khi trước đó đã có
bản tóm tắt chờ xác nhận và state có địa điểm đã resolve, xe, fare và số liên hệ.
Guardrail tiếp tục đối chiếu tool params với state lần cuối.

Model không nhận toàn bộ tool catalog ở mọi lượt. Mỗi `RegisteredTool.available`
chỉ expose semantic tool hợp lệ từ typed state hiện tại. Ví dụ
`confirm_booking` không tồn tại trước khi có confirmation summary đang chờ.

## Baseline F1–F8

Đã có trên production model-driven path:

1. F1: model-driven intent/tool routing.
2. F2: typed `AgentState`, `TurnSession`, booking/trip/FAQ state và history.
3. F3: resolve → option/fare → explicit confirmation → create/cancel booking.
4. F4: trip lookup, not-found, single và multi-match selection.
5. F5: handoff kèm reason/source workflow/safe history summary.
6. F6: typed ToolCall/ToolResult, correlation, idempotency và reducers.
7. F7: knowledge retrieval, score/freshness filtering và citations.
8. F8: pre-turn policy, final guardrails và offline conversation evals.

Core Agent không dùng LangGraph cho model/tool loop. Backend adapter gọi trực
tiếp `LLMAgent`; Voice runtime có thể dùng LiveKit/Pipecat độc lập mà không kéo
STT/TTS/WebRTC vào Core Agent.

Phần phát triển sau baseline: production tracing không log PII, provider eval ở
CI release, và xóa `legacy/` khi toàn bộ old regression fixtures đã chuyển sang
scripted-model conversation evals.

## Migration

Khi `AGENT_LLM_ENABLED=true`, `LLMAgent()` dùng model-driven core. Legacy router,
understanding và workflows hiện còn được giữ làm compatibility path khi LLM bị
tắt hoặc test chủ động inject dependency cũ. Chúng không phải kiến trúc đích và
sẽ được xóa sau khi conversation evals bao phủ booking, lookup, FAQ, handoff và
failure/reconciliation ở mức tương đương.
