# PRD mẫu — Trợ lý tra cứu tri thức cho phòng Kế toán

**Phiên bản:** 0.2 · **Trạng thái:** Draft để xác thực với người dùng · **Primary persona:** Kế toán viên doanh nghiệp

> Sản phẩm giúp kế toán tìm và đối chiếu thông tin trong bộ tài liệu đã được doanh nghiệp phê duyệt. Sản phẩm hỗ trợ tra cứu, không thay thế phê duyệt nghiệp vụ hay tư vấn thuế.

## 1. Problem statement

Khi kiểm tra một khoản thu/chi, hóa đơn hoặc cách hạch toán, kế toán viên phải tìm thủ công trong nhiều nguồn: quy chế tài chính nội bộ, quy trình thanh toán, hướng dẫn hạch toán, luật, nghị định, thông tư và công văn. Tài liệu phân tán, dài, có nhiều phiên bản và cách diễn đạt khác nhau khiến việc tìm chậm, dễ dùng nhầm văn bản hết hiệu lực hoặc trả lời thiếu căn cứ.

**Giả thuyết baseline cần kiểm chứng:** mỗi kế toán có 5–10 lượt tra cứu/tuần, mất 15–30 phút/lượt; vào kỳ khóa sổ hoặc kê khai, tần suất và rủi ro sai tăng cao. Trước khi chốt PRD, phỏng vấn 3–5 kế toán, quan sát ít nhất 5 lượt tra cứu và thu 5–10 tài liệu mẫu.

### Pain points ưu tiên

| Pain point | Quy trình hiện tại → failure | Tác động | Root cause |
|---|---|---|---|
| Tra cứu quy định thu/chi và tiền | Mở quy chế, quy trình, file biểu mẫu và hỏi người có kinh nghiệm → lâu, câu trả lời không đồng nhất | Chậm duyệt thanh toán; có thể thiếu hồ sơ hoặc vượt thẩm quyền | Tài liệu phân tán, tìm theo từ khóa, thiếu một nguồn đã duyệt |
| Áp dụng chính sách thuế | Tìm luật/nghị định/thông tư/công văn trên nhiều cổng → khó xác định hiệu lực và văn bản liên quan | Nguy cơ kê khai hoặc xác định chi phí/thuế sai | Văn bản thay đổi, dẫn chiếu chéo, thiếu lịch sử phiên bản |
| Đối chiếu chứng từ và hạch toán | So hóa đơn/chứng từ với hướng dẫn nội bộ, chế độ kế toán → dễ bỏ sót điều kiện | Tốn thời gian rà soát; tăng vòng hỏi–đáp và sửa hồ sơ | Thông tin nằm ở nhiều đoạn, bảng và phụ lục |
| Bàn giao và giải trình | Tìm lại căn cứ cho kiểm toán, quản lý hoặc nhân sự mới → phụ thuộc người nhớ tài liệu | Mất thời gian, tri thức thất lạc khi đổi nhân sự | Kiến thức nằm trong đầu người và thư mục rời rạc |

