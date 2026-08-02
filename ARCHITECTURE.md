# Architecture Document

## System Overview

AloSM Voice AI Agent là hệ thống hội thoại bằng giọng nói theo kiến trúc đa lớp, kết hợp Voice & Conversation Orchestration với các dịch vụ nghiệp vụ backend để cung cấp trải nghiệm đặt xe và hỗ trợ khách hàng hoàn toàn tự nhiên bằng tiếng Việt. Kiến trúc được thiết kế theo nguyên tắc **Voice-First + Human-in-the-Loop**, cho phép tự động hóa các nghiệp vụ tiêu chuẩn trong khi đảm bảo chuyển tiếp mượt mà sang tổng đài viên khi cần. Hệ thống hỗ trợ đa kênh (Web, Mobile, Tổng đài điện thoại) và mở rộng được theo chiều ngang thông qua API Gateway trung tâm.

---

## Architecture Diagram

`mermaid
graph TB
    subgraph CH["1. Kênh Người Dùng"]
        KH["Khách hàng - Web / Mobile / Tổng đài"]
        TDV["Tổng đài viên - Operator Console"]
        TX["Tài xế - Driver App / Portal"]
        QTV["Quản trị viên - Admin & AI Operations"]
    end

    subgraph LGT["2. Lớp Giao Tiếp"]
        CP["Customer Portal UI"]
        OP["Operator Console UI"]
        DP["Driver Portal UI"]
        AP["Admin Portal UI"]
        GW["API Gateway / Auth"]
        WS["WebSocket / Realtime Session Manager"]
    end

    subgraph VOCO["3. Voice & Conversation Orchestration"]
        AI["Audio Input / Streaming"]
        VAD["VAD & Audio Preprocessing"]
        ASR["ASR / Speech-to-Text"]
        TCM["Transcript & Context Manager"]
        AOC["Agent Orchestrator - Intent / Dialogue State / Tool Routing"]
        RAG["RAG / Knowledge Retrieval"]
        RG["Response Generator"]
        TTS["TTS / Text-to-Speech"]
        AO["Audio Output / Playback"]
    end

    subgraph NVT["4. Nghiệp Vụ & Tích Hợp"]
        BS["Booking Service"]
        FE2["Fare Estimation"]
        LG2["Location / Geocoding"]
        TLC["Trip Lookup & Cancellation"]
        HHS["Human Handoff Service"]
        NS["Notification Service"]
        DA["Driver Assignment"]
    end

    subgraph DLT["5. Dữ Liệu & Tri Thức"]
        URD[("User & Role Data")]
        CVH[("Conversation History")]
        BKD[("Bookings")]
        DTD[("Driver / Trip Data")]
        KBD[("Knowledge Base Documents")]
        VPF[("Voice Preferences")]
        FAL[("Feedback & Audit Logs")]
    end

    subgraph VHQ["6. Vận Hành & Quản Trị AI"]
        KBM["Knowledge Base Management"]
        ACF["Agent Configuration"]
        VL["Voice Library"]
        EVD["Evaluation Dashboard"]
        MNA["Monitoring & Analytics"]
        CPV["Consent / Privacy Controls"]
    end

    KH --> CP
    TDV --> OP
    TX --> DP
    QTV --> AP
    CP --> GW
    OP --> GW
    DP --> GW
    AP --> GW
    GW --> WS
    GW --> AI
    WS --> AI

    AI --> VAD --> ASR --> TCM --> AOC
    AOC --> RAG --> RG --> TTS --> AO
    AO -->|"Barge-in / Ngắt lời"| AI

    AOC -->|"Tool Calls"| BS
    AOC -->|"Tool Calls"| FE2
    AOC -->|"Tool Calls"| LG2
    AOC -->|"Tool Calls"| TLC
    AOC -->|"Tool Calls"| HHS
    AOC -->|"Tool Calls"| NS
    AOC -->|"Tool Calls"| DA

    BS -->|"Booking Result"| AI
    HHS --> OP

    BS --- BKD
    FE2 --- DTD
    LG2 --- URD
    TLC --- BKD
    AOC --- CVH
    RAG --- KBD
    RG --- VPF
    NS --- FAL

    KBM --- KBD
    ACF --- AOC
    VL --- TTS
    EVD --- FAL
    MNA --- CVH
    CPV --- URD
`

---

## Components

### 1. Kênh Người Dùng (User Channels)

