# AGENTS.md — Coding Principles for Agentic AI Track

Đề: Các cột thông tin chính (Cột 1 & Cột 2)
STT / Mã: 124 | GSM-08

Tên dự án / Mảng: KD VH Dịch vụ gọi xe X – Ứng dụng gọi xe X (Dịch vụ gọi xe X)

Chi tiết nội dung trong các ô:
1. Mô tả & Vấn đề (Ảnh 1):
Tên tính năng / Giải pháp:

AI Agent Tổng đài giọng nói đặt xe & tra cứu Dịch vụ gọi xe X

📍 Thực trạng:

Nhiều khách (đặc biệt lớn tuổi) quen gọi tổng đài đặt xe; nhân viên trực điện thoại tốn nguồn lực, giờ cao điểm nghẽn máy.

🎯 Vấn đề:

Cần AI Agent giọng nói (voice) tiếp nhận cuộc gọi: nghe yêu cầu đặt xe/tra cứu chuyến/hỏi cước, xác nhận điểm đón-đến bằng lời, gọi tool đặt xe và đọc xác nhận, chuyển người thật khi cần.

🔒 Ràng buộc:

HITL/chuyển tổng đài viên khi nhận diện kém hoặc yêu cầu phức tạp; bảo mật ghi âm & PII; độ chính xác STT tiếng Việt & xác nhận địa chỉ; độ trễ hội thoại thấp (barge-in), kiểm soát chi phí STT/TTS.

2. Công nghệ & Phạm vi triển khai (Ảnh 2):
Stack công nghệ:

STT tiếng Việt (Whisper/PhoWhisper) + TTS (ElevenLabs/Google) + LLM + LangGraph

tool geocoding (Mapbox/Google Places) xác nhận địa chỉ

PostgreSQL chuyến

backend FastAPI + WebRTC/WebSocket streaming

frontend React (web call)

deploy Fly.io.

Phạm vi chức năng:

Cơ bản:

Web call deploy, đăng nhập khách & tổng đài viên

Luồng thoại đặt xe + xác nhận địa chỉ + đọc kết quả

Transcript & memory hội thoại.

Nâng cao:

Barge-in & xử lý ngắt lời

HITL chuyển người thật kèm ngữ cảnh

Cảnh báo độ tin cậy nhận dạng thấp

Fallback sang nhập tay khi STT lỗi và guardrail PII.

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

Luồng tổng quát:

```text
Voice/STT
   ↓ transcript + confidence
Backend
   ↓ AgentInput + AgentState
LLMAgent
   ↓
Router
   ↓
Business Workflow
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
→ đúng workflow đang chờ
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

### Router / Orchestrator

Router trả lời:

> Request này thuộc workflow nào hoặc cần tiếp tục workflow nào?

Router được phép:
- classify intent;
- ưu tiên `current_workflow`;
- route `ToolResult`;
- xử lý unknown/fallback ở mức tổng quát.

Router **không** được:
- thu thập pickup/destination;
- xác nhận booking;
- diễn giải business result của tool;
- viết logic chi tiết của Booking/Trip/FAQ.

### Business Workflow

Workflow trả lời:

> Trong workflow hiện tại, bước nghiệp vụ tiếp theo là gì?

Workflow chịu trách nhiệm:
- đọc input + state;
- xác định missing data;
- quyết định hỏi user;
- quyết định cần tool;
- xử lý `ToolResult` của chính workflow;
- cập nhật step;
- hoàn thành / retry / handoff theo policy.

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

## 7. Feature ownership

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
src/agents/schemas.py
src/agents/state.py
src/agents/agent.py
src/agents/workflows/base.py
src/agents/tools/base.py
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

Track integration branch:

```text
feature/agentic-ai
```

Feature branch phải branch từ `feature/agentic-ai`.

Flow:

```text
feat/<feature-name>
    ↓ PR
feature/agentic-ai
    ↓ integration test
develop
    ↓ system test
main
```

PR phải:
- chỉ chứa scope của feature;
- không trộn refactor không liên quan;
- mô tả behavior thay đổi;
- nêu state transition nếu có;
- có tests;
- target `feature/agentic-ai`.

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

Core Agent F1–F8 đã implemented, gồm multi-turn workflows, typed tool lifecycle,
conversation history/context/rewrite, repair/interruption, grounded FAQ,
production guardrails và offline readiness evaluation.

Current offline baseline:
- 342 tests passed, 5 real-provider tests skipped theo opt-in policy;
- Ruff passed;
- Python compile passed;
- readiness-v1 đạt các configured gates.

External executors, production persistence/knowledge ingestion và Voice Runtime
không nằm trong `src/agents`. Dùng `CORE_AGENT_STATUS.md` làm trạng thái/DoD hiện
hành; các implementation/completion plan chỉ mô tả thiết kế và lịch sử phase.

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
