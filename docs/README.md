# Chỉ mục tài liệu AloSM Voice

Cập nhật: **2026-08-20** · Trạng thái: `CURRENT`.

## Đọc theo thứ tự

1. [CODING_AGENT_HANDOFF.md](CODING_AGENT_HANDOFF.md) — trạng thái LiveKit và việc tiếp theo.
2. [LIVEKIT_TEAM_SETUP.md](LIVEKIT_TEAM_SETUP.md) — cài, chạy, test và troubleshooting.
3. [LIVEKIT_MIGRATION_IMPLEMENTATION.md](LIVEKIT_MIGRATION_IMPLEMENTATION.md) — kiến trúc/implementation record.
4. [PHASE4_EVALUATION_PLAN.md](PHASE4_EVALUATION_PLAN.md) — reliability, benchmark và cutover.
5. [PROJECT_SOURCE_OF_TRUTH.md](PROJECT_SOURCE_OF_TRUTH.md) — trạng thái toàn project/external blockers.
6. [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md), [PRD_AloSM_Voice.md](PRD_AloSM_Voice.md), [MVP.md](MVP.md) — product requirements.
7. [../mustdo.md](../mustdo.md) — việc bắt buộc cần owner/hạ tầng.

Scope mentor gốc được giữ tại [GSM-08_VOICE_AGENT_SCOPE.md](GSM-08_VOICE_AGENT_SCOPE.md).

## Tài liệu hiện hành

| Nhóm | Tài liệu |
|---|---|
| Product | `PRODUCT_BRIEF.md`, `PRD_AloSM_Voice.md`, `MVP.md` |
| Architecture/API | `architecture_diagram.md`, `interface_design.md`, `database_supabase.md` |
| LiveKit current | `CODING_AGENT_HANDOFF.md`, `LIVEKIT_TEAM_SETUP.md`, `LIVEKIT_MIGRATION_IMPLEMENTATION.md` |
| Evaluation | `PHASE4_EVALUATION_PLAN.md`, `logs/livekit/*.jsonl` local evidence |
| Legacy Voice/evidence | [voice-ai/README.md](voice-ai/README.md) — historical reference; runtime/code đã được gỡ sau cutover |
| Agent | `src/agents/README.md`, `src/agents/docs/*`, `src/agents/DATAFINDING.md` |
| Backend | `src/backend/README.md` |
| Frontend | `src/frontend/README.md`, `src/frontend/docs/*` |
| Data | `data/README.md`, `data/catalog.json` |
| AI Logs | [AI_LOGS.md](AI_LOGS.md) |
| Performance | [performance/latency-remediation-plan.md](performance/latency-remediation-plan.md) |
| Policy | [policies/policy-integration-plan.md](policies/policy-integration-plan.md) |
| Verification/readiness | [verification/README.md](verification/README.md) |
| Deployment | [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md), [DEPLOYMENT_FLY_IO.md](DEPLOYMENT_FLY_IO.md), [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md) |

## Reference tách biệt

`docs/guide/` và `specification_documents/` chỉ chứa tài liệu khóa học/template tham khảo,
không phải runtime status hoặc contract của AloSM. `presentation/` là khu vực deliverable trình bày.
Proposal/prompt/TODO đã bị implementation hoặc `mustdo.md` thay thế được loại khỏi
cây hiện hành; dùng Git history khi cần truy vết.

Mọi thay đổi runtime phải cập nhật contract/status liên quan trong cùng PR. Không tạo progress diary
hoặc duplicate TODO; blocker ngoài repository chỉ ghi tại `mustdo.md`.