- **Purpose:** Điểm khởi đầu tương tác từ các nhóm người dùng khác nhau — Khách hàng, Tổng đài viên, Tài xế, Quản trị viên.
- **Key Features:**
  - Đa kênh: Web browser, Mobile app, Tổng đài điện thoại
  - Mỗi nhóm người dùng có giao diện riêng biệt phù hợp với vai trò
  - Tất cả kênh đi qua API Gateway / Auth chung

### 2. Lớp Giao Tiếp (Communication Layer)

- **Customer Portal UI:** Giao diện web cho khách hàng khởi tạo hội thoại giọng nói, xem transcript và xác nhận booking.
- **Operator Console UI:** Giao diện cho tổng đài viên tiếp nhận cuộc gọi chuyển từ AI, xem transcript, tóm tắt và thực hiện nghiệp vụ.
- **Driver Portal UI:** Giao diện cho tài xế nhận chuyến, xem chi tiết và cập nhật trạng thái.
- **Admin Portal UI:** Giao diện quản trị viên/AI Ops để cấu hình Agent, quản lý Knowledge Base và theo dõi vận hành.
- **API Gateway / Auth:** Lớp trung tâm xác thực, phân quyền và định tuyến tất cả request từ mọi kênh.
- **WebSocket / Realtime Session Manager:** Duy trì kết nối thời gian thực để stream audio và cập nhật trạng thái hội thoại.
- **Authentication:** JWT-based, phân quyền theo role (Customer / Operator / Driver / Admin)

### 3. Voice & Conversation Orchestration

Pipeline 8 bước xử lý hội thoại:

#### Bước 1: Audio Input / Streaming
- Nhận audio stream từ microphone của người dùng qua WebSocket.
- Hỗ trợ barge-in (ngắt lời) — người dùng có thể ngắt phản hồi của AI bất kỳ lúc nào.

#### Bước 2: VAD & Audio Preprocessing
- **VAD (Voice Activity Detection):** Phát hiện khi nào người dùng bắt đầu/kết thúc nói.
- Lọc nhiễu và chuẩn hóa âm thanh trước khi gửi ASR.

#### Bước 3: ASR / Speech-to-Text
- Chuyển giọng nói thành văn bản (tiếng Việt).
- Tối ưu cho đa giọng vùng miền và ngữ cảnh đặt xe.

#### Bước 4: Transcript & Context Manager
- Lưu và quản lý transcript hội thoại theo phiên.
- Duy trì context đa lượt (địa chỉ đã xác nhận, intent trước đó, v.v.).

#### Bước 5: Agent Orchestrator
- **Agent Type:** ReAct Agent với Dialogue State Management
- **State Schema:**

`
AgentState:
  session_id: str
  user_id: str
  transcript: List[Message]
  intent: str                    # booking | info_query | cancellation | handoff | faq
  dialogue_state: str            # collecting_info | confirming | executing | completed
  collected_slots: Dict          # pickup, dropoff, vehicle_type, time
  confidence_score: float
  handoff_reason: Optional[str]
  tool_results: Dict
`

- **Nodes:**
  - intent_detector — Phân loại ý định từ utterance
  - slot_filler — Thu thập thông tin còn thiếu (hỏi từng slot một)
  - confirmation_gate — Xác nhận thông tin quan trọng trước khi thực hiện
  - 	ool_router — Định tuyến gọi tool phù hợp
  - handoff_trigger — Kích hoạt chuyển tổng đài viên khi cần
  - 
esponse_planner — Lập kế hoạch phản hồi ngắn gọn, rõ ràng

- **Agent Flow:**

`mermaid
graph LR
    START --> ID["intent_detector"]
    ID --> SF{"Đủ thông tin?"}
    SF -->|"Không"| SL["slot_filler"]
    SL --> SF
    SF -->|"Có"| CG["confirmation_gate"]
    CG --> HT{"Handoff?"}
    HT -->|"Có"| HTG["handoff_trigger"]
    HTG --> END
    HT -->|"Không"| TR["tool_router"]
    TR --> RP["response_planner"]
    RP --> END
`

- **Tools:**
  - create_booking — Tạo booking mới
  - estimate_fare — Ước tính giá chuyến
  - geocode_address — Phân giải địa chỉ / địa danh
  - lookup_trip — Tra cứu trạng thái chuyến đi
  - cancel_trip — Hủy chuyến (với xác nhận 2 chiều)
  - handoff_to_operator — Chuyển tiếp tổng đài viên kèm context
  - send_notification — Gửi thông báo SMS/app
  - search_knowledge_base — Tìm kiếm FAQ và chính sách dịch vụ

