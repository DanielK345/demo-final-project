# AloSM Voice AI Agent — PRD

**Phiên bản:** 1.2 · **Trạng thái:** Draft để xác thực với người dùng · **Primary persona:** Khách hàng ít thành thạo công nghệ / người lớn tuổi

> Sản phẩm cho phép khách hàng thực hiện toàn bộ hành trình dịch vụ AloSM — từ đặt xe, thanh toán, khiếu nại đến hỗ trợ tài xế — bằng giọng nói tiếng Việt tự nhiên, thông qua giao diện web. AI xử lý các nghiệp vụ có quy trình cố định; con người tiếp nhận các tình huống khẩn cấp, phức tạp và cần phán đoán.

---

## 1. Problem statement

Hiện tại, khách hàng AloSM có hai lựa chọn để đặt xe: dùng ứng dụng di động hoặc gọi hotline 1555. Cả hai đều có giới hạn rõ ràng:

- **Ứng dụng** yêu cầu người dùng phải biết thao tác màn hình cảm ứng, nhập địa chỉ chính xác và thực hiện nhiều bước. Người lớn tuổi hoặc người ít quen công nghệ thường bỏ cuộc giữa chừng, phải nhờ người thân hỗ trợ, hoặc không đặt được xe.
- **Hotline 1555** hoạt động nhờ tổng đài viên xử lý từng cuộc gọi thủ công. Giờ cao điểm (sáng sớm, chiều tối) lượng gọi tăng đột biến vượt năng lực phục vụ — khách chờ lâu, tổng đài viên quá tải.
- **Thanh toán, khiếu nại và hoàn tiền** hiện chỉ xử lý được qua app hoặc tổng đài — người dùng không quen app bị phụ thuộc vào kênh duy nhất là hotline vốn đã quá tải.
- **Tài xế** cần xác nhận chuyến và cập nhật trạng thái khi đang lái xe, nhưng thao tác app trong khi lái rất bất tiện và không an toàn.

**Giả thuyết cần kiểm chứng trước sprint 1:** Phần lớn cuộc gọi tổng đài là đặt xe, hỏi giá, tra cứu trạng thái, hỏi về thanh toán và khiếu nại — các nghiệp vụ có quy trình cố định, hoàn toàn có thể tự động hóa. Cần thu thập số liệu vận hành thực tế từ CS Manager trước khi đặt KPI giảm tải cụ thể.

### Pain points ưu tiên

| Pain point | Quy trình hiện tại → điểm gãy | Tác động | Nguyên nhân gốc |
|---|---|---|---|
| Người lớn tuổi / ít quen app không đặt được xe | Mở app → nhập địa chỉ → thực hiện từng bước → bỏ cuộc hoặc nhờ người khác | Mất khách; khách phụ thuộc vào người thân | Không có kênh đặt xe nào đơn giản hơn app |
| Khách phải kể lại toàn bộ thông tin khi được chuyển sang tổng đài viên | AI không xử lý được → chuyển operator → khách bắt đầu lại từ đầu | Trải nghiệm kém; tổng đài viên phải mất thêm thời gian thu thập lại thông tin đã có | Không có cơ chế chuyển ngữ cảnh từ AI sang người thật |
| AI tự chọn địa chỉ sai → tài xế đến nhầm nơi | Khách nói tên địa danh → AI tự chọn một kết quả → booking được tạo với địa chỉ sai | Booking thất bại; tài xế và khách đều bị ảnh hưởng | AI suy diễn thay vì hỏi lại khi địa chỉ chưa rõ |
| Nghẽn đường dây giờ cao điểm | Lượng gọi tăng đột biến → khách chờ dài → bỏ cuộc | Mất đơn; chi phí cơ hội cao | Số tổng đài viên cố định; không có lớp tự động xử lý phía trước |
| Khách không thể thanh toán / khiếu nại khi không quen app | Gọi hotline → chờ dài → mô tả lại vấn đề → xử lý thủ công | Trải nghiệm kém; khách bỏ cuộc giữa chừng | Không có kênh thay thế cho app khi xử lý giao dịch và phản ánh |
| Tài xế phải thao tác điện thoại khi đang lái để cập nhật trạng thái | Cầm điện thoại → mở app → bấm xác nhận → không an toàn khi di chuyển | Nguy cơ tai nạn; tài xế bỏ qua cập nhật trạng thái | Không có cách nào cập nhật bằng giọng nói |

> Các pain point trên được rút ra từ phỏng vấn sơ bộ và phân tích nghiệp vụ, **chưa có số đo nội bộ**. Cần phỏng vấn 5–10 người dùng mục tiêu và thu thập dữ liệu vận hành tổng đài trước khi sprint 1 bắt đầu.

---

## 2. Goals & metrics

Trong pilot 4–6 tuần với nhóm người dùng mục tiêu (ưu tiên người lớn tuổi, người ít quen app):

