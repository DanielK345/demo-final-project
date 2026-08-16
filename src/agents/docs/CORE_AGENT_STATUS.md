# Core Agent Status

Tài liệu này là nguồn trạng thái hiện hành cho phạm vi `src/agents`. README mô tả
contracts và cách phát triển; các implementation/completion plan lưu thiết kế và
lịch sử triển khai.

## Scope đã hoàn tất

| Phần | Trạng thái | Bằng chứng chính |
|---|---|---|
| F1 Core & Routing | Implemented | model/tool loop + capability registry |
| F2 State & Memory | Implemented | AgentState + typed TurnSession/history |
| F3 Ride Booking | Implemented | booking capability, confirmation, correction, cancellation |
| F4 Trip Lookup | Implemented | typed lookup state + single/multi-match reducer |
| F5 Human Handoff | Implemented | deterministic safety policy, typed reason/priority/severity/queue, redacted context |
| F6 Tool Lifecycle | Implemented | typed params/results, correlation, deadline và idempotency contracts |
| F7 FAQ + grounded RAG | Implemented | score/freshness filter, citation và grounding tests |
| F8 Guardrails & Eval | Implemented | cross-cutting guardrails, scripted-model conversation evals |
| Conversation repair/interruption | Implemented | repeat/correct/cancel/pause/resume/FAQ interruption tests |
| Natural-language understanding | Implemented | conversation model chọn structured semantic tools |

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
2. Scripted-model conversation suite đạt zero configured safety violations;
   provider/release eval được chạy riêng trong môi trường release.
3. Shared contracts trong README và Backend integration contract đồng bộ code.
4. Real-provider smoke tests vẫn là opt-in; phải chạy trong release environment
   khi phát hành cấu hình model production.

Current verification ngày 2026-08-16: toàn bộ Agent/Backend/API/Voice scope `281 passed, 2 skipped`; frontend lint và production build đều pass. Một skip là fixture audio thật chưa được cấp; live Transcript Rewriter hiện fail đúng với `AuthenticationError` và được theo dõi trong `mustdo.md`.
Real-provider tests vẫn opt-in và yêu cầu key tương ứng.

## Ngoài phạm vi Core Agent

- Maps/Booking/Trip/Handoff executors và network retry thực tế;
- PostgreSQL/Redis persistence, authentication, encryption, retention;
- production knowledge ingestion/vector store;
- production-grade persistent handoff executor/operator routing beyond the current authenticated API;
- STT/TTS, WebRTC/WebSocket, acoustic barge-in và telephony transfer;
- frontend call UI, audio E2E và production observability infrastructure.

Các phần này phải tuân thủ `BACKEND_INTEGRATION.md`; chúng không được giả lập như
production implementation bên trong `src/agents`.
