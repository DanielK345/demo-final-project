# PRD — AloSM Voice: Đặt xe bằng giọng nói

**Phiên bản:** 0.4 · **Trạng thái:** Draft để xác thực với người dùng · **Primary persona:** Khách hàng ưu tiên tương tác bằng giọng nói

> Sản phẩm giúp khách hàng đặt xe, tra cứu chuyến đi và hỏi thông tin dịch vụ bằng giọng nói tiếng Việt qua hotline. AI xử lý các nghiệp vụ có quy trình cố định; con người tiếp nhận các tình huống khẩn cấp, phức tạp và cần phán đoán.

## 1. Problem statement

Ứng dụng di động của Alo SM đáp ứng phần lớn nhu cầu đặt xe, nhưng tổng đài 1555 vẫn quan trọng với một bộ phận lớn khách hàng. Tổng đài đang tiếp nhận khối lượng lớn yêu cầu lặp lại có quy trình chuẩn hóa: đặt xe, tra cứu trạng thái và giải đáp thông tin dịch vụ.

**Giả thuyết baseline cần kiểm chứng:** một bộ phận khách hàng không muốn hoặc không thể dùng app; gọi tổng đài viên để xử lý tác vụ chuẩn gây quá tải CSKH và tốn chi phí vận hành. Trước khi chốt PRD, cần thu thập dữ liệu lưu lượng cuộc gọi, cơ cấu yêu cầu (đặt xe / tra cứu / khiếu nại) và chi phí vận hành tổng đài từ nội bộ Alo SM.

### Pain points ưu tiên

| Pain point | Quy trình hiện tại → failure | Tác động | Root cause |
|---|---|---|---|
| Rào cản thao tác app di động | Khách mở app, nhập địa chỉ, xác nhận nhiều bước → thao tác phức tạp, dễ nhầm | Bỏ cuộc hoặc chuyển sang gọi hotline 1555 | Người lớn tuổi (11.86% dân số), ít quen công nghệ (chỉ 12.7% người 60+ truy cập Internet), hoặc đang bận tay |
| Quá tải tổng đài viên với tác vụ lặp lại | Khách gọi 1555 để đặt xe, hỏi giá, kiểm tra vị trí → tổng đài viên tiếp nhận thủ công | Quá tải lúc cao điểm; thời gian chờ lâu; chi phí vận hành tăng | Thiếu kênh tự động hóa bằng giọng nói xử lý quy trình tiêu chuẩn 24/7 |
| Mất ngữ cảnh khi chuyển tiếp sự cố | Khi AI chuyển sang tổng đài viên → khách phải trình bày lại từ đầu | Khách bức xúc, giảm trải nghiệm dịch vụ | Thiếu cơ chế tóm tắt ngữ cảnh hội thoại khi chuyển giao cuộc gọi |

Đây là pain point thực tế dựa trên bối cảnh xã hội: Việt Nam có 11.41 triệu người cao tuổi (2019); khảo sát Rakuten Insight (2025) cho thấy 66% đặt ô tô / 67% đặt xe máy qua app; Alo SM đạt hơn 1 triệu chuyến/ngày.

## 2. Goals & metrics

Trong pilot thử nghiệm với nhóm người dùng mục tiêu (người lớn tuổi, ít quen công nghệ, cần tương tác rảnh tay):

- Tỷ lệ hoàn thành đặt xe ≥ **80%** — số người hoàn tất kịch bản / tổng số người thử nghiệm.
- Tỷ lệ tự động hóa không lỗi ≥ **65%** — số yêu cầu hoàn tất không cần tổng đài viên / tổng yêu cầu hợp lệ.
- **100%** trường hợp out-of-scope hoặc thất bại 2 lần được chuyển tổng đài viên kèm tóm tắt.
- **100%** hành động đặt xe có xác nhận đồng ý bằng lời nói trước khi gửi API.

> ⚠️ **TODO:** Mục tiêu về độ trễ phản hồi (giây), ASR accuracy target và chỉ số giảm chi phí tổng đài sẽ bổ sung sau khi thiết lập baseline thực tế.