- **Task completion (đặt xe):** Ít nhất **80% người tham gia** hoàn tất kịch bản đặt xe bằng giọng nói từ đầu đến khi nhận mã booking, không cần hỗ trợ thêm.
- **AI resolution:** Ít nhất **65% yêu cầu đặt xe hợp lệ** được AI xử lý thành công mà không cần chuyển sang tổng đài viên; tỉ lệ booking sai địa chỉ **≤ 5%**.
- **Handoff quality:** **100% cuộc gọi chuyển operator** phải có transcript đầy đủ và tóm tắt ngữ cảnh sẵn sàng trước khi tổng đài viên tiếp nhận — tổng đài viên **không phải hỏi lại từ đầu**.
- **Emergency response:** **100% tình huống khẩn cấp** (tai nạn, người ngã, cần cấp cứu) được phát hiện và kết nối tổng đài viên chuyên môn trong vòng **30 giây**.
- **Complaint & refund capture:** **100% yêu cầu hoàn tiền và khiếu nại** được tiếp nhận có ticket đầy đủ thông tin, không để khách phải gọi lại.
- **Baseline:** Thiết lập được bộ số liệu gốc (số cuộc gọi/ngày, tỉ lệ hoàn thành, CSAT) trong tuần đầu tiên của pilot để làm mốc so sánh cho các giai đoạn tiếp theo.

---

## 3. Persona

**Primary — Khách hàng ít quen công nghệ:** không sử dụng thành thạo ứng dụng đặt xe; người thân đã cài sẵn và hướng dẫn cơ bản. Nói chậm, có thể dừng giữa chừng để suy nghĩ. Sợ nói sai địa chỉ và lo lắng khi hệ thống im lặng lâu. Mục tiêu: tự đặt xe, thanh toán và gửi khiếu nại mà không cần nhờ người khác hỗ trợ.

*Kịch bản điển hình:* Gọi AI và nói "Tôi muốn đặt xe đi Bệnh viện Bạch Mai, tôi đang ở đường Trần Hưng Đạo, quận Hoàn Kiếm."

**Secondary — Khách hàng quen công nghệ nhưng bận tay:** thành thạo app, nhưng thường xuyên trong tình huống không thể nhìn hoặc thao tác màn hình (đang mang đồ, di chuyển). Muốn đặt xe, kiểm tra thanh toán hoặc báo sự cố nhanh bằng giọng nói mà không mở app.

*Kịch bản điển hình:* Đang trong thang máy, nói "Cho tôi đặt xe từ Landmark 81 đến sân bay Tân Sơn Nhất."

**Secondary — Tài xế đối tác:** cần xác nhận chuyến, tra cứu thông tin và cập nhật trạng thái trong khi đang lái xe. Thao tác điện thoại khi lái nguy hiểm và không hợp pháp.

*Kịch bản điển hình:* Đang lái xe, nói "Xác nhận tôi đã đón khách" hoặc "Tôi muốn hỏi địa chỉ điểm đến của chuyến này."

**Vai trò liên quan (không phải primary persona):**

- **Tổng đài viên:** tiếp nhận cuộc gọi được chuyển từ AI; cần thấy ngay nội dung hội thoại và tóm tắt ngữ cảnh để tiếp tục hỗ trợ mà không hỏi lại từ đầu.
- **AI Operations:** quản lý kho tri thức (Knowledge Base) và cấu hình AI Agent; cần công cụ kiểm thử nội dung trước khi đưa vào production và theo dõi chất lượng qua dashboard.

---

## 4. Scope & priority

| Priority | Feature | Giá trị — Pain point được giải quyết |
|---|---|---|
| **Must** | F1 — Đặt xe bằng giọng nói | Xóa rào cản app; bất kỳ ai cũng có thể đặt xe chỉ bằng câu nói tự nhiên |
| **Must** | F2 — Chuyển giao tổng đài viên (Human-in-the-Loop) | Khách không bị kẹt với AI; tổng đài viên nhận đầy đủ ngữ cảnh ngay lập tức |
| **Must** | F3 — Tra cứu thông tin và giải đáp câu hỏi thường gặp | Tự động xử lý các cuộc gọi hỏi giá, hỏi trạng thái — giảm tải cho tổng đài |
| **Must** | F9 — Xử lý tình huống khẩn cấp và tai nạn | An toàn tính mạng không thể chờ; AI phát hiện và kết nối ngay đúng người xử lý |
| **Should** | F4 — Đăng nhập, đồng ý ghi âm và phân quyền | Bảo vệ dữ liệu cá nhân; mỗi vai trò chỉ thấy đúng thông tin thuộc phạm vi của mình |
| **Should** | F5 — Quản lý kho tri thức và theo dõi chất lượng | AI Ops cập nhật được nội dung; PO và CS Manager có dữ liệu để cải thiện Agent |
| **Should** | F6 — Thanh toán qua giọng nói | Người dùng không cần mở app để thanh toán; giảm tải hotline cho nghiệp vụ tài chính cơ bản |
| **Should** | F7 — Tiếp nhận hoàn tiền và khiếu nại | Mọi phản ánh đều được ghi nhận đầy đủ; tổng đài viên xử lý ca phức tạp có đủ context |
| **Should** | F8 — Hỗ trợ tài xế qua giọng nói | Tài xế không phải thao tác màn hình khi đang lái — an toàn hơn và cập nhật trạng thái đúng giờ |
| **Won't** | Tích hợp đa kênh (Zalo, Messenger, WhatsApp), đa ngôn ngữ, app mobile native, can thiệp thuật toán ghép chuyến, tự phê duyệt hoàn tiền không qua con người | Giữ MVP trong phạm vi hội thoại qua web — kiểm soát được và đủ để kiểm chứng giá trị |