#### Bước 6: RAG / Knowledge Retrieval
- Truy xuất thông tin từ Knowledge Base (chính sách, FAQ, giá cước) bằng semantic search.
- **Embeddings:** Vietnamese-optimized embedding model
- **Vector Store:** ChromaDB (có thể thay bằng Pinecone khi scale)

#### Bước 7: Response Generator
- Sinh câu trả lời ngắn gọn, tự nhiên, phù hợp với giọng nói (không dùng Markdown hay bullet points).
- Áp dụng Voice Preferences (tốc độ, giọng, phong cách ngôn ngữ) theo từng nhóm user.

#### Bước 8: TTS / Text-to-Speech & Audio Output
- Chuyển văn bản phản hồi thành giọng nói tiếng Việt tự nhiên.
- Stream audio output về client.

### 4. Nghiệp Vụ & Tích Hợp (Business Services)

| Service | Chức năng |
|---|---|
| **Booking Service** | Tạo, cập nhật booking; trả về Booking Result cho Agent |
| **Fare Estimation** | Ước tính giá chuyến dựa trên điểm đón/đến và loại xe |
| **Location / Geocoding** | Phân giải địa danh, địa chỉ tiếng Việt thành tọa độ |
| **Trip Lookup & Cancellation** | Tra cứu và hủy chuyến đang thực hiện |
| **Human Handoff Service** | Chuyển context + transcript sang Operator Console |
| **Notification Service** | Gửi SMS/push notification xác nhận booking, cập nhật trạng thái |
| **Driver Assignment** | Nhận yêu cầu booking và phân công tài xế |

### 5. Dữ Liệu & Tri Thức (Data Layer)

| Store | Loại | Nội dung |
|---|---|---|
| **User & Role Data** | Relational (PostgreSQL) | Thông tin tài khoản, phân quyền, consent |
| **Conversation History** | Document (PostgreSQL JSONB) | Transcript phiên hội thoại, dialogue state |
| **Bookings** | Relational (PostgreSQL) | Thông tin booking, trạng thái chuyến |
| **Driver / Trip Data** | Relational (PostgreSQL) | Thông tin tài xế, chuyến đi, vị trí |
| **Knowledge Base Documents** | Vector Store (ChromaDB) + Object Storage | FAQ, chính sách, hướng dẫn dịch vụ |
| **Voice Preferences** | Relational (PostgreSQL) | Cài đặt giọng, tốc độ, ngôn ngữ theo user |
| **Feedback & Audit Logs** | Append-only (PostgreSQL / S3) | Đánh giá cuộc gọi, log nghiệp vụ, audit trail |

- **Migrations:** Alembic

### 6. Vận Hành & Quản Trị AI (AI Operations)

| Module | Chức năng |
|---|---|
| **Knowledge Base Management** | Upload, chỉnh sửa, phiên bản hóa và xuất bản tài liệu KB |
| **Agent Configuration** | Cấu hình prompt, ngưỡng confidence, số lần retry trước handoff |
| **Voice Library** | Quản lý voice profiles, TTS model versions |
| **Evaluation Dashboard** | Theo dõi Task Completion Rate, CSAT, handoff rate, lỗi tool |
| **Monitoring & Analytics** | Real-time metrics, alert khi anomaly, phân tích cuộc gọi thất bại |
| **Consent / Privacy Controls** | Quản lý consent ghi âm, ẩn PII trong UI, GDPR/PDPA compliance |

---

## Data Flow

**Luồng chính — Đặt xe bằng giọng nói:**

1. Người dùng nhấn "Gọi AI" → Cấp quyền microphone → WebSocket kết nối.
2. Audio stream → VAD phát hiện giọng nói → ASR chuyển thành text.
3. Transcript & Context Manager lưu utterance, cập nhật dialogue history.
4. Agent Orchestrator phân tích intent → xác định thiếu slot (pickup/dropoff).
5. Agent yêu cầu RAG tra cứu nếu cần thông tin địa danh / chính sách.
6. Response Generator sinh câu hỏi thu thập thông tin còn thiếu.
7. TTS → Audio Output phát câu hỏi về client.
8. Người dùng trả lời → lặp lại bước 2–7 cho đến khi đủ thông tin.
9. Agent kích hoạt confirmation_gate → đọc lại thông tin để xác nhận.
10. Người dùng xác nhận → Agent gọi create_booking → Booking Service tạo booking.
11. Booking Result trả về → Response Generator tạo thông báo xác nhận.
12. TTS phát kết quả → Notification Service gửi SMS xác nhận.

