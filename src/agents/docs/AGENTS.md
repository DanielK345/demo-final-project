# AGENTS.md — Coding Principles for Agentic AI Track

> **CURRENT INSTRUCTION** — Quy tắc làm việc trong `src/agents/docs/`. Product scope nằm tại
> `docs/PRD_AloSM_Voice.md`; runtime truth nằm tại `docs/PROJECT_SOURCE_OF_TRUTH.md` và
> `src/agents/README.md`. Không dùng brief, stack hoặc kế hoạch lịch sử để suy ra implementation.
## 1. Vai trò của coding agent

Bạn đang hỗ trợ phát triển **Agentic AI / LLM Agent** cho hệ thống Voice AI Ride-Hailing.

Mục tiêu:
- hiểu codebase hiện tại trước khi sửa;
- phát triển đúng feature được giao;
- giữ đúng architecture và shared contracts;
- viết code đơn giản, test được, phù hợp MVP;
- không tự redesign hệ thống nếu không có lý do rõ ràng.

**Trước khi code trong track Agentic AI, luôn đọc `src/agents/README.md` trước.**  
Đây là technical source of truth của track.

---

## 2. Architecture bắt buộc phải giữ

Luồng production bắt buộc:

```text
Voice/STT
   ↓ transcript + confidence
Backend
   ↓ AgentInput + AgentState
LLMAgent
   ↓ instructions + typed state + semantic tools
ModelDrivenAgent
   ↓
Deterministic policy / guardrails
   ↓
AgentAction
   ↓
Backend
   ↓
TTS / API / Handoff
```

Nếu Agent phát `CALL_TOOL`:

```text
Agent
→ AgentAction(CALL_TOOL)
→ Backend gọi API/tool thật
→ ToolResult
→ Agent
→ typed result reducer
→ action tiếp theo
```

### Boundary quan trọng

**Agent không trực tiếp gọi external API và không tạo side effect.**

Agent chỉ quyết định bước tiếp theo và trả structured `AgentAction`.

Backend mới thực thi:
- Maps API;
- Booking API;
- Trip API;
- Knowledge service;
- Human handoff;
- TTS và các side effect khác.

Không đưa HTTP/API execution thật vào `src/agents/` nếu architecture hiện tại không yêu cầu rõ ràng.

---

## 3. Các Action hợp lệ

Agent chỉ được trả một trong các action đã định nghĩa trong shared contract:

- `ASK_USER`
- `RESPOND`
- `CALL_TOOL`
- `HANDOFF`
- `END_SESSION`

Quy tắc:
- `CALL_TOOL` phải có `tool_call`.
- Action khác không được chứa `tool_call`.
- Text nói với khách nằm trong `message`.
- `reason` chỉ dùng cho debug/evaluation.
- `state_updates` là partial update, không phải toàn bộ state.
- Không tự tạo output format mới nếu shared contract hiện tại đã đáp ứng.

---

## 4. State là single source of truth

`AgentState` là nguồn trạng thái duy nhất của conversation.

Không:
- tạo state riêng trong workflow;
- giữ một bản copy khác với shared state;
- dùng state của session khác;
- update state bằng cấu trúc không validate nếu codebase đã có reducer/apply mechanism.

Workflow phải dựa vào state chung, ví dụ:
- `current_workflow`;
- `current_step`;
- dữ liệu đã thu thập;
- confirmation;
- retry/confidence;
- pending tool call;
- conversation history theo contract hiện tại.

Nếu cần thêm field mới:
1. kiểm tra field hiện tại có đáp ứng chưa;
2. nếu chưa, giải thích use case;
3. đánh giá ảnh hưởng tới feature khác và Backend;
4. xin review trước khi sửa shared contract;
5. cập nhật tests và documentation.

---

## 5. Phân chia trách nhiệm

### Model / Orchestrator

Model-driven orchestrator trả lời:

> Người dùng muốn gì, cần trả lời hay chọn semantic tool nào tiếp theo?

Orchestrator được phép:
- hiểu intent/slot/correction theo toàn bộ typed context;
- trả lời smalltalk ngắn gọn;
- chọn semantic tool;
- route correlated `ToolResult` về reducer tương ứng.

