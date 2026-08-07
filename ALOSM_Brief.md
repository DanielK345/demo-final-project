# PRODUCT BRIEF
## GreenSM Voice
**AI Voice Customer Service Agent for Green SM**
Prepared by: Team T160

---

## Project Vision
**Nói một câu, Green SM lo phần còn lại.**

GreenSM Voice hướng đến việc trở thành cổng giao tiếp bằng hội thoại cho hệ sinh thái Green SM, giúp khách hàng tiếp cận dịch vụ một cách tự nhiên, thuận tiện và toàn diện thông qua giọng nói; đồng thời hỗ trợ doanh nghiệp tối ưu quy trình chăm sóc khách hàng và nâng cao hiệu quả vận hành.

## 1. Project Overview

### Background
Ngành dịch vụ đang chuyển dịch mạnh từ các giao diện tương tác truyền thống sang các giải pháp Conversational AI. Thay vì yêu cầu người dùng thực hiện nhiều thao tác trên màn hình hoặc tuân theo các quy trình phức tạp, doanh nghiệp ngày càng hướng đến việc cho phép khách hàng giao tiếp bằng ngôn ngữ tự nhiên thông qua giọng nói.

Xu hướng này đặc biệt phù hợp với các doanh nghiệp có quy mô khách hàng lớn và hệ thống chăm sóc khách hàng hoạt động liên tục như ngân hàng, hàng không, bảo hiểm và dịch vụ gọi xe. AI Voice có thể tiếp nhận các yêu cầu phổ biến, tự động hóa quy trình hỗ trợ và giảm tải cho tổng đài viên.

Đối với Green SM, ứng dụng di động đã đáp ứng phần lớn nhu cầu đặt xe, nhưng tổng đài vẫn giữ vai trò quan trọng đối với nhiều nhóm khách hàng. Doanh nghiệp đồng thời phải xử lý nhiều yêu cầu lặp lại như đặt xe, tra cứu chuyến đi và giải đáp thông tin dịch vụ. Đây là cơ hội để Green SM bổ sung một kênh tương tác bằng giọng nói, nâng cao khả năng tiếp cận dịch vụ và tối ưu hoạt động chăm sóc khách hàng.

### Why Now?
Việt Nam có tỷ lệ sử dụng smartphone cao, nhưng khả năng tiếp cận dịch vụ số giữa các nhóm người dùng vẫn chưa đồng đều. Tổng điều tra Dân số và Nhà ở 2019 ghi nhận Việt Nam có **11,41 triệu người từ 60 tuổi trở lên**, tương đương **11,86% dân số** [1]. Trong khi đó, nghiên cứu LSAHV do ERIA và PHAD công bố năm 2020, dựa trên mẫu 6.050 người từ 60 tuổi trở lên tại 10 tỉnh, cho thấy chỉ **12,7% người cao tuổi được khảo sát có khả năng truy cập Internet**; tỷ lệ này giảm từ 17,0% ở nhóm 60–69 tuổi xuống còn 2,8% ở nhóm từ 80 tuổi trở lên [2]. Những số liệu này cho thấy khả năng tiếp cận công nghệ giữa các nhóm tuổi vẫn có sự chênh lệch đáng kể và củng cố nhu cầu về những phương thức tương tác đơn giản, trực quan hơn.

Song song đó, nhu cầu gọi xe qua nền tảng số đã phổ biến. Khảo sát Rakuten Insight năm 2025 ghi nhận **66% người trả lời từng đặt ô tô, 67% từng đặt xe máy** qua ứng dụng và Xanh SM là thương hiệu được sử dụng thường xuyên nhất bởi 32% người trả lời [3]. Green SM cũng công bố quy mô hơn **1 triệu chuyến mỗi ngày**, hơn 100 triệu lượt khách đã sử dụng dịch vụ và hotline 1555 [4]. Trong bối cảnh nhu cầu gọi xe số phát triển nhưng khả năng tiếp cận công nghệ chưa đồng đều, đây là thời điểm phù hợp để Green SM đánh giá AI Voice như một kênh bổ sung cho ứng dụng và tổng đài truyền thống.

## 2. Business Problem