**Luồng handoff — Chuyển tổng đài viên:**

1. Agent phát hiện: confidence thấp / 2 lần thất bại / yêu cầu nhạy cảm / user chủ động yêu cầu.
2. handoff_trigger gọi Human Handoff Service kèm toàn bộ context.
3. Operator Console UI hiển thị transcript, tóm tắt, thông tin đã thu thập cho tổng đài viên.
4. Tổng đài viên tiếp nhận mà không cần hỏi lại khách từ đầu.

---

## Deployment Architecture

`mermaid
graph TB
    subgraph Cloud["Cloud Infrastructure"]
        subgraph FE_Layer["Frontend Layer"]
            CP_C["Customer Portal - Next.js"]
            OP_C["Operator Console - Next.js"]
            DP_C["Driver Portal - Next.js"]
            AP_C["Admin Portal - Next.js"]
        end

        subgraph GW_Layer["Gateway Layer"]
            GW_C["API Gateway - FastAPI"]
            WS_C["WebSocket Server - FastAPI async"]
        end

        subgraph BE_Layer["Backend Services"]
            VOCO_C["Voice Orchestration Service"]
            BIZ_C["Business Services - FastAPI microservices"]
            AI_OPS["AI Ops Service"]
        end

        subgraph DATA_Layer["Data Layer"]
            PG[("PostgreSQL")]
            CHROMA[("ChromaDB - Vector Store")]
            S3["Object Storage - S3 / MinIO"]
        end
    end

    CP_C --> GW_C
    OP_C --> GW_C
    DP_C --> GW_C
    AP_C --> GW_C
    CP_C -->|"Audio WebSocket"| WS_C
    GW_C --> VOCO_C
    GW_C --> BIZ_C
    GW_C --> AI_OPS
    WS_C --> VOCO_C
    VOCO_C --> PG
    VOCO_C --> CHROMA
    BIZ_C --> PG
    AI_OPS --> PG
    AI_OPS --> CHROMA
    AI_OPS --> S3
`

- **Containerization:** Docker + Docker Compose (dev), Kubernetes (prod)
- **CI/CD:** GitHub Actions
- **Environment:** .env per service, secrets via Vault / cloud secret manager

---

## Security

| Hạng mục | Giải pháp |
|---|---|
| **Authentication** | JWT (access token ngắn hạn + refresh token) |
| **Authorization** | RBAC — 4 roles: Customer / Operator / Driver / Admin |
| **API Keys & Secrets** | Lưu trong .env, không commit vào repo; production dùng Vault |
| **Input Validation** | Pydantic v2 trên toàn bộ API |
| **Audio Privacy** | Ghi âm chỉ khi có consent; tự động xóa sau thời hạn lưu trữ |
| **PII Protection** | Số điện thoại không đọc toàn bộ qua TTS; ẩn trong UI theo role |
| **Rate Limiting** | Giới hạn request/IP trên API Gateway |
| **CORS** | Chỉ cho phép domain frontend đã cấu hình |
| **Audit Logging** | Mọi hành động nghiệp vụ (tạo/hủy booking, handoff) đều được ghi log |

---

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| **API Framework** | FastAPI | Async native, auto-docs OpenAPI, type-safe với Pydantic |
| **Agent Architecture** | LangGraph ReAct | State machine rõ ràng, dễ debug dialogue flow, hỗ trợ multi-step tool use |
| **Realtime Communication** | WebSocket | Latency thấp cho audio streaming 2 chiều, hỗ trợ barge-in |
| **Database** | PostgreSQL | ACID transactions cần thiết cho booking; JSONB cho dialogue state linh hoạt |
| **Vector Store** | ChromaDB | Dễ self-host, phù hợp MVP; migrate Pinecone khi cần scale |
| **Embeddings** | Vietnamese-optimized model | ASR và retrieval chính xác hơn với tiếng Việt có dấu |
| **Frontend** | Next.js | SSR/SSG, routing, tích hợp WebSocket dễ dàng, TypeScript native |
| **Voice Pipeline** | Streaming chunk-by-chunk | Giảm perceived latency; cho phép barge-in tự nhiên |
| **Handoff Strategy** | Human-in-the-Loop | AI chỉ tự xử lý nghiệp vụ chuẩn hóa; con người tiếp nhận khi cần phán đoán |
| **Knowledge Management** | RAG + ChromaDB | Không cần fine-tune khi cập nhật chính sách; chỉ cần update document |
