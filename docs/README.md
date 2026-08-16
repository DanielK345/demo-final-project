# Chỉ mục tài liệu AloSM Voice

Cập nhật: **2026-08-16** · Trạng thái: `CURRENT`.

## Đọc theo thứ tự

1. [PROJECT_SOURCE_OF_TRUTH.md](PROJECT_SOURCE_OF_TRUTH.md) — authority, trạng thái và roadmap.
2. [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) — tóm tắt mục tiêu và giá trị sản phẩm.
3. [PRD_AloSM_Voice.md](PRD_AloSM_Voice.md) — yêu cầu sản phẩm chuẩn v1.2.
4. [MVP.md](MVP.md) — phạm vi và điều kiện nghiệm thu theo F1–F9.
5. [architecture_diagram.md](architecture_diagram.md) — kiến trúc runtime thực tế.
6. [interface_design.md](interface_design.md) — HTTP, WebSocket và Agent boundary.
7. [../src/agents/DATAFINDING.md](../src/agents/DATAFINDING.md) — data contract và khoảng trống.
8. [../mustdo.md](../mustdo.md) — external blockers duy nhất.

## Tài liệu hiện hành

| Nhóm | Tài liệu |
|---|---|
| Product | `PRODUCT_BRIEF.md`, `PRD_AloSM_Voice.md`, `MVP.md` |
| Architecture/API | `architecture_diagram.md`, `interface_design.md`, `database_supabase.md` |
| Voice | [voice-ai/README.md](voice-ai/README.md) và các runbook/evidence được index tại đó |
| Agent | `src/agents/README.md`, `src/agents/docs/*`, `src/agents/DATAFINDING.md` |
| Backend | `src/backend/README.md` |
| Frontend | `src/frontend/README.md`, `src/frontend/docs/*` |
| Data | `data/README.md`, `data/catalog.json` |
| AI Logs | [AI_LOGS.md](AI_LOGS.md) |
| Performance | [performance/latency-remediation-plan.md](performance/latency-remediation-plan.md) |
| Verification/readiness | [verification/README.md](verification/README.md) |
| Documentation maintenance | [DOCUMENTATION_REMEDIATION_PROMPT.md](DOCUMENTATION_REMEDIATION_PROMPT.md) |

## Reference tách biệt

`docs/guide/` và `specification_documents/` chỉ chứa tài liệu khóa học/template tham khảo,
không phải runtime status hoặc contract của AloSM. `presentation/` là khu vực deliverable trình bày.
Các kế hoạch, prompt tích hợp, báo cáo tiến trình và nguồn trùng đã được loại khỏi cây hiện hành;
dùng Git history khi cần truy vết.

Mọi thay đổi runtime phải cập nhật contract/status liên quan trong cùng PR. Không tạo progress diary
hoặc duplicate TODO; blocker ngoài repository chỉ ghi tại `mustdo.md`.