---

## 5. Features & acceptance criteria

> **Quy ước đọc tài liệu này:** Mục "AC" (Acceptance Criteria) là điều kiện bắt buộc — tính năng chỉ được xem là hoàn thành khi đáp ứng toàn bộ. Các "User stories" là gợi ý phân rã để team grooming, **chưa được chốt chính thức**; AC cấp story sẽ được thêm trong buổi sprint planning.

---

### F1 — Đặt xe bằng giọng nói (Must)

**Pain point giải quyết:** Người lớn tuổi và người ít quen công nghệ không thể đặt xe qua app vì giao diện đòi hỏi quá nhiều thao tác. Tính năng này cho phép họ chỉ cần nói — AI lo phần còn lại.

**User stories**

1. Là khách hàng, tôi muốn nói yêu cầu đặt xe bằng câu bình thường để AI hiểu và thu thập thông tin thay tôi.
2. Là khách hàng, tôi muốn được chọn địa chỉ từ danh sách khi tôi nói tên chung chung, để tránh booking sai nơi.
3. Là khách hàng, tôi muốn biết giá ước tính trước khi xác nhận để chủ động quyết định.
4. Là khách hàng, tôi muốn nghe lại toàn bộ thông tin (điểm đón, điểm đến, loại xe, giá) trước khi xác nhận đặt, để kiểm tra lại trước khi chốt.
5. Là khách hàng, tôi muốn sửa bất kỳ thông tin nào trước khi xác nhận để tránh booking sai.
6. Là khách hàng, tôi muốn dùng bàn phím nhập text khi micro không hoạt động để vẫn đặt được xe.

**AC**

- Given khách nói yêu cầu đặt xe, when AI chưa đủ thông tin (thiếu điểm đón hoặc điểm đến hoặc loại xe), then AI hỏi đúng một thông tin còn thiếu mỗi lượt — không hỏi nhiều thứ cùng lúc.
- Given khách nói địa danh có nhiều vị trí tương tự (ví dụ: "Vincom"), when AI tìm thấy nhiều hơn một kết quả khớp, then AI liệt kê danh sách ít nhất 2 lựa chọn cụ thể và hỏi khách chọn — **AI không tự chọn**.
- Given AI đã thu thập đủ thông tin, when chuyển sang bước xác nhận, then AI đọc lại toàn bộ: điểm đón, điểm đến, loại xe và giá ước tính, kèm ghi chú rõ "đây là giá tham khảo, không phải giá chính thức".
- Given khách xác nhận, when AI tạo booking, then hệ thống trả về mã booking duy nhất; nếu khách bấm xác nhận nhiều lần trong cùng phiên, hệ thống **không tạo booking thứ hai**.
- Given khách muốn sửa thông tin trước khi xác nhận, when khách nói hoặc gõ yêu cầu sửa, then AI cập nhật và đọc lại thông tin đã thay đổi.
- Given micro không hoạt động hoặc khách từ chối cấp quyền mic, when hệ thống phát hiện, then tự động hiện ô nhập text kèm hướng dẫn; AI tiếp tục hội thoại bình thường qua text.
- Given cuộc gọi đang diễn ra, then màn hình luôn hiển thị một trong ba trạng thái: **Đang nghe** / **Đang xử lý** / **Đang trả lời** — không để khách chờ im lặng quá 3 giây mà không có phản hồi nào.
- Given hội thoại đang diễn ra, then transcript (nội dung cuộc gọi dạng chữ) hiển thị realtime, phân biệt rõ phần AI nói và phần khách nói bằng màu hoặc nhãn khác nhau.

---

### F2 — Chuyển giao tổng đài viên (Must)

**Pain point giải quyết:** Khách phải kể lại toàn bộ thông tin khi được chuyển sang tổng đài viên; khách bị kẹt với AI khi yêu cầu vượt quá phạm vi xử lý tự động.

**User stories**

1. Là khách hàng, tôi muốn yêu cầu gặp người thật bất kỳ lúc nào trong cuộc gọi để không bị giữ lại với AI.
2. Là khách hàng, tôi muốn AI tự động chuyển tổng đài viên sau khi AI thất bại 2 lần liên tiếp, để không bị kẹt trong vòng lặp.
3. Là tổng đài viên, tôi muốn thấy ngay nội dung cuộc gọi và tóm tắt khi tiếp nhận, để không phải hỏi lại khách từ đầu.
4. Là tổng đài viên, tôi muốn tạo booking thủ công trong màn hình hỗ trợ, để phục vụ khách khi AI không tạo được.