Đây là các pain point hợp lý theo nghiệp vụ nhưng **chưa phải evidence nội bộ**. Cơ sở pháp lý cho thấy tài liệu kế toán phải được bảo quản đầy đủ, an toàn và người lập/ký chịu trách nhiệm về nội dung; thủ tục thuế trải rộng từ khai, nộp, hoàn, miễn/giảm đến tra soát nghĩa vụ. Vì vậy nguồn trích dẫn, phiên bản và quyền truy cập là yêu cầu cốt lõi, không phải tính năng phụ ([Luật Kế toán 88/2015/QH13](https://vanban.chinhphu.vn/?classid=1&docid=183198&pageid=27160&typegroupid=3), [Cục Thuế — giao dịch điện tử trong lĩnh vực thuế](https://gdt.gov.vn/wps/portal/home/documents/detail?1dmy=&current=true&urile=wcm%3Apath%3AGDT+Content%2Fsa_gdt%2Fcctthc%2Ftthchh%2Fsa_tthc_vanban%2Fsa_tthc_vb_vbqd%2F85fdcbb0-5cbc-474d-a5af-14182128833f)).

## 2. Goals & metrics

Trong pilot 4 tuần với 5 kế toán viên và bộ câu hỏi chuẩn do Kế toán trưởng duyệt:

- Giảm thời gian trung vị để tìm được câu trả lời có căn cứ xuống **≤ 3 phút/lượt** và ít nhất **70% so với baseline đo tuần đầu**.
- Ít nhất **90% câu trả lời được chấp nhận** bởi Kế toán trưởng, không có lỗi nghiêm trọng trong bộ 30 câu hỏi chuẩn.
- **100% câu trả lời khẳng định nghiệp vụ** có trích dẫn đúng tài liệu, phiên bản và vị trí nguồn.
- **100% câu không đủ căn cứ hoặc ngoài phạm vi** được báo rõ là chưa đủ thông tin, không tự suy diễn.

## 3. Persona

**Primary — Kế toán viên doanh nghiệp:** làm việc trên laptop; dùng phần mềm kế toán, Excel, email và thư mục dùng chung; thường tra cứu dưới áp lực hạn thanh toán, khóa sổ và kê khai; hiểu nghiệp vụ nhưng mức độ quen AI không đồng đều. Mục tiêu là tìm đúng căn cứ nhanh và có thể kiểm tra lại trước khi thực hiện.

**Vai trò liên quan:** Kế toán trưởng là người phê duyệt nguồn và kết quả quan trọng; quản trị tri thức quản lý tài liệu/quyền truy cập. Hai vai trò này không phải primary persona.

## 4. Input

| Chiều input | Phạm vi MVP |
|---|---|
| Loại | PDF và DOCX dạng text: quy chế tài chính, quy trình thu/chi–thanh toán, hướng dẫn hạch toán, luật/nghị định/thông tư/công văn |
| Kích thước | ≤ 50 MB/file, ≤ 200 trang/file, tối đa 20 file/lần |
| Ngôn ngữ | Tiếng Việt; có thể chứa bảng và thuật ngữ tiếng Anh |
| Chất lượng | Tài liệu đọc được, có tiêu đề/phiên bản; file scan và chữ viết tay ngoài MVP |
| Khối lượng pilot | ≤ 1.000 tài liệu, 5 người dùng |
| Nguồn | Chỉ tài liệu do quản trị tri thức tải lên và Kế toán trưởng đánh dấu **Đã duyệt**; lưu metadata: tên, loại, số hiệu, ngày hiệu lực/hết hiệu lực, phiên bản, phòng ban, mức truy cập |

## 5. Scope & priority

| Priority | Feature | Giá trị |
|---|---|---|
| **Must** | Quản lý kho tài liệu đã duyệt | Một nguồn tra cứu có phiên bản và trạng thái hiệu lực rõ ràng |
| **Must** | Hỏi đáp kèm trích dẫn | Tìm câu trả lời và mở đúng vị trí nguồn để kiểm chứng |
| **Must** | Phân quyền 2 vai trò | Ngăn người dùng xem tài liệu ngoài quyền truy cập |
| **Should** | Tóm tắt một tài liệu theo mẫu | Nắm nhanh phạm vi, điểm chính, nghĩa vụ và mốc thời gian |
| **Could** | So sánh hai phiên bản văn bản | Hỗ trợ nhận biết nội dung thay đổi |
| **Won't** | Tự động hạch toán, duyệt chi, kê khai/nộp thuế; kết nối ngân hàng/phần mềm kế toán; tư vấn pháp lý; OCR file scan; tìm Internet trực tiếp | Giữ MVP trong một hành trình tra cứu an toàn |

## 6. Features & acceptance criteria

> **Quy ước:** Feature và AC ở cấp feature là phạm vi cam kết của PRD. Các user stories bên dưới chỉ là gợi ý phân rã, **không bắt buộc và chưa được chốt**; team sẽ refinement, bổ sung và chốt AC cấp story trong buổi grooming trước từng sprint.

### F1 — Quản lý kho tài liệu đã duyệt (Must)

**Pain point giải quyết:** tài liệu phân tán, thiếu phiên bản chuẩn và khó xác định hiệu lực.

**User stories**

1. Là quản trị tri thức, tôi muốn tải tài liệu và khai báo metadata để tạo nguồn tra cứu có cấu trúc.
2. Là Kế toán trưởng, tôi muốn duyệt tài liệu để chỉ nguồn hợp lệ được sử dụng.
3. Là kế toán viên, tôi muốn thấy phiên bản và hiệu lực để tránh dùng nhầm tài liệu.

**AC**

- Given file đúng phạm vi, when tải lên, then hệ thống hiển thị trạng thái xử lý và các metadata bắt buộc.
- Tài liệu chỉ được dùng để trả lời sau khi có trạng thái **Đã duyệt**.
- Phiên bản cũ vẫn truy vết được nhưng phải hiển thị trạng thái hết hiệu lực/thay thế.
- File lỗi, thiếu metadata hoặc vượt giới hạn bị từ chối với lý do cụ thể.

### F2 — Hỏi đáp có căn cứ (Must)

**Pain point giải quyết:** tra cứu thu/chi, thuế, chứng từ và hạch toán chậm; kết quả tìm kiếm thiếu căn cứ hoặc mâu thuẫn. *Lưu ý phạm vi: MVP hỗ trợ tra cứu quy định/hướng dẫn liên quan; việc so khớp từng chứng từ cụ thể vẫn do kế toán viên thực hiện.*

**User stories**

1. Là kế toán viên, tôi muốn hỏi bằng ngôn ngữ tự nhiên để không phải mở từng tài liệu.
2. Là kế toán viên, tôi muốn mở đúng đoạn nguồn để kiểm tra trước khi áp dụng.
3. Là kế toán viên, tôi muốn hệ thống từ chối khi thiếu căn cứ để không dùng câu trả lời sai.

**AC**

- Câu trả lời chỉ dựa trên tài liệu **Đã duyệt** mà người dùng có quyền xem.
- Mỗi kết luận nghiệp vụ kèm tên/số hiệu tài liệu, phiên bản và số trang hoặc mục; người dùng mở được đúng đoạn nguồn.
- **Định nghĩa "đủ căn cứ":** mỗi kết luận nghiệp vụ phải gắn với ít nhất một đoạn trích nguyên văn từ tài liệu **Đã duyệt** chứa trực tiếp nội dung kết luận đó. Câu trả lời chỉ suy diễn bằng cách ghép nhiều đoạn, mà không đoạn nào nêu trực tiếp kết luận, được coi là **thiếu căn cứ**.
- Khi câu hỏi ngoài phạm vi hoặc thiếu căn cứ theo định nghĩa trên, hệ thống báo "Chưa đủ căn cứ trong kho tài liệu" và gợi ý thông tin/tài liệu cần bổ sung.
- Nếu các nguồn mâu thuẫn, hệ thống nêu rõ mâu thuẫn và yêu cầu Kế toán trưởng xác nhận, không tự chọn một đáp án.
- Không tạo trích dẫn không tồn tại; tỷ lệ trích dẫn hợp lệ đạt 100% trên bộ 30 câu hỏi chuẩn.
- p95 thời gian phản hồi ≤ 10 giây trong pilot, không tính thời gian xử lý tài liệu mới.

### F3 — Phân quyền và truy vết (Must)

**Pain point giải quyết:** tài liệu tài chính nhạy cảm nhưng đang nằm trong thư mục dùng chung; khó biết ai đã tải, duyệt hoặc sử dụng nguồn nào.

**User stories**

1. Là kế toán viên, tôi chỉ muốn thấy tài liệu được cấp quyền để tránh lộ dữ liệu phòng ban khác.
2. Là quản trị tri thức, tôi muốn gán quyền theo vai trò để quản lý phạm vi truy cập.
3. Là Kế toán trưởng, tôi muốn xem nhật ký để truy vết khi cần kiểm tra hoặc giải trình.

**AC**

- Kế toán viên chỉ xem/hỏi trên tài liệu được cấp quyền; quản trị tri thức được tải và quản lý tài liệu.
- Người không có quyền không thấy tên, nội dung, đoạn trích hoặc sự tồn tại của tài liệu bị hạn chế.
- Mọi lần tải tài liệu, đổi trạng thái, hỏi và mở nguồn đều có nhật ký gồm người dùng và thời điểm.

### F4 — Tóm tắt tài liệu theo mẫu (Should)

**Pain point giải quyết:** văn bản dài, nhiều dẫn chiếu khiến kế toán mất thời gian xác định phần liên quan đến nghiệp vụ.

**User stories**

1. Là kế toán viên, tôi muốn xem tóm tắt để nhanh chóng hiểu phạm vi và nội dung chính.
2. Là kế toán viên, tôi muốn thấy nghĩa vụ, điều kiện và mốc thời gian để biết phần cần chú ý.
3. Là kế toán viên, tôi muốn từng ý có nguồn để kiểm tra lại tài liệu gốc.

**AC**

- Output gồm: phạm vi áp dụng, nội dung chính, nghĩa vụ/điều kiện, mốc thời gian, văn bản liên quan và điểm cần Kế toán trưởng xác nhận.
- Mỗi mục có trích dẫn; nội dung không có trong tài liệu được ghi "Không đề cập".

## 7. Non-functional requirements

- **Bảo mật:** xác thực người dùng, kiểm soát quyền ở cả kết quả và trích dẫn; không dùng dữ liệu nội bộ để huấn luyện nếu chưa được cho phép.
- **Độ tin cậy:** không trả lời khi nguồn không đủ; lưu phiên bản nguồn và nhật ký để truy vết. **Mọi câu trả lời khẳng định nghiệp vụ (hỏi đáp, tóm tắt) luôn kèm cảnh báo: cần người có thẩm quyền kiểm tra trước khi áp dụng** — áp dụng chung cho mọi feature, không lặp lại ở AC từng feature.
- **Hiệu năng:** p95 hỏi đáp ≤ 10 giây với phạm vi pilot.
- **Đánh giá AI:** bộ 30 câu hỏi chuẩn với phân bố cố định — 12 happy path · 6 thiếu nguồn · 6 nguồn mâu thuẫn · 6 ngoài phạm vi; Kế toán trưởng chấm đúng/sai và mức độ có căn cứ. Phân bố có thể điều chỉnh khi chốt đáp án chuẩn nhưng phải cố định trước khi đo.
- **Khả dụng:** lỗi tải/xử lý tài liệu phải có trạng thái và hướng xử lý rõ ràng.

## 8. Definition of Done

MVP done khi 5 người dùng hoàn thành hành trình **đăng nhập → hỏi → đọc câu trả lời → mở nguồn → xác nhận/từ chối sử dụng**, toàn bộ **Must features (F1–F3) đạt AC cấp feature ở mục 6** và đạt các metric ở mục 2 trên bộ 30 câu hỏi chuẩn.

## 9. Open questions

| Câu hỏi cần chốt | Owner | Hạn |
|---|---|---|
| Baseline thực tế: lượt tra cứu, thời gian và lỗi phổ biến? | PO | Trước khi sprint 1 bắt đầu |
| 5–10 tài liệu mẫu và metadata nào đang sẵn có? | Kế toán trưởng | Trước grooming F1 |
| Ai có quyền duyệt từng loại văn bản và xử lý khi nguồn mâu thuẫn? | Kế toán trưởng | Trước grooming F2 |
| Ngưỡng "lỗi nghiêm trọng" (quyết định cách xây bộ eval) | PO + Kế toán trưởng | Trước khi sprint 1 bắt đầu |
| Đáp án chuẩn cho 30 câu eval | Kế toán trưởng | Trước UAT |

## 10. Sign-off

PRD chỉ chuyển từ **Draft → Approved** khi đủ 3 xác nhận dưới đây. Mỗi người ký xác nhận đúng phạm vi trách nhiệm của mình.

| Vai trò | Phạm vi xác nhận | Người | Ngày | Trạng thái |
|---|---|---|---|---|
| PO | Nội dung, ưu tiên MoSCoW, metric khả thi về nghiệp vụ | — | — | ☐ Chờ ký |
| Tech Lead | Khả thi kỹ thuật trong capacity team, gồm p95 ≤ 10s với kho ≤ 1.000 tài liệu | — | — | ☐ Chờ ký |
| Kế toán trưởng | Đúng nghiệp vụ kế toán–thuế; duyệt bộ 30 câu eval và định nghĩa "đủ căn cứ" | — | — | ☐ Chờ ký |
