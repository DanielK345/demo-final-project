# Chỉ mục tài liệu AloSM Voice

Cập nhật: **2026-08-16** · Trạng thái: `CURRENT`.

## Đọc theo thứ tự

1. [`PROJECT_SOURCE_OF_TRUTH.md`](PROJECT_SOURCE_OF_TRUTH.md) — authority, trạng thái và roadmap.
2. [`PRD_AloSM_Voice.md`](PRD_AloSM_Voice.md) — product requirement.
3. [`MVP.md`](MVP.md) — phạm vi/acceptance MVP.
4. [`architecture_diagram.md`](architecture_diagram.md) — kiến trúc runtime.
5. [`interface_design.md`](interface_design.md) — HTTP/WS/Agent boundary.
6. [`../src/agents/DATAFINDING.md`](../src/agents/DATAFINDING.md) — data contract/gap.
7. [`../mustdo.md`](../mustdo.md) — external blockers duy nhất.

## Tài liệu hiện hành

| Nhóm | Tài liệu |
|---|---|
| Product | `PRD_AloSM_Voice.md`, `MVP.md` |
| Architecture/API | `architecture_diagram.md`, `interface_design.md`, `database_supabase.md` |
| Voice | [`voice-ai/README.md`](voice-ai/README.md) và các runbook/evidence được index tại đó |
| Agent | `src/agents/README.md`, `src/agents/docs/*`, `src/agents/DATAFINDING.md` |
| Backend | `src/backend/README.md` |
| Frontend | `src/frontend/README.md`, `src/frontend/docs/*` |
| Data | `data/README.md`, `data/catalog.json` |
| AI Logs | [`AI_LOGS.md`](AI_LOGS.md) |
| Documentation maintenance | [`DOCUMENTATION_REMEDIATION_PROMPT.md`](DOCUMENTATION_REMEDIATION_PROMPT.md) |

## Reference tách biệt

`docs/guide/` và `specification_documents/` là tài liệu khóa học/template tham khảo,
không phải runtime status hoặc project contract. `presentation/` chỉ phục vụ artifact
trình bày. Kế hoạch, prompt tích hợp và progress log cũ đã xóa khỏi cây hiện hành;
dùng Git history khi cần tra cứu.

Mọi thay đổi runtime phải cập nhật contract/status liên quan trong cùng PR. Không tạo
thêm progress diary hoặc duplicate TODO; blocker ngoài repository chỉ ghi tại `mustdo.md`.