Orchestrator **không** được:
- tự tạo business facts hoặc external tool result;
- tự truyền place ID/fare/booking ID không có trong state;
- vượt qua confirmation/policy để tạo side effect;
- thực thi HTTP, database, Voice hoặc Backend service.

### Typed state / deterministic policy

Policy trả lời:

> Semantic action model chọn có hợp lệ với state hiện tại không, và ToolCall cụ
> thể phải được dựng thế nào?

Policy chịu trách nhiệm validation, dependent-field invalidation, explicit
confirmation, correlation/idempotency, typed result reduction và dựng external
tool params từ state. Không parse lại câu người dùng bằng regex/FSM.

`legacy/` chứa router/FSM/NLU/repair cũ cho regression migration; không thêm
feature production mới vào đó.

### Tool layer

Tool layer trả lời:

> Yêu cầu Backend thực hiện hành động này bằng `ToolCall` nào?

Tool layer chịu trách nhiệm:
- params schema;
- validation;
- `call_id`;
- `ToolCall`;
- `ToolResult` contract;
- error normalization/correlation.

Tool layer **không** quyết định business step tiếp theo.

---

## 6. Business rules quan trọng

### Ride Booking
- Không tạo booking khi chưa có confirmation rõ ràng.
- Không tự chọn địa điểm khi có nhiều candidate tương đương.
- Không tự tạo booking ID.
- Không tự bịa giá hoặc ETA.
- Không gọi Maps/Booking API trực tiếp trong workflow.
- Nếu user sửa dữ liệu quan trọng, phải xem xét/reset confirmation theo workflow policy.

### Trip Lookup
- Không gọi lookup tool nếu thiếu cả booking ID và phone.
- Không suy đoán ETA hoặc trip status.
- Chỉ dùng dữ liệu tool trả về.

### FAQ / RAG
- Chỉ trả lời dựa trên retrieved context đủ tin cậy.
- Không thêm thông tin ngoài source.
- Không tạo citation/source giả.
- Không có nguồn phù hợp thì fallback/handoff theo policy.

### Human Handoff
Trigger tối thiểu:
- user yêu cầu người thật;
- complaint;
- emergency;
- retry vượt giới hạn;
- critical tool error;
- low confidence theo policy.

Agent chỉ chuẩn bị context và phát action; không tự thực hiện chuyển cuộc gọi.

Feedback/rating kém không cần realtime có thể thuộc ticket/review flow sau; không nhầm với handoff realtime.

---

## 7. Feature ownership nội bộ Agent

Các mã F1–F8 dưới đây là tên workstream kỹ thuật cũ của riêng `src/agents`, không phải mã
feature F1–F9 trong PRD sản phẩm v1.2. Khi viết tài liệu mới, ưu tiên tên miền chức năng để
tránh nhầm hai taxonomy.

Implementation hiện được chia thành:

- **F1 — Agent Core & Intent Routing**
- **F2 — Conversation State & Memory**
- **F3 — Ride Booking Workflow**
- **F4 — Trip Lookup Workflow**
- **F5 — Human Handoff Workflow**
- **F6 — Tool Calling & Integration**
- **F7 — FAQ + Agentic RAG**
- **F8 — Prompt, Guardrails & Evaluation**

Khi được giao feature:
- chỉ sửa đúng scope cần thiết;
- ưu tiên source chính của feature;
- không làm thay feature khác;
- nếu cần sửa shared file thì phải giải thích impact trước.

---

## 8. Shared files cần thận trọng

Các file sau ảnh hưởng nhiều feature:

```text
src/agents/contracts/schemas.py
src/agents/contracts/state.py
src/agents/agent.py
src/agents/core/agent.py
src/agents/tools/schemas.py
```

Không tự ý:
- đổi tên field;
- đổi semantics;
- tạo enum/model duplicate;
- phá compatibility của feature khác.

Nếu phải sửa:
- nêu rõ lý do;
- liệt kê ảnh hưởng;
- update README/spec;
- update contract tests;
- giữ backward compatibility nếu hợp lý.

---

## 9. Cách làm việc khi nhận một task

Trước khi sửa code:

1. Đọc `src/agents/README.md`.
2. Inspect các file liên quan.
3. Inspect tests hiện có.
4. Tóm tắt current behavior.
5. Xác định gap so với feature specification.
6. Đưa implementation plan ngắn.
7. Sau đó mới sửa code.