**AC**

- Given khách nói "gặp người thật" hoặc nhấn nút Gặp tổng đài viên bất kỳ lúc nào, when AI nhận yêu cầu, then AI thông báo ngay và chuyển khách vào hàng chờ — **không từ chối, không hỏi lý do, không trì hoãn**.
- Given AI nhận diện hoặc xác nhận thất bại 2 lần liên tiếp với cùng một yêu cầu, when đạt ngưỡng, then AI chủ động thông báo cho khách và đề nghị chuyển tổng đài viên; ngưỡng "2 lần" có thể thay đổi qua cấu hình Admin.
- Given phát hiện tình huống nhạy cảm (khách đề cập khiếu nại tranh chấp phức tạp, yêu cầu không có trong KB), when AI nhận dạng được, then AI chuyển ngay sang tổng đài viên mà không cần chờ đủ 2 lần thất bại.
- Given cuộc gọi được chuyển sang tổng đài viên, when tổng đài viên mở màn hình tiếp nhận, then tổng đài viên thấy: toàn bộ transcript, tóm tắt ngắn (ý định khách, thông tin đã thu thập, lý do chuyển) — **trước** khi nghe tiếng khách.
- Given nhiều tổng đài viên đang online, when một cuộc gọi vào hàng chờ, then chỉ đúng một tổng đài viên tiếp nhận — không có tình trạng hai người cùng nhận một cuộc gọi.
- Given khách đang trong hàng chờ, then khách thấy vị trí của mình trong hàng chờ và có thể hủy chờ bất kỳ lúc nào.
- Given tổng đài viên đã tiếp nhận, then tổng đài viên có thể tạo booking mới từ màn hình hỗ trợ bằng form gồm: điểm đón, điểm đến, loại xe, thông tin liên hệ; booking chỉ được tạo sau khi tổng đài viên xác nhận.

---

### F3 — Tra cứu thông tin và giải đáp câu hỏi thường gặp (Must)

**Pain point giải quyết:** Tổng đài phải xử lý nhiều cuộc gọi hỏi giá, hỏi trạng thái chuyến và hỏi chính sách — các câu hỏi lặp lại, có câu trả lời cố định. Nếu AI xử lý được những cuộc này, tổng đài viên có thêm thời gian cho các ca phức tạp thực sự.

**User stories**

1. Là khách hàng, tôi muốn hỏi giá ước tính từ điểm A đến điểm B mà không cần đặt xe, để quyết định trước khi hành động.
2. Là khách hàng, tôi muốn hỏi chuyến đặt của tôi đang ở đâu và tài xế đến chưa, để không phải lo lắng chờ đợi.
3. Là khách hàng, tôi muốn hỏi về chính sách dịch vụ (hủy xe, loại xe, khuyến mãi) và nhận câu trả lời chính xác có nguồn gốc rõ ràng.

**AC**

- Given khách hỏi giá từ A đến B, when AI trả lời, then câu trả lời bao gồm: giá ước tính và ghi chú rõ "đây là giá tham khảo, giá thực tế có thể thay đổi tùy thời điểm và lộ trình" — AI không đưa ra giá cố định.
- Given khách hỏi trạng thái chuyến, when AI truy vấn hệ thống, then AI đọc kết quả trạng thái cụ thể và hiển thị trong transcript.
- Given khách hỏi về chính sách dịch vụ, when AI tìm trong kho tri thức, then câu trả lời chỉ được tổng hợp từ tài liệu đã được xuất bản chính thức — AI không tự suy diễn hay thêm thông tin ngoài tài liệu.
- Given câu hỏi không có câu trả lời đủ căn cứ trong kho tri thức, when AI không tìm được tài liệu phù hợp, then AI thông báo rõ "Tôi chưa có thông tin về vấn đề này" và đề nghị chuyển tổng đài viên — không đoán hay bịa câu trả lời.

---

### F4 — Đăng nhập, đồng ý ghi âm và phân quyền (Should)

**Pain point giải quyết:** Dữ liệu cá nhân của khách (số điện thoại, địa chỉ nhà) cần được bảo vệ. Mỗi vai trò (khách hàng, tổng đài viên, tài xế, admin) chỉ nên thấy đúng thông tin và chức năng thuộc phạm vi của mình.

**User stories**

1. Là khách hàng, tôi muốn được hỏi ý kiến rõ ràng trước khi cuộc gọi được ghi âm, để tôi có quyền quyết định.
2. Là khách hàng, tôi muốn đăng nhập bằng số điện thoại và mã OTP để xác nhận danh tính an toàn.
3. Là Admin, tôi muốn tạo, khóa và phân quyền tài khoản tổng đài viên và tài xế để kiểm soát ai được truy cập hệ thống.