Green SM đã xây dựng một hệ sinh thái dịch vụ hiện đại với ứng dụng di động là kênh tương tác chính. Tuy nhiên, vẫn còn khoảng trống trong trải nghiệm của một bộ phận khách hàng và trong cách doanh nghiệp vận hành tổng đài chăm sóc khách hàng.

Từ góc độ người dùng, không phải tất cả khách hàng đều muốn hoặc có thể sử dụng ứng dụng di động. Người lớn tuổi, người ít thành thạo công nghệ hoặc người đang cần thao tác rảnh tay thường ưu tiên giao tiếp bằng giọng nói. Với họ, việc nói “Tôi muốn đặt một xe từ Vincom Đồng Khởi về Landmark 81” tự nhiên và thuận tiện hơn so với việc mở ứng dụng, nhập địa chỉ và thực hiện từng bước đặt xe.

Từ góc độ doanh nghiệp, tổng đài phải tiếp nhận các yêu cầu như đặt xe, tra cứu trạng thái chuyến đi, giải đáp thông tin dịch vụ và hướng dẫn khách hàng. Nhiều nghiệp vụ có quy trình tương đối chuẩn hóa và là ứng viên phù hợp cho tự động hóa. Tuy nhiên, Green SM chưa công bố lưu lượng cuộc gọi, tỷ trọng từng loại yêu cầu hoặc chi phí vận hành tổng đài; các số liệu này cần được dùng làm baseline nội bộ trước khi đánh giá tác động kinh doanh của MVP.

Trong khi đó, tổng đài viên nên tập trung vào các tình huống cần đánh giá, xử lý linh hoạt hoặc ra quyết định của con người như khiếu nại, tranh chấp và các trường hợp đặc biệt.

**Problem Statement**
Làm thế nào để Green SM mở rộng khả năng tiếp cận dịch vụ thông qua hội thoại bằng giọng nói, đồng thời tự động hóa các nghiệp vụ tiêu chuẩn nhằm giảm tải cho tổng đài viên, tối ưu nguồn lực vận hành và nâng cao trải nghiệm khách hàng, nhưng vẫn đảm bảo những tình huống phức tạp được xử lý bởi con người?

## 3. Target Users

### Primary Users
GreenSM Voice được thiết kế cho những khách hàng ưu tiên hoặc cần tương tác bằng giọng nói thay vì thao tác trên ứng dụng, bao gồm:
* Người lớn tuổi chưa quen sử dụng ứng dụng đặt xe.
* Người ít thành thạo công nghệ.
* Người gặp khó khăn khi thao tác trên điện thoại.

Đây là persona chính của MVP. Hội thoại cần sử dụng câu ngắn, tốc độ vừa phải và xác nhận rõ các thông tin quan trọng, thay vì yêu cầu người dùng ghi nhớ và thực hiện nhiều bước trên giao diện ứng dụng.

### Secondary Users
Người cần tương tác rảnh tay, chẳng hạn khi đang mang hành lý hoặc bế trẻ nhỏ, là persona phụ: họ có thể thành thạo công nghệ nhưng tạm thời không thuận tiện dùng màn hình. Đội ngũ tổng đài viên cũng là nhóm người dùng thứ cấp của giải pháp. GreenSM Voice sẽ tiếp nhận và xử lý trước các yêu cầu có quy trình rõ ràng, giúp tổng đài viên tập trung vào những trường hợp cần hỗ trợ chuyên sâu. Qua đó, doanh nghiệp có thể nâng cao hiệu quả làm việc và cải thiện chất lượng chăm sóc khách hàng.

### Core Values

**Accessibility**
Giúp nhiều nhóm khách hàng tiếp cận dịch vụ dễ dàng hơn thông qua giọng nói.

**Convenience**
Đơn giản hóa quá trình sử dụng dịch vụ bằng hội thoại tự nhiên.

**Operational Efficiency**
Tự động hóa các nghiệp vụ chuẩn hóa nhằm giảm tải tổng đài và tối ưu nguồn lực.

**Human-Centered AI**
AI hỗ trợ con người thay vì thay thế con người; các tình huống phức tạp được chuyển đến tổng đài viên.

## 4. Proposed Solution

GreenSM Voice là một AI Voice Customer Service Agent cho phép khách hàng tương tác với các dịch vụ Green SM bằng tiếng Việt tự nhiên. Sản phẩm đóng vai trò là lớp giao tiếp thông minh giữa khách hàng và hệ thống nghiệp vụ, không phải một ứng dụng gọi xe mới hay một chatbot thay thế hoàn toàn con người.

