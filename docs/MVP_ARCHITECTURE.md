# AloSM MVP Architecture

> Cập nhật: **2026-08-17** · Phạm vi: **Login/Auth** và **Homepage đặt xe bằng text hoặc voice**. Không gồm tracking, history, payment hoặc wallet.

## Tech stack

| Phần | Công nghệ chính |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Agent | Custom model/tool loop, OpenAI-compatible LLM, typed `AgentState`, deterministic guardrails |
| Voice | ZipFormer/OpenAI/Gemini/Groq ASR, contextual LLM rewrite, OpenAI/Edge TTS, FFmpeg |
| Data | PostgreSQL/Supabase; SQLite local; Hà Nội gazetteer và mock VinUni/Hồ Gươm |

## 1. Overall architecture

```mermaid
flowchart TB
    U[User]
    FE[React Web<br/>Login + Homepage + Assistant popup]
    API[FastAPI<br/>REST + WebSocket]
    CORE[Backend orchestration<br/>Auth + Session + Voice]
    AGENT[Core Agent<br/>Conversation + Booking decisions]
    TOOLS[Backend tools<br/>Place + Quote + Booking]
    DATA[(PostgreSQL / Supabase<br/>Gazetteer / Maps)]
    AI[External AI<br/>LLM + ASR + TTS]

    U --> FE
    FE --> API
    API --> CORE
    CORE <--> AGENT
    AGENT -->|ToolCall| TOOLS
    TOOLS --> DATA
    TOOLS -->|ToolResult| AGENT
    CORE <--> AI
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

## 3. Voice Gateway architecture

```mermaid
flowchart TB
    AUDIO[Browser audio]
    TRANSPORT{Transport}
    REST[REST /voice/turn<br/>Utterance hoàn chỉnh]
    WS[WebSocket /voice/stream<br/>PCM16 + VAD]
    ASR[ASR<br/>ZipFormer hoặc cloud provider]
    CLEAN[Normalize + place aliases]
    REWRITE[Contextual LLM rewrite<br/>PII + semantic guard]
    SESSION[SessionService + Core Agent]
    REVIEW[Output review]
    TTS[TTS<br/>OpenAI hoặc Edge fallback]
    OUTPUT[Transcript + reply + audio]

    AUDIO --> TRANSPORT
    TRANSPORT --> REST
    TRANSPORT --> WS
    REST --> ASR
    WS --> ASR
    ASR --> CLEAN
    CLEAN --> REWRITE
    REWRITE --> SESSION
    SESSION --> REVIEW
    REVIEW --> TTS
    TTS --> OUTPUT
```

| Lane | Runtime hiện tại |
|---|---|
| REST | ASR auto: ZipFormer → OpenAI → Gemini; OpenAI TTS primary, Edge fallback |
| WebSocket | ZipFormer → Groq ASR; Edge TTS |
| Rewrite | Dùng workflow, bước hiện tại và place candidates; lỗi thì giữ transcript cũ |

Các gap cần xử lý trước production:

- Agent booking vẫn chủ yếu dùng local Hà Nội gazetteer; Maps provider chưa là nguồn duy nhất.
- OpenAI TTS chưa đi qua đầy đủ FFmpeg validation như Edge lane.
- `/voice/speak` chưa enforce auth; WebSocket hiện tạo guest session.
- Supabase migration, RLS, backup/restore và multi-instance test vẫn là release gate.

## Runtime entrypoints

| Phần | File chính |
|---|---|
| Backend | `src/backend/main.py`, `src/backend/services/session_service.py` |
| Agent | `src/agents/agent.py`, `src/agents/core/agent.py` |
| Voice | `src/backend/services/voice_service.py`, `src/voice/gateway.py` |
| Frontend | `src/frontend/src/app/router/index.tsx`, `src/frontend/src/features/ai-assistant/` |

Nguồn đối chiếu: [`PROJECT_SOURCE_OF_TRUTH.md`](PROJECT_SOURCE_OF_TRUTH.md), [`src/agents/README.md`](../src/agents/README.md), [`voice-runtime-architecture.md`](voice-ai/voice-runtime-architecture.md).