**AC**

- Given khách nhấn "Gọi AI", when màn hình khởi động cuộc gọi, then hệ thống hiển thị thông báo đồng ý ghi âm trước khi bắt đầu; nếu khách từ chối, cuộc gọi vẫn diễn ra bình thường nhưng **không ghi âm**.
- Given khách đăng nhập thành công, when vào hệ thống, then giao diện hiển thị đúng theo vai trò: khách hàng **không thấy** màn hình tổng đài viên; tổng đài viên **không thấy** trang cấu hình Admin; tài xế chỉ thấy màn hình dành cho tài xế.
- Given AI đang phản hồi bằng giọng nói, when AI cần nhắc số điện thoại của khách, then AI chỉ đọc 4 số cuối — **không đọc toàn bộ số**.
- Given Admin khóa một tài khoản, when tài khoản đó cố đăng nhập, then hệ thống từ chối truy cập; hành động khóa được ghi vào nhật ký (audit log) với thời điểm và tên Admin thực hiện.

---

### F5 — Quản lý kho tri thức và theo dõi chất lượng (Should)

**Pain point giải quyết:** AI Ops hiện không có công cụ để kiểm tra xem AI sẽ trả lời gì trước khi đưa tài liệu vào production. PO và CS Manager không có dữ liệu tổng hợp để biết AI đang hoạt động tốt hay không và cần cải thiện ở đâu.

> **Lưu ý cho người đọc không chuyên kỹ thuật:** "Kho tri thức" (Knowledge Base) là tập hợp tài liệu nội bộ (chính sách, FAQ, quy trình) mà AI dùng để trả lời câu hỏi của khách. Việc kiểm thử truy xuất nghĩa là: nhập một câu hỏi thử, xem AI sẽ tìm ra tài liệu nào để trả lời — để đảm bảo AI không dùng tài liệu sai hoặc đã hết hiệu lực.

**User stories**

1. Là AI Ops, tôi muốn tải tài liệu FAQ và chính sách lên kho tri thức và kiểm thử câu trả lời trước khi công bố, để đảm bảo AI trả lời đúng.
2. Là AI Ops, tôi muốn khôi phục phiên bản tài liệu cũ khi phát hiện tài liệu mới có nội dung sai, để sửa nhanh mà không gián đoạn dịch vụ.
3. Là PO / CS Manager, tôi muốn xem dashboard tổng hợp các chỉ số quan trọng mỗi ngày để biết AI đang hoạt động tốt đến đâu và cần cải thiện ở đâu.

**AC**

- Given AI Ops tải tài liệu lên (định dạng PDF, DOCX hoặc TXT), when hệ thống xử lý xong, then tài liệu hiển thị trạng thái "Chờ xuất bản"; tài liệu **chỉ được AI dùng để trả lời** sau khi AI Ops chủ động bấm "Xuất bản" — tài liệu đang chờ không ảnh hưởng production.
- Given tài liệu đã xuất bản, when AI Ops nhập một câu hỏi kiểm thử, then hệ thống hiển thị: tên tài liệu được chọn, điểm liên quan (relevance score) và đoạn trích được dùng để trả lời.
- Given AI Ops cần rollback, when chọn phiên bản cũ và xác nhận, then phiên bản cũ được kích hoạt; phiên bản nào đang hiệu lực được đánh dấu rõ ràng trong danh sách.
- Given PO hoặc CS Manager vào Dashboard, when chọn khoảng thời gian, then màn hình hiển thị tối thiểu 5 chỉ số: (1) tổng số cuộc gọi, (2) tỉ lệ đặt xe thành công qua AI, (3) tỉ lệ chuyển tổng đài viên (HITL rate), (4) điểm hài lòng khách hàng (CSAT), (5) số ticket khiếu nại / hoàn tiền đã tạo; dữ liệu cập nhật ít nhất mỗi giờ.

---

### F6 — Thanh toán qua giọng nói (Should)

**Pain point giải quyết:** Người dùng không quen app không thể thực hiện thanh toán qua giao diện đồ họa. Họ phải gọi hotline — vốn đã quá tải — để được hỗ trợ thanh toán.

> **Lưu ý:** AI thực hiện giao dịch qua payment gateway tích hợp. AI không lưu thông tin thẻ và không xử lý thông tin thanh toán nhạy cảm — mọi dữ liệu thẻ đi qua payment gateway được chứng nhận bảo mật. Cần xác nhận payment gateway cụ thể của AloSM trước khi phát triển (xem Open Questions).

**User stories**

1. Là khách hàng, tôi muốn xem lịch sử thanh toán của mình để kiểm tra các giao dịch đã thực hiện.
2. Là khách hàng, tôi muốn chọn phương thức thanh toán (ví điện tử, thẻ, tiền mặt) bằng giọng nói.
3. Là khách hàng, tôi muốn xác nhận giao dịch thanh toán rõ ràng trước khi tiền bị trừ.

**AC**