## 3. Persona

**Primary — Khách hàng ưu tiên tương tác bằng giọng nói:** người lớn tuổi, ít quen công nghệ, gặp khó khăn nhìn/nhập liệu trên màn hình cảm ứng, hoặc tạm thời bận tay (mang hành lý, bế con). Tương tác bằng câu nói ngắn, tự nhiên bằng tiếng Việt; cần xác nhận rõ ràng từng bước và tốc độ phản hồi vừa phải.

**Vai trò liên quan:** Đội ngũ tổng đài viên là người tiếp nhận cuộc gọi vượt khả năng AI (khiếu nại, tai nạn, sự cố thanh toán); cần nhận cuộc gọi kèm tóm tắt ngữ cảnh để xử lý ngay. Vai trò này không phải primary persona.

## 4. Input

| Chiều input | Phạm vi MVP |
|---|---|
| Loại | Luồng giọng nói tiếng Việt tự nhiên qua kênh tổng đài / điện thoại |
| Ngôn ngữ | Tiếng Việt phổ thông (giọng Bắc, Trung, Nam ở mức cơ bản) |
| Ngữ cảnh | Duy trì session memory: điểm đón, điểm đến, thông tin tra cứu |
| Phạm vi nghiệp vụ | Đặt xe tiêu chuẩn · Tra cứu trạng thái chuyến · Giải đáp FAQ dịch vụ & giá cước |
| Nguồn FAQ | Cơ sở dữ liệu thông tin dịch vụ, bảng giá, quy chế đã được Alo SM phê duyệt |
| Giới hạn pilot | Nhóm người dùng thử nghiệm thuộc persona chính |

## 5. Scope & priority

| Priority | Feature | Giá trị |
|---|---|---|
| **Must** | F1 — Đặt xe bằng giọng nói | Nghe, hiểu, thu thập điểm đón/đến, xác nhận, gửi lệnh đặt xe |
| **Must** | F2 — Chuyển tổng đài viên kèm tóm tắt | Tự động chuyển cuộc gọi khi thất bại/quá phạm vi, gửi kèm tóm tắt ngữ cảnh |
| **Must** | F3 — Tra cứu trạng thái chuyến đi | Phản hồi vị trí và trạng thái xe cho khách đã đặt |
| **Should** | F4 — Giải đáp FAQ | Trả lời tự động về giá cước tham khảo và thông tin dịch vụ |
| **Won't** | Thanh toán, hoàn tiền, xử lý giao dịch tài chính | Ngoài phạm vi MVP |
| **Won't** | Khiếu nại, tranh chấp, sự cố tai nạn | Chuyển thẳng tổng đài viên |
| **Won't** | Điều phối tài xế, thuật toán ghép chuyến | Do backend Alo SM xử lý |

## 6. Features & acceptance criteria

> **Quy ước:** Feature và AC ở cấp feature là phạm vi cam kết của PRD. Các user stories bên dưới chỉ là gợi ý phân rã, **không bắt buộc và chưa được chốt**; team sẽ refinement, bổ sung và chốt AC cấp story trong buổi grooming trước từng sprint.

### F1 — Đặt xe bằng giọng nói (Must)

**Pain point giải quyết:** đặt xe trên app phức tạp với người lớn tuổi/rảnh tay; đặt xe qua tổng đài viên tốn chi phí cho tác vụ chuẩn hóa.

**User stories**

1. Là khách hàng, tôi muốn nói nhu cầu bằng tiếng Việt tự nhiên để AI hiểu và thực hiện thay vì phải bấm màn hình.
2. Là khách hàng, tôi muốn AI ghi nhớ điểm đón đã nói trước đó để tôi không phải nhắc lại ở câu sau.
3. Là khách hàng, tôi muốn AI đọc lại thông tin chuyến đi để tôi xác nhận "Đúng" trước khi đặt xe.
4. Là khách hàng, tôi muốn được thông báo ngay khi đặt xe thành công.

**AC**

