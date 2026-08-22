# AloSM MVP Architecture

> Cập nhật: **2026-08-17** · Phạm vi: **Login/Auth** và **Homepage đặt xe bằng text hoặc voice**. Không gồm tracking, history, payment hoặc wallet.

> Voice production đã cutover sang LiveKit-native theo
> [`LIVEKIT_MIGRATION_IMPLEMENTATION.md`](LIVEKIT_MIGRATION_IMPLEMENTATION.md).

## Tech stack

| Phần | Công nghệ chính |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Agent | Custom model/tool loop, OpenAI-compatible LLM, typed `AgentState`, deterministic guardrails |
| Voice | LiveKit AgentSession, native Room transport, configurable STT/LLM/TTS plugins |
| Data | PostgreSQL/Supabase; SQLite local; Hà Nội gazetteer và mock VinUni/Hồ Gươm |

## 1. Overall architecture

```mermaid
flowchart TB
    U[User]
    FE[React Web<br/>Login + Homepage + Assistant popup]
    API[FastAPI<br/>REST control plane]
    LK[LiveKit Room<br/>realtime media + transcript]
    WORKER[LiveKit Agent worker]
    CORE[Backend orchestration<br/>Auth + Session + Booking]
    AGENT[Core Agent<br/>Conversation + Booking decisions]
    TOOLS[Backend tools<br/>Place + Quote + Booking]
    DATA[(PostgreSQL / Supabase<br/>Gazetteer / Maps)]
    AI[External AI<br/>STT + LLM + TTS]

    U --> FE
    FE --> API
    FE <--> LK
    LK <--> WORKER
    WORKER <--> CORE
    WORKER <--> AI
    API --> CORE
    CORE <--> AGENT
    AGENT -->|ToolCall| TOOLS
    TOOLS --> DATA
    TOOLS -->|ToolResult| AGENT
    CORE --> API
    API --> FE
```

Nguyên tắc ownership:

- Frontend chỉ hiển thị và thu input.
- Agent quyết định hội thoại nhưng không gọi DB/network.
- Backend thực thi tool, persist state và xác nhận booking.
- Chỉ báo đặt xe thành công sau kết quả Backend.

## 2. Agent architecture

```mermaid
flowchart TB
    INPUT[AgentInput<br/>Transcript hoặc ToolResult]
    STATE[AgentState<br/>Nguồn trạng thái duy nhất]
    MODEL[LLM<br/>Hiểu ý định và chọn semantic tool]
    POLICY[Typed policy + guardrails]
    ACTION{AgentAction}
    REPLY[ASK_USER / RESPOND / HANDOFF]
    CALL[CALL_TOOL]
    EXEC[Backend Tool Executor]

    INPUT --> STATE
    STATE --> MODEL
    MODEL --> POLICY
    POLICY --> ACTION
    ACTION --> REPLY
    ACTION --> CALL
    CALL --> EXEC
    EXEC -->|ToolResult| INPUT
```

Booking flow:

```mermaid
flowchart TB
    A[Thu pickup + destination + vehicle]
    B[Resolve địa điểm]
    C{Một hay nhiều kết quả?}
    D[Hỏi user chọn địa chỉ]
    E[Lấy quote]
    F[Đọc summary và hỏi xác nhận]
    G{User xác nhận?}
    H[Tạo booking idempotent]
    I[Trả kết quả]

    A --> B --> C
    C -->|Nhiều| D --> E
    C -->|Một| E
    E --> F --> G
    G -->|Có| H --> I
    G -->|Sửa thông tin| A
```

- User chỉ cần cung cấp **điểm đón, điểm đến, loại xe**.
- VinUni/Hồ Gươm trả nhiều mock candidates nên Agent phải hỏi chọn địa chỉ cụ thể.
- Đổi địa điểm/loại xe sẽ xóa quote và confirmation cũ.

## 3. LiveKit voice architecture

```mermaid
flowchart TB
    BROWSER[React + LiveKit components]
    ROOM[LiveKit Room]
    SESSION[AgentSession<br/>turn detection + interruption]
    MODELS[LiveKit STT / LLM / TTS plugins]
    TOOLS[Typed booking, quote, place, handoff tools]
    DB[(PostgreSQL / Supabase)]
    OP[Operator browser]

    BROWSER <--> ROOM
    ROOM <--> SESSION
    SESSION <--> MODELS
    SESSION --> TOOLS
    TOOLS <--> DB
    OP <--> ROOM
```

LiveKit sở hữu media transport, VAD/endpointing, interruption, realtime transcript
và audio playback. AloSM worker sở hữu prompt, typed tools, state recovery và handoff.

Các gap cần xử lý trước production:

- Agent booking vẫn chủ yếu dùng local Hà Nội gazetteer; Maps provider chưa là nguồn duy nhất.
- Supabase migration, RLS, backup/restore và multi-instance test vẫn là release gate.

## Runtime entrypoints

| Phần | File chính |
|---|---|
| Backend | `src/backend/main.py`, `src/backend/services/session_service.py` |
| Agent | `src/agents/agent.py`, `src/agents/core/agent.py` |
| Voice | `src/voice_agent/server.py`, `src/voice_agent/agent.py` |
| Frontend | `src/frontend/src/app/router/index.tsx`, `src/frontend/src/features/ai-assistant/` |

Nguồn đối chiếu: [`PROJECT_SOURCE_OF_TRUTH.md`](PROJECT_SOURCE_OF_TRUTH.md), [`src/agents/README.md`](../src/agents/README.md), [`voice-runtime-architecture.md`](voice-ai/voice-runtime-architecture.md).