- Given khách hỏi lịch sử thanh toán, when AI truy vấn hệ thống theo tài khoản đã đăng nhập, then AI đọc danh sách tối đa 5 giao dịch gần nhất (ngày, số tiền, loại xe, phương thức thanh toán) — không đọc số thẻ hay tài khoản đầy đủ.
- Given khách muốn thanh toán cho một chuyến, when AI xác định chuyến cần thanh toán, then AI thông báo rõ: số tiền, phương thức đang dùng; khách phải xác nhận bằng lời nói rõ ràng trước khi giao dịch được gửi đến payment gateway.
- Given khách xác nhận thanh toán, when payment gateway xử lý, then AI thông báo kết quả thành công hay thất bại kèm lý do ngắn gọn nếu thất bại.
- Given thanh toán thất bại (hết tiền, lỗi kết nối), when xảy ra, then AI đề nghị thử lại hoặc chọn phương thức khác — không tự thử lại mà không có sự đồng ý của khách.
- Given khách muốn thay đổi phương thức thanh toán mặc định, when AI nhận yêu cầu, then AI chuyển sang màn hình cài đặt phương thức thanh toán — **không xử lý thay đổi thẻ qua giọng nói trực tiếp** (bảo mật).

---

### F7 — Tiếp nhận hoàn tiền và khiếu nại (Should)

**Pain point giải quyết:** Khách muốn phản ánh sự cố hoặc yêu cầu hoàn tiền nhưng không quen thao tác app và không muốn chờ tổng đài. Mọi phản ánh cần được ghi nhận đầy đủ và theo dõi được, ngay cả khi AI không tự giải quyết được.

**User stories**

1. Là khách hàng, tôi muốn yêu cầu hoàn tiền cho một chuyến có sự cố bằng giọng nói, để không phải thao tác app.
2. Là khách hàng, tôi muốn theo dõi trạng thái yêu cầu hoàn tiền hoặc khiếu nại đã gửi, để biết đang được xử lý đến đâu.
3. Là khách hàng, tôi muốn phản ánh sự cố với tài xế (thái độ, lộ trình sai, v.v.) bằng giọng nói.

**AC**

- Given khách yêu cầu hoàn tiền, when AI thu thập được: mã chuyến (hoặc ngày giờ ước chừng), lý do yêu cầu, then AI xác nhận lại thông tin và tạo ticket hoàn tiền với trạng thái "Chờ xem xét"; AI thông báo mã ticket và thời gian xử lý dự kiến theo chính sách.
- Given khách muốn khiếu nại về tài xế hoặc dịch vụ, when AI nhận yêu cầu, then AI hỏi: loại sự cố (thái độ / lộ trình / an toàn / khác), mã chuyến liên quan, mô tả sự cố; sau khi thu thập đủ, tạo ticket với mức ưu tiên phù hợp.
- Given sự cố liên quan đến **an toàn** (tai nạn, hành vi đe dọa), when AI nhận dạng được loại sự cố, then **ưu tiên cao nhất — chuyển ngay sang F9 (Emergency Response)** thay vì tạo ticket thông thường.
- Given khách hỏi trạng thái ticket đã tạo, when AI truy vấn hệ thống theo mã ticket hoặc số điện thoại, then AI đọc trạng thái hiện tại và bước tiếp theo dự kiến.
- Given ticket đã được tạo, then **AI không tự phê duyệt hoàn tiền** — quyết định phê duyệt thuộc về tổng đài viên hoặc hệ thống nội bộ theo quy trình của AloSM.

---

### F8 — Hỗ trợ tài xế qua giọng nói (Should)

**Pain point giải quyết:** Tài xế cần thao tác điện thoại trong khi lái xe để xác nhận chuyến, cập nhật trạng thái hoặc tra cứu thông tin — gây nguy hiểm và không an toàn. Giọng nói cho phép tài xế tập trung lái xe.

**User stories**

1. Là tài xế, tôi muốn xác nhận đã đón khách hoặc hoàn thành chuyến bằng giọng nói khi đang lái.
2. Là tài xế, tôi muốn hỏi địa chỉ điểm đến hoặc thông tin liên lạc của khách mà không cần mở app.
3. Là tài xế, tôi muốn báo cáo sự cố (kẹt xe, khách hủy, sự cố xe) bằng giọng nói.

**AC**

- Given tài xế nói lệnh xác nhận ("Tôi đã đón khách" hoặc "Hoàn thành chuyến"), when AI nhận diện lệnh và xác minh có chuyến đang hoạt động, then AI xác nhận lại lệnh và cập nhật trạng thái chuyến trong hệ thống; AI đọc xác nhận kết quả cho tài xế.
- Given tài xế hỏi thông tin chuyến (điểm đến, thời gian dự kiến), when AI truy vấn hệ thống theo chuyến đang hoạt động của tài xế đã đăng nhập, then AI đọc thông tin ngắn gọn — **không đọc số điện thoại đầy đủ của khách**.
- Given tài xế báo cáo sự cố kẹt xe hoặc chậm trễ, when AI nhận thông tin, then AI ghi nhận vào hệ thống và thông báo cho khách (nếu phù hợp) về thời gian điều chỉnh dự kiến.
- Given tài xế báo cáo khách hủy hoặc không có mặt, when AI nhận xác nhận của tài xế, then AI xử lý theo quy trình hủy chuyến phía tài xế và thông báo kết quả.
- Given tình huống sự cố nghiêm trọng (tai nạn, hành khách có vấn đề sức khỏe), when tài xế báo cáo, then **chuyển ngay sang F9 (Emergency Response)**.

