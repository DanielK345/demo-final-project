# Core Agent Status

Tài liệu này là nguồn trạng thái hiện hành cho phạm vi `src/agents`. README mô tả
contracts và cách phát triển; các implementation/completion plan lưu thiết kế và
lịch sử triển khai.

## Scope đã hoàn tất

| Phần | Trạng thái | Bằng chứng chính |
|---|---|---|
| F1 Core & Routing | Implemented | routing, graph và orchestration tests |
| F2 State & Memory | Implemented | typed state/history, optimistic version và isolation tests |
| F3 Ride Booking | Implemented | confirmation, correction, retry, cancellation và reconciliation tests |
| F4 Trip Lookup | Implemented | contextual lookup, multi-match và stale/replay tests |
| F5 Human Handoff | Implemented | reason/context redaction và safety tests |
| F6 Tool Lifecycle | Implemented | typed params/results, correlation, deadline và idempotency contracts |
| F7 FAQ + grounded RAG | Implemented | freshness, injection, citation và grounding tests |
| F8 Guardrails & Eval | Implemented | cross-cutting guardrails và readiness-v1 |
| Conversation repair/interruption | Implemented | repeat/correct/cancel/pause/resume/FAQ interruption tests |
| Structured understanding/rewrite | Implemented, opt-in provider | deterministic fallback và fake-provider tests |

## Core invariants đã chốt

- Core Agent không thực thi external API hoặc side effect.
- Correlated tool result có ưu tiên hơn transcript/repair command cùng invocation.
- Pending side effect chỉ được clear bởi result khớp `call_id` và `tool_name`;
  unknown outcome đi reconciliation.
- Unknown top-level state/update fields bị reject.
- Customer-facing action luôn có message; `CALL_TOOL` dừng sau structured call.
- Booking/cancellation cần explicit confirmation và stable idempotency key.
- Trip status, ETA, fare và FAQ facts chỉ đến từ validated tool result.
- Readiness không thể pass khi expected workflow chưa complete, tool arguments
  dưới threshold hoặc có safety violation.

## Definition of Done cho Core Agent

Core Agent được coi là done khi:

1. Full offline pytest, Ruff, compileall và `git diff --check` pass.
2. `readiness-v1` trả `ready=true` với zero configured safety violations.
3. Shared contracts trong README và Backend integration contract đồng bộ code.
4. Real-provider tests vẫn là opt-in; phải chạy trong release environment nếu
   release bật OpenAI understanding/rewrite.

Current verification: `342 passed, 5 skipped`; 5 skipped là real OpenAI tests
yêu cầu `RUN_OPENAI_INTEGRATION=1`.

## Ngoài phạm vi Core Agent

- Maps/Booking/Trip/Handoff executors và network retry thực tế;
- PostgreSQL/Redis persistence, authentication, encryption, retention;
- production knowledge ingestion/vector store;
- FastAPI integration endpoints;
- STT/TTS, WebRTC/WebSocket, acoustic barge-in và telephony transfer;
- frontend call UI, audio E2E và production observability infrastructure.

Các phần này phải tuân thủ `BACKEND_INTEGRATION.md`; chúng không được giả lập như
production implementation bên trong `src/agents`.