Trong khi code:
- ưu tiên thay đổi nhỏ, rõ ràng;
- reuse shared contracts;
- không thêm abstraction/framework nếu chưa cần;
- không over-engineer;
- giữ code dễ review;
- giữ test offline và deterministic.

Sau khi code:
- thêm/điều chỉnh tests;
- chạy full test suite;
- chạy lint/compile checks;
- tóm tắt file đã sửa và behavior thay đổi.

---

## 10. Testing rules

Mỗi feature phải có:
- happy-path test;
- error/edge-case tests quan trọng;
- regression tests nếu sửa bug.

Tests của Agent phải:
- chạy offline;
- deterministic;
- không gọi OpenAI thật;
- không gọi Maps thật;
- không gọi Booking/Trip API thật;
- không phụ thuộc vector service production.

Trước PR, chạy:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m compileall -q src tests
git diff --check
```

Không coi task hoàn thành nếu làm hỏng test baseline mà chưa giải thích và cập nhật đúng specification.

---

## 11. Git / PR discipline

- Dùng branch/target được task hoặc repository hiện hành chỉ định; không hard-code branch lịch sử.
- PR chỉ chứa scope cần thiết, mô tả behavior/state transition và có test phù hợp.
- Không trộn refactor không liên quan hoặc thay shared contract mà không nêu impact.
- Không tự commit, push, mở PR hoặc đổi branch nếu người dùng/lead chưa yêu cầu.
---

## 12. Nguyên tắc khi hỗ trợ lead

Lead của Agentic AI cần dễ review và kiểm soát integration.

Vì vậy:
- nêu rõ assumption;
- chỉ ra nếu thay đổi chạm shared contract;
- không tự quyết định thay architecture;
- nếu có nhiều cách, ưu tiên cách ít ảnh hưởng nhất;
- báo rõ dependency với feature khác;
- không âm thầm sửa code ngoài scope;
- không tạo side effect thật để “cho chạy được”.

Nếu task chưa rõ:
- inspect code và README trước;
- dùng architecture hiện tại làm mặc định;
- chỉ hỏi lại khi codebase/spec không đủ để quyết định an toàn.

---

## 13. MVP mindset

Project đang ở giai đoạn **MVP integration sau khi hoàn thành phạm vi Core Agent F1–F8**.

Không cần xây lại skeleton hoặc redesign toàn hệ thống.

Ưu tiên:
1. core Agent chạy đúng;
2. workflow rõ ràng;
3. state nhất quán;
4. structured Action đúng;
5. tool lifecycle đúng;
6. RAG grounded;
7. guardrails/test đủ tốt;
8. integration ổn.

Tránh:
- abstraction quá sớm;
- framework mới không cần thiết;
- production-scale complexity khi MVP chưa cần;
- làm phần UI/Backend/Voice nếu task chỉ thuộc Agentic AI.

---

## 14. Trạng thái hiện tại

Core Agent F1–F8 đã implemented bằng model/tool loop, typed tool lifecycle,
conversation history, grounded FAQ, deterministic policy/guardrails và offline
readiness evaluation. Router/FSM/NLU/repair cũ chỉ còn trong `legacy/`.

Current verification ngày 2026-08-16:
- full suite: `325 passed, 5 skipped`;
- Ruff và Python compile pass;
- frontend lint, typecheck và production build pass;
- scripted-model conversation safety regressions đạt các configured gates.

External executors, production persistence/knowledge ingestion và Voice Runtime
không nằm trong `src/agents`. Dùng `CORE_AGENT_STATUS.md` làm trạng thái/DoD hiện
hành; quyết định hoặc kế hoạch đã thay thế chỉ được truy vết qua Git history.

---

## 15. Quy tắc cuối cùng

Khi có xung đột giữa:
1. task prompt,
2. code hiện tại,
3. `src/agents/README.md`,
4. file này,

hãy ưu tiên:
- requirement cụ thể đã được lead xác nhận;
- shared contracts và architecture trong `src/agents/README.md`;
- code/test hiện tại làm baseline kỹ thuật.

Nếu thay đổi làm lệch các nguyên tắc trên, phải nêu rõ trước khi thực hiện.