---

### F9 — Xử lý tình huống khẩn cấp và tai nạn (Must)

**Pain point giải quyết:** Khi xảy ra tai nạn hoặc tình huống nguy hiểm tính mạng, mọi giây đều quan trọng. AI cần phát hiện nhanh, ghi nhận đầy đủ và kết nối đúng người có thể xử lý ngay — không để khách hoặc tài xế phải tự tìm số điện thoại hay chờ hàng chờ thông thường.

**User stories**

1. Là khách hàng hoặc tài xế, tôi muốn AI nhận ra ngay khi tôi báo tai nạn và kết nối tôi với tổng đài viên có chuyên môn ngay lập tức.
2. Là khách hàng hoặc tài xế, tôi muốn thông tin sự cố của tôi được ghi lại đầy đủ trước khi chuyển tổng đài, để tôi không phải kể lại từ đầu.
3. Là tổng đài viên khẩn cấp, tôi muốn nhận ngay vị trí, thông tin chuyến và mô tả sự cố khi tiếp nhận cuộc gọi khẩn cấp.

**AC**

- Given người dùng nói các từ khóa khẩn cấp (tai nạn, cấp cứu, nguy hiểm, va chạm, bất tỉnh, v.v.) hoặc chuỗi từ gợi ý tình huống nguy hiểm tính mạng, when AI nhận diện được, then AI **ngắt toàn bộ quy trình hiện tại**, thông báo ngay "Tôi đang kết nối bạn với tổng đài khẩn cấp ngay bây giờ" và kích hoạt luồng khẩn cấp — **không hỏi thêm câu hỏi không cần thiết**.
- Given luồng khẩn cấp được kích hoạt, when trong vòng 30 giây, then tổng đài viên khẩn cấp được kết nối và nhận: vị trí GPS (nếu có), mã chuyến đang diễn ra, thông tin tài xế và khách, đoạn transcript mô tả sự cố.
- Given vị trí GPS có sẵn, when sự cố được báo cáo, then AI đính kèm tọa độ vào thông tin sự cố gửi cho tổng đài viên.
- Given tình huống có thể cần dịch vụ khẩn cấp bên ngoài (ambulance, cảnh sát), when tổng đài viên đánh giá cần thiết, then hệ thống hỗ trợ tổng đài viên kết nối với đầu số khẩn cấp (112) từ màn hình hỗ trợ — **AI không tự gọi 112**.
- Given sự cố đã được ghi nhận, then hệ thống tạo Emergency Incident Record với: thời gian, vị trí, mô tả ban đầu, trạng thái xử lý; record này chỉ tổng đài viên và Admin được xem.
- Given cuộc gọi khẩn cấp đang diễn ra, then hàng chờ thông thường **không chen vào** — cuộc gọi khẩn cấp có độ ưu tiên cao nhất.

---

## 6. Non-functional requirements

- **Dễ dùng (Usability):** Người dùng phổ thông bắt đầu cuộc gọi trong tối đa 3 thao tác từ trang chủ. Cỡ chữ tối thiểu 16px; nút bấm tối thiểu 44×44px. Hỗ trợ tăng cỡ chữ và giảm tốc độ giọng nói AI cho người lớn tuổi.
- **Độ tin cậy (Reliability):** Hệ thống không tạo booking trùng trong cùng phiên. Toàn bộ ngữ cảnh cuộc gọi được chuyển nguyên vẹn khi handoff. Khi AI gặp lỗi nội bộ, hệ thống hiển thị thông báo thân thiện — **không để lộ lỗi kỹ thuật**. Luồng khẩn cấp (F9) phải hoạt động kể cả khi các module khác đang lỗi.
- **Bảo mật & Riêng tư (Privacy & Security):** Ghi âm chỉ sau khi có đồng ý. Số điện thoại và PII không hiển thị đầy đủ. Thông tin thanh toán không đi qua AI — chỉ qua payment gateway đạt chuẩn bảo mật. Mỗi vai trò chỉ truy cập dữ liệu thuộc phạm vi.
- **Hiệu năng (Performance):** Trong vòng 500ms sau khi khách dừng nói, màn hình hiển thị chỉ báo "Đang xử lý". Luồng khẩn cấp kết nối tổng đài viên trong **≤ 30 giây**. Giao diện không bị đứng (freeze) trong khi AI xử lý.
- **Khả năng mở rộng (Scalability):** Kiến trúc hệ thống cho phép thêm kênh giao tiếp mới và nghiệp vụ mới qua cấu hình — không cần viết lại luồng xử lý cốt lõi.

