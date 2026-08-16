# Prompt chuẩn hóa toàn bộ tài liệu AloSM Voice

Cập nhật: **2026-08-16**. Prompt này là execution specification cho đợt làm sạch
tài liệu hiện tại và có thể tái sử dụng cho các lần audit sau.

## Prompt

Bạn đang làm việc trực tiếp trong repository AloSM Voice. Hãy audit và chuẩn hóa
toàn bộ tài liệu để một developer hoặc AI mới có thể xác định chính xác:

1. Project hiện chạy gì.
2. Contract nào có thẩm quyền.
3. Dữ liệu nào là demo, staging, release-gated hoặc production-blocked.
4. Việc cần làm tiếp theo theo đúng dependency.
5. Cách chạy, test, deploy và nghiệm thu từng subsystem.

### Nguồn sự thật

Khi có mâu thuẫn, ưu tiên theo thứ tự:

1. Code runtime, migration, OpenAPI và test hiện hành.
2. Contract của subsystem.
3. `docs/PROJECT_SOURCE_OF_TRUTH.md` và status/runbook hiện hành.
4. PRD/MVP cho yêu cầu chưa triển khai.
5. Git history cho kế hoạch, prompt và báo cáo cũ.

Không giữ một file chỉ vì nó ghi lại lịch sử. Git đã làm nhiệm vụ lưu lịch sử.

### Taxonomy bắt buộc

Mỗi tài liệu được phân đúng một nhóm:

- `CURRENT`: contract, runbook hoặc status đang dùng.
- `PRODUCT`: PRD/MVP/design requirement còn hiệu lực.
- `REFERENCE`: tài liệu khóa học hoặc reference độc lập, không mô tả runtime.
- `EVIDENCE`: report JSON/benchmark/eval tái tạo được và còn dùng nghiệm thu.
- `DELETE`: đã bị thay thế, trùng lặp, sai runtime hoặc chỉ là kế hoạch lịch sử.

Không tạo thư mục archive trong repository cho nhóm `DELETE`; dùng Git history.

### Tiêu chí giữ

Chỉ giữ tài liệu đáp ứng ít nhất một điều kiện:

- định nghĩa product requirement còn hiệu lực;
- định nghĩa API/schema/state/tool/runtime contract hiện hành;
- hướng dẫn chạy/test/deploy có thể thực hiện với code hiện tại;
- mô tả status/gap có owner, evidence và ngày cập nhật;
- là artifact benchmark/eval/live report còn được referenced;
- là tài liệu reference được phân vùng rõ, không thể bị hiểu là project status.

### Tiêu chí xóa

Xóa tài liệu nếu:

- prompt đã thực thi xong và kết quả đã nằm trong code/runbook;
- TODO/kế hoạch tuần/branch cũ không còn phản ánh repository;
- báo cáo tiến trình chỉ kể lịch sử và không phải acceptance evidence;
- duplicate must-do/status/source-of-truth;
- phần lớn link, tên file, route, provider hoặc trạng thái đã lỗi thời;
- nội dung đã được thay thế đầy đủ bởi tài liệu CURRENT khác.

Trước khi xóa phải tìm mọi reference bằng `rg`, cập nhật code comment, README,
JSON comment và link sang tài liệu CURRENT tương ứng.

### Cấu trúc đích

```text
README.md                         entrypoint ngắn
mustdo.md                         external blockers duy nhất
docs/
  README.md                       chỉ mục duy nhất
  PROJECT_SOURCE_OF_TRUTH.md      authority/status/roadmap
  DOCUMENTATION_REMEDIATION_PROMPT.md
  PRD_AloSM_Voice.md
  MVP.md
  architecture_diagram.md
  interface_design.md
  database_supabase.md
  AI_LOGS.md
  voice-ai/
    README.md                     chỉ mục Voice
    voice-runtime-architecture.md
    voice_local_dev.md
    transcript-rewrite.md
    tts-output.md
    zipformer-asr.md
    *.json                        evidence benchmark/live
src/agents/README.md              Agent entrypoint
src/agents/docs/*                 Agent contracts/status
src/backend/README.md             Backend runtime/persistence truth
src/frontend/README.md            Frontend entrypoint
src/frontend/docs/*               status/design/integration/user flow hiện hành
data/README.md + catalog.json      data governance/catalog
docs/guide/ + specification_documents/  REFERENCE, không phải project status
```

### Yêu cầu nội dung

- Mọi link nội bộ phải tồn tại và dùng đường dẫn đúng từ file nguồn.
- Không ghi test count, provider readiness hoặc production claim nếu chưa có evidence.
- Một khái niệm chỉ có một nguồn chuẩn; file khác link tới, không copy dài.
- ENV phải khớp `.env.example`; không ghi credential thật.
- API phải khớp OpenAPI/code; frontend status phải khớp route và API client.
- `mustdo.md` chỉ chứa việc thật sự cần credential, business data, consent,
  license, hạ tầng hoặc human sign-off.
- Code comment không được trỏ tới file đã xóa.
- Tài liệu tiếng Việt dùng UTF-8, thuật ngữ và trạng thái nhất quán.

### Trình tự thực hiện

1. Inventory toàn bộ Markdown/JSON evidence và reference graph.
2. Lập manifest KEEP/RENAME/DELETE với replacement cho từng file xóa.
3. Tạo/cập nhật entrypoint và subsystem index trước.
4. Rename tài liệu CURRENT có filename lỗi thời.
5. Cập nhật nội dung CURRENT từ code/test/OpenAPI.
6. Cập nhật toàn bộ reference trong code và docs.
7. Xóa chính xác từng file nhóm DELETE; không recursive delete thư mục rộng.
8. Kiểm tra không còn basename/reference của file đã xóa.
9. Chạy Markdown link checker, JSON parse, secret-pattern scan, `git diff --check`.
10. Chạy pytest/Ruff/compile và frontend lint/typecheck/build theo thay đổi.

### Definition of Done

- Có một entrypoint và một source of truth rõ ràng.
- Không còn tài liệu project lịch sử/trùng lặp trong cây hiện hành.
- Không còn link/code comment trỏ file đã xóa.
- Mọi tài liệu giữ lại được phân loại rõ CURRENT/PRODUCT/REFERENCE/EVIDENCE.
- Runtime/API/ENV/status trong docs khớp code và test.
- Link checker, JSON parse, secret scan và diff check đạt.
- Backend/Voice/Agent tests, Ruff/compile và frontend checks đạt.
- Báo cáo cuối liệt kê file xóa/rename/giữ, lý do, test result và external blockers.

### Quy tắc an toàn

- Không xóa PRD, contract, migration, evidence live hoặc runbook còn hiệu lực.
- Không sửa business truth khi chưa có owner/provider data.
- Không mock provider rồi gọi là live evidence.
- Không in hoặc commit secret.
- Không sửa/xóa unrelated user changes.