Người dùng chỉ cần trình bày nhu cầu bằng giọng nói. AI sẽ tiếp nhận yêu cầu, duy trì ngữ cảnh, thu thập và xác nhận thông tin cần thiết, thực hiện nghiệp vụ phù hợp và phản hồi kết quả. Khi yêu cầu vượt ngoài phạm vi xử lý hoặc cần đánh giá của con người, hệ thống sẽ chuyển tiếp cuộc hội thoại đến tổng đài viên theo mô hình Human-in-the-Loop.

### Product Principles

**Voice First**
Giọng nói là phương thức tương tác chính, cho phép người dùng tiếp cận dịch vụ bằng hội thoại tự nhiên.

**Human-Centered AI**
AI xử lý các nghiệp vụ tiêu chuẩn; con người tiếp nhận những tình huống cần phán đoán hoặc hỗ trợ chuyên sâu.

**Reliable Automation**
Hệ thống chỉ tự động hóa những nghiệp vụ có quy trình rõ ràng, có thể kiểm soát và xác nhận.

**Continuous Conversation**
AI duy trì ngữ cảnh trong nhiều lượt trao đổi, ghi nhớ thông tin trong phiên và phản hồi nhất quán.

### Core Capabilities
Trong phạm vi MVP, GreenSM Voice tập trung vào bốn năng lực chính:
* **Booking Services:** thu thập và xác nhận điểm đón, điểm đến, sau đó thực hiện quy trình đặt xe.
* **Information Services:** tra cứu trạng thái chuyến đi, thông tin dịch vụ, giá tham khảo và các câu hỏi thường gặp.
* **Conversation Management:** duy trì ngữ cảnh, xử lý hội thoại nhiều lượt và xác nhận thông tin quan trọng.
* **Human Handoff:** chuyển tiếp cuộc hội thoại đến tổng đài viên khi người dùng yêu cầu trực tiếp, sau hai lần nhận diện hoặc xác nhận thất bại, khi độ tin cậy thấp, hoặc khi xuất hiện tình huống nhạy cảm như khiếu nại, thanh toán hay tai nạn. Tổng đài viên nhận được tóm tắt và các thông tin đã xác nhận để khách hàng không phải trình bày lại từ đầu.

## 5. Project Scope

MVP tập trung vào những nghiệp vụ có quy trình rõ ràng và khả năng tự động hóa cao, nhằm kiểm chứng giá trị cốt lõi của sản phẩm trong phạm vi khả thi.

**In Scope**
* Tiếp nhận và phản hồi hội thoại bằng giọng nói tiếng Việt.
* Hiểu ý định và duy trì ngữ cảnh trong nhiều lượt trao đổi.
* Đặt xe.
* Tra cứu trạng thái chuyến đi.
* Giải đáp thông tin dịch vụ và câu hỏi thường gặp.
* Xác nhận thông tin quan trọng trước khi thực hiện nghiệp vụ.
* Lưu lịch sử hội thoại trong phiên.
* Chuyển tiếp tổng đài viên khi cần.

**Out of Scope**
* Thanh toán, hoàn tiền và xử lý giao dịch.
* Khiếu nại, tranh chấp và đánh giá trách nhiệm.
* Điều phối tài xế hoặc can thiệp vào thuật toán ghép chuyến.
* Tai nạn, tình huống khẩn cấp và các trường hợp đặc biệt.

GreenSM Voice không hướng đến việc thay thế tổng đài viên. MVP chỉ chứng minh rằng AI có thể tự động hóa hiệu quả các nghiệp vụ tiêu chuẩn, giúp con người tập trung vào những tình huống cần chuyên môn và khả năng đánh giá.

## 6. Expected Outcome

Sau khi hoàn thành MVP, dự án kỳ vọng chứng minh rằng AI Voice có thể trở thành một kênh tương tác hiệu quả trong hệ sinh thái Green SM.

**Customer Value**
Khách hàng có thêm phương thức tiếp cận dịch vụ đơn giản và tự nhiên, đặc biệt đối với người ít thành thạo công nghệ hoặc không thuận tiện sử dụng ứng dụng.