---

## 7. Definition of Done

MVP được xem là hoàn thành khi:

1. Nhóm người dùng mục tiêu hoàn tất hành trình đầy đủ: **Gọi AI → Nói yêu cầu → AI hỏi và xác nhận thông tin → Thực hiện nghiệp vụ → Nhận kết quả**.
2. Toàn bộ **Must features (F1, F2, F3, F9) đạt đủ AC** được liệt kê tại mục 5.
3. Đạt các ngưỡng metric pilot tại mục 2: task completion ≥ 80%, AI resolution ≥ 65%, 100% handoff có context đầy đủ, 100% khẩn cấp kết nối trong ≤ 30 giây.

---

## 8. Open questions

| Câu hỏi cần chốt | Người quyết định | Hạn chót | Ảnh hưởng nếu chưa trả lời |
|---|---|---|---|
| Baseline vận hành thực tế của tổng đài: số cuộc gọi/ngày, cơ cấu loại yêu cầu, chi phí hiện tại? | PO, CS Manager | Trước sprint 1 | Không thể đặt KPI giảm tải và tính ROI thực tế |
| ASR tiếng Việt với người lớn tuổi, giọng địa phương và môi trường ồn ào có đạt ngưỡng chấp nhận không? | AI/ML | Trước R1 | Cần tăng cường fallback text hoặc thu hẹp phạm vi pilot |
| MVP kết nối với hệ thống đặt xe thật hay sandbox? | PO, Engineering | Trước R1 | Không thiết kế được luồng tạo booking và xử lý lỗi thực tế |
| Chính sách lưu trữ ghi âm và transcript: lưu bao lâu, ai được xem, xóa khi nào? | DPO, PO | Trước R1 | Không thiết kế được màn hình đồng ý và quy trình xóa dữ liệu |
| Ai có quyền xuất bản tài liệu lên kho tri thức? | PO, AI Ops | Trước grooming F5 | Không xây được luồng phê duyệt tài liệu |
| Giá ước tính lấy từ hệ thống nào và cập nhật theo chu kỳ nào? | PO, Business | Trước grooming F1 | Không xác định được nguồn dữ liệu giá cho F1 và F3 |
| MVP phục vụ khu vực địa lý nào? | PO, Business | Trước R1 | Không xác định phạm vi dữ liệu địa chỉ cần chuẩn bị |
| AloSM dùng payment gateway nào? API có sẵn chưa? Yêu cầu PCI-DSS cụ thể ra sao? | PO, Engineering, Finance | Trước grooming F6 | Không thiết kế được luồng thanh toán và chọn phương thức |
| Quy trình phê duyệt hoàn tiền: ai phê duyệt, thời gian xử lý, điều kiện tự động hoàn? | PO, CS Manager, Finance | Trước grooming F7 | Không thiết kế được luồng tạo ticket và thông báo kết quả |
| Khiếu nại đi vào hệ thống CRM nào? Tiêu chí phân loại mức ưu tiên là gì? | PO, CS Manager | Trước grooming F7 | Không thiết kế được luồng tạo ticket và điều phối |
| Tài xế: API endpoint nào cho xác nhận chuyến và cập nhật trạng thái? | Engineering | Trước grooming F8 | Không tích hợp được hành động của tài xế vào hệ thống |
| Quy trình leo thang khẩn cấp nội bộ: ai tiếp nhận, quy trình kết nối 112 cụ thể như thế nào? | PO, CS Manager, Legal | Trước grooming F9 | Không thiết kế được luồng kết nối khẩn cấp an toàn |

---

## 9. Sign-off

PRD chỉ chuyển từ **Draft → Approved** khi đủ 4 xác nhận.

| Vai trò | Phạm vi xác nhận | Người | Ngày | Trạng thái |
|---|---|---|---|---|
| Product Owner | Nội dung PRD đúng hướng kinh doanh; ưu tiên MoSCoW và metric pilot khả thi | — | — | ☐ Chờ ký |
| Tech Lead | Khả thi kỹ thuật trong capacity hiện tại: ASR, TTS, payment gateway, emergency integration | — | — | ☐ Chờ ký |
| CS Manager | Luồng nghiệp vụ tổng đài chính xác; luồng handoff, khiếu nại và khẩn cấp đúng thực tế vận hành | — | — | ☐ Chờ ký |
| Data Protection Officer | Đồng ý với cách xử lý PII, ghi âm, dữ liệu thanh toán và thông tin sự cố khẩn cấp | — | — | ☐ Chờ ký |

---

*Toàn bộ số liệu mục tiêu trong tài liệu này là **đề xuất cho giai đoạn pilot, chưa được xác minh bằng dữ liệu production**. Các con số sẽ được hiệu chỉnh sau khi có baseline vận hành thực tế từ AloSM.*