- Given người dùng phát biểu bằng tiếng Việt, when truyền âm thanh tới hệ thống, then ASR chuyển thành văn bản và AI trích xuất đúng ý định cùng điểm đón/đến.
- Given người dùng đã nói "đón tôi ở Vincom Đồng Khởi" ở lượt trước, when nói "đi Landmark 81" ở lượt sau, then AI tổng hợp cả 2 điểm mà KHÔNG hỏi lại điểm đón.
- AI phải thu thập đủ **điểm đón** và **điểm đến**, đọc xác nhận rõ ràng, và chỉ gọi API khi nhận xác nhận đồng ý.
- Nếu địa điểm mơ hồ (>1 kết quả Geocoding), AI liệt kê ít nhất 2 phương án cho khách chọn.
- Given ASR nhận diện thất bại 2 lần liên tiếp, then AI kích hoạt chuyển tổng đài viên (F2).
- Given người dùng chưa cung cấp thông tin, then AI KHÔNG tự suy diễn mà phải hỏi lại.
- Given người dùng nói "Thôi, không đặt nữa", then AI hủy yêu cầu — KHÔNG gọi API.
- Mỗi yêu cầu đặt xe phải kèm idempotency key để tránh tạo booking trùng.

### F2 — Chuyển tổng đài viên kèm tóm tắt (Must)

**Pain point giải quyết:** khách bực mình khi AI không hiểu nhưng không gặp được con người; hoặc gặp tổng đài viên phải nhắc lại từ đầu.

**User stories**

1. Là khách hàng, tôi muốn gặp tổng đài viên bất kỳ lúc nào tôi yêu cầu.
2. Là tổng đài viên, tôi muốn xem tóm tắt cuộc hội thoại AI để hỗ trợ khách tức thì.

**AC**

- Khi gặp ASR thất bại 2 lần, ngoài phạm vi (khiếu nại, thanh toán, tai nạn) hoặc khách yêu cầu → chuyển tổng đài viên kèm tóm tắt.
- Tóm tắt chứa: lý do chuyển, thông tin đã thu thập (điểm đón/đến nếu có), nội dung trao đổi chính.
- AI thông báo rõ cho khách trước khi chuyển: "Em xin phép chuyển cuộc gọi đến tổng đài viên ạ".
- Tổng đài viên nhận cuộc gọi kèm tóm tắt hiển thị trên màn hình Agent Desktop.
- Nếu telephony lỗi, AI KHÔNG ngắt cuộc gọi đột ngột mà thông báo lỗi.

### F3 — Tra cứu trạng thái chuyến đi (Must)

**Pain point giải quyết:** khách phải chờ giữ máy tổng đài chỉ để hỏi xe đang ở đâu.

**User stories**

1. Là khách hàng đã đặt xe, tôi muốn hỏi vị trí xe để biết khi nào tài xế tới đón.

**AC**

- Given khách hỏi "Xe tôi đặt đã đến chưa?", when AI truy vấn Trip Status API, then phản hồi thời gian dự kiến.
- Thông tin chuyến đi chỉ cung cấp cho đúng số điện thoại / phiên gọi của khách.
- Given không tìm thấy chuyến đi nào, then AI thông báo rõ: "Không tìm thấy chuyến đi đang hoạt động".

### F4 — Giải đáp FAQ (Should)

**Pain point giải quyết:** khách gọi tổng đài để hỏi giá cước hoặc thông tin dịch vụ — tốn thời gian chờ tổng đài viên.

**User stories**

1. Là khách hàng, tôi muốn hỏi giá cước hoặc thông tin dịch vụ để cân nhắc sử dụng.

**AC**

- FAQ chỉ trả lời dựa trên bộ tri thức đã được Alo SM phê duyệt, không dùng nguồn ngoài.
- Khi không có câu trả lời, AI báo "Chưa có thông tin" và đề nghị chuyển tổng đài viên — KHÔNG tự bịa.

## 7. Non-functional requirements