**Business Value**
Green SM có thể tự động hóa các nghiệp vụ tiêu chuẩn, giảm tải tổng đài, chuẩn hóa quy trình hỗ trợ và tăng khả năng phục vụ đồng thời.

**Operational Value**
Tổng đài viên được giảm bớt công việc lặp lại và có thể tập trung vào những trường hợp cần chuyên môn hoặc xử lý linh hoạt.

**Technical Validation**
MVP đóng vai trò Proof of Concept, chứng minh khả năng hiểu hội thoại tiếng Việt, duy trì ngữ cảnh, thực hiện nghiệp vụ và phối hợp với tổng đài viên theo mô hình Human-in-the-Loop.

**Success Criteria**
Trong pilot với đúng nhóm người dùng mục tiêu, MVP được xem là đạt mục tiêu ban đầu khi:
* Tối thiểu 80% người tham gia hoàn tất đúng kịch bản đặt xe bằng giọng nói.
* Tối thiểu 65% yêu cầu hợp lệ được hoàn tất không cần tổng đài viên và không xảy ra lỗi ở điểm đón, điểm đến hoặc hành động đặt xe.

Đây là ngưỡng mục tiêu cần kiểm chứng trong pilot, không phải kết quả đã đạt. Tác động giảm tải hoặc giảm chi phí chỉ được đánh giá sau khi có baseline vận hành thực tế của Green SM.

## 7. Risks and Open Questions

* Độ chính xác ASR tiếng Việt với người lớn tuổi, giọng vùng miền và tiếng ồn ngoài đường.
* Độ trễ hội thoại và khả năng nhận diện, xác nhận chính xác địa chỉ.
* Khả năng tích hợp với hệ thống đặt xe và chuyển tổng đài mà không đặt trùng hoặc báo thành công sai.
* Lưu lượng, cơ cấu yêu cầu và chi phí tổng đài hiện tại của Green SM chưa có dữ liệu công khai.
* Chính sách ghi âm, lưu transcript và bảo vệ số điện thoại, địa chỉ của khách hàng.

## 8. Future Direction

Nếu MVP chứng minh được tính khả thi, GreenSM Voice có thể được mở rộng theo các hướng sau:
* Bổ sung nghiệp vụ hủy chuyến, báo mất đồ, tiếp nhận phản ánh, hỗ trợ khuyến mãi và khách hàng doanh nghiệp.
* Triển khai trên nhiều kênh như tổng đài, ứng dụng Green SM, website và kiosk tự phục vụ.
* Cá nhân hóa trải nghiệm, ghi nhớ lịch sử tương tác, hỗ trợ đa ngôn ngữ và cải thiện khả năng hiểu hội thoại tự nhiên.
* Phát triển thành lớp giao tiếp bằng hội thoại thống nhất cho nhiều dịch vụ trong hệ sinh thái Green SM.

GreenSM Voice được định vị là một AI Voice Customer Service Agent, đóng vai trò như lớp giao tiếp thông minh giữa khách hàng và hệ thống dịch vụ Green SM. Sản phẩm kết hợp tự động hóa với Human-in-the-Loop nhằm mở rộng khả năng tiếp cận dịch vụ, nâng cao trải nghiệm khách hàng và tối ưu hiệu quả vận hành.

## Tài liệu tham khảo

[1] Tổng cục Thống kê và UNFPA Việt Nam (2021), *Population Ageing and Older Persons in Viet Nam*. https://vietnam.unfpa.org/sites/default/files/pub-pdf/ageing_report_from_census_2019_eng_final27082021.pdf

[2] Vu, N.C., Tran, M.T., Dang, L.T., Chei, C.L. và Saito, Y. (chủ biên) (2020), *Ageing and Health in Viet Nam*. Jakarta: Economic Research Institute for ASEAN and East Asia (ERIA); Hà Nội: Institute of Population, Health and Development (PHAD). https://www.eria.org/uploads/media/Books/2020-Ageing-and-Health-VietNam/Ageing-and-Health-in-Viet-Nam-new.pdf

[3] Rakuten Insight Global (2025), *2025 Ride-Hailing App Landscape in Vietnam*. https://insight.rakuten.com/2025-ride-hailing-app-landscape-in-vietnam/

[4] Green SM, số liệu doanh nghiệp công bố, truy cập ngày 02/08/2026. https://www.greensm.com/vn-vi