- **Bảo mật & PII:** Mã hóa PII (SĐT, địa chỉ) AES-256 trong storage và TLS 1.2+ khi truyền; không lưu âm thanh cuộc gọi dạng plaintext; masked SĐT (`090*****89`) trong log; file ghi âm tự hủy theo chính sách bảo mật dữ liệu.
- **Độ tin cậy & HITL (Human-in-the-Loop):** Khi ASR nhận diện kém (≥ 2 lần), yêu cầu phức tạp ngoài phạm vi, hoặc API backend lỗi → chuyển mượt mà sang tổng đài viên kèm bản tóm tắt ngữ cảnh; tỷ lệ call drop < 1%.
- **Độ trễ hội thoại & Barge-in:** Hỗ trợ ngắt lời tự nhiên (Barge-in / Voice Activity Detection) khi khách nói chen ngang; mục tiêu độ trễ phản hồi giọng nói (voice-to-voice) tối ưu ≤ 2.5s.
- **Độ chính xác STT & Xác nhận địa chỉ:** STT nhận diện tốt phương ngữ tiếng Việt phổ thông; địa chỉ mơ hồ phải qua bước xác nhận/làm rõ Geocoding; 100% lệnh đặt xe phải có xác nhận bằng lời nói (BR-001).
- **Kiểm soát chi phí STT/TTS & LLM:** Sử dụng prompt ngắn gọn, cache các audio TTS tĩnh (lời chào, xác nhận mẫu); cơ chế ngắt stream sớm (VAD) khi khách im lặng để tối ưu chi phí token và speech computing.
- **Đánh giá AI:** Booking Completion Rate ≥ 80% và Unassisted Automation Rate ≥ 65% trên bộ test pilot.
- **Accessibility:** AI phản hồi bằng câu ngắn (≤ 30 từ), tốc độ vừa phải cho người lớn tuổi.
- **Logging:** Log mọi cuộc gọi: timestamp, intent, entities, action, handoff reason — structured JSON, không chứa SĐT/địa chỉ raw.

## 8. Definition of Done

MVP done khi nhóm pilot hoàn thành hành trình **gọi điện → nói nhu cầu → AI hiểu và xác nhận → đặt xe thành công hoặc chuyển tổng đài viên**, toàn bộ **Must features (F1–F3) đạt AC cấp feature ở mục 6** và đạt các metric ở mục 2.

## 9. Open questions

| Câu hỏi cần chốt | Owner | Hạn |
|---|---|---|
| Dữ liệu baseline lưu lượng cuộc gọi 1555 và chi phí vận hành? | PO / CSKH | Trước Sprint 1 |
| Dịch vụ xe mặc định (Taxi 4 chỗ, 7 chỗ, Luxury, Bike) khi đặt qua giọng nói? | PO | Trước grooming F1 |
| Chuẩn tích hợp dữ liệu tóm tắt lên màn hình Tổng đài viên? | Tech Lead | Trước grooming F2 |
| Ngưỡng confidence threshold của ASR? | AI Team | Trước Sprint 1 |
| Silence timeout (giây)? | AI Team | Trước Sprint 1 |
| Quy định ghi âm, bảo mật PII và thời hạn giữ transcript? | Legal | Trước UAT |
| Cho phép barge-in (người dùng nói chen khi AI đang phát) không? | PO | Trước Sprint 1 |
| Xử lý khi tổng đài viên không available tại thời điểm Handoff? | PO / CSKH | Trước grooming F2 |
| Booking API SLA (timeout, rate limit) từ Alo SM backend? | Tech Lead | Trước Sprint 1 |

## 10. Sign-off

PRD chỉ chuyển từ **Draft → Approved** khi đủ 3 xác nhận dưới đây. Mỗi người ký xác nhận đúng phạm vi trách nhiệm của mình.

| Vai trò | Phạm vi xác nhận | Người | Ngày | Trạng thái |
|---|---|---|---|---|
| PO | Nội dung, ưu tiên MoSCoW, tiêu chí pilot | — | — | ☐ Chờ ký |
| Tech Lead | Khả thi kỹ thuật (ASR, NLU, TTS, tích hợp Booking API & SIP) | — | — | ☐ Chờ ký |
| Head of CSKH | Đúng quy trình nghiệp vụ tổng đài, kịch bản Human Handoff | — | — | ☐ Chờ ký |
