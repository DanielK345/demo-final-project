# AloSM Voice AI Agent
## Product Requirements Document

> "Nói một câu, AloSM lo phần còn lại."

---

| **Thuộc tính** | **Giá trị** |
|---|---|
| **Phiên bản** | 1.0 |
| **Trạng thái** | Draft for Review |
| **Ngày** | 02/08/2026 |
| **Đối tượng** | PO, BA, UX/UI, Dev, Stakeholders |
| **Chuẩn bị bởi** | AloSM Product & BA Team (tham khảo GreenSM Voice PB) |
| **Bảo mật** | Nội bộ - Không phân phối bên ngoài |

---

*Tài liệu này mở rộng từ GreenSM Voice Product Brief (Team T160) thành PRD đầy đủ phục vụ phát triển sản phẩm AloSM.*


# Lịch sử phiên bản tài liệu

| **Phiên bản** | **Ngày** | **Người cập nhật** | **Nội dung thay đổi** | **Trạng thái** |
|-|-|-|-|-|
| 1.0 | 02/08/2026 | AloSM Product Team | Khởi tạo PRD đầy đủ từ GreenSM Voice Product Brief; bổ sung FR (45+), US (30+), UAT, Release Plan, Open Questions |  |

# Bảng phê duyệt

| **Vai trò** | **Người phụ trách** | **Trạng thái** | **Ngày** | **Ghi chú** |
|-|-|-|-|-|
| Product Owner | [Chờ xác nhận] |  | - | Xác nhận phạm vi MVP và ưu tiên |
| Business Analyst | [Chờ xác nhận] |  | - | Xác nhận FR và business rules |
| CS Manager | [Chờ xác nhận] |  | - | Xác nhận luồng handoff và operator |
| AI/ML Lead | [Chờ xác nhận] |  | - | Xác nhận tính khả thi ASR/TTS |
| Engineering Lead | [Chờ xác nhận] |  | - | Xác nhận phụ thuộc kỹ thuật |
| Data Protection Officer | [Chờ xác nhận] |  | - | Xác nhận privacy và consent |
| Ban lãnh đạo | [Chờ xác nhận] |  | - | Phê duyệt chiến lược và ngân sách |

# Bảng viết tắt và thuật ngữ

| **Thuật ngữ** | **Định nghĩa** |
|-|-|
| AI Voice Agent | Hệ thống trí tuệ nhân tạo tương tác qua giọng nói - trong tài liệu này là AloSM Voice AI Agent |
| ASR | Automatic Speech Recognition - Nhận diện giọng nói tự động |
| TTS | Text-to-Speech - Chuyển văn bản thành giọng nói |
| STT | Speech-to-Text - Chuyển giọng nói thành văn bản |
| RAG | Retrieval-Augmented Generation - Sinh câu trả lời có tham chiếu tri thức |
| LLM | Large Language Model - Mô hình ngôn ngữ lớn |
| NLU | Natural Language Understanding - Hiểu ngôn ngữ tự nhiên |
| HITL | Human-In-The-Loop - Quy trình chuyển từ AI sang người thật |
| KB | Knowledge Base - Kho tri thức |
| MVP | Minimum Viable Product - Sản phẩm khả dụng tối thiểu |
| FR | Functional Requirement - Yêu cầu chức năng |
| BR | Business Rule - Quy tắc nghiệp vụ |
| UAT | User Acceptance Testing - Kiểm thử chấp nhận người dùng |
| PO | Product Owner |
| BA | Business Analyst |
| CSAT | Customer Satisfaction Score - Chỉ số hài lòng khách hàng |
| KPI | Key Performance Indicator - Chỉ số hiệu suất chính |
| MoSCoW | Must / Should / Could / Won't (khung ưu tiên) |
| Booking | Đơn đặt xe đã được tạo trong hệ thống |
| Handoff | Chuyển tiếp cuộc gọi từ AI sang tổng đài viên |
| Operator | Tổng đài viên - nhân viên tiếp nhận cuộc gọi hỗ trợ khách hàng |
| Conversational AI | Hệ thống AI tương tác bằng ngôn ngữ tự nhiên (giọng nói hoặc văn bản) |
| Pilot | Giai đoạn thử nghiệm với nhóm người dùng kiểm soát trước khi mở rộng |
| Baseline | Dữ liệu vận hành hiện tại dùng làm mốc so sánh đánh giá tác động |
| JTBD | Jobs To Be Done - Công việc người dùng cần hoàn thành |
| DOR | Definition of Ready - Tiêu chí sẵn sàng phát triển |
| DOD | Definition of Done - Tiêu chí hoàn thành |
| PII | Personally Identifiable Information - Thông tin nhận dạng cá nhân |
| GWT | Given-When-Then - Cấu trúc viết acceptance criteria |

# Executive Summary

**AloSM Voice AI Agent** là hệ thống trợ lý hội thoại thông minh cho phép khách hàng tương tác với dịch vụ AloSM bằng tiếng Việt tự nhiên. Sản phẩm đóng vai trò là lớp giao tiếp thông minh giữa khách hàng và hệ thống nghiệp vụ - không phải một ứng dụng gọi xe mới hay một chatbot thay thế hoàn toàn con người.

> **Tầm nhìn sản phẩm**

> 
>     > "Nói một câu, AloSM lo phần còn lại.''"
>   
>   
>   AloSM Voice AI Agent hướng tới trở thành **cổng giao tiếp bằng hội thoại** cho hệ sinh thái dịch vụ AloSM - giúp khách hàng tiếp cận dịch vụ một cách tự nhiên, thuận tiện và toàn diện thông qua giọng nói; đồng thời hỗ trợ doanh nghiệp tối ưu quy trình chăm sóc khách hàng và nâng cao hiệu quả vận hành.

## Sản phẩm là gì

Người dùng chỉ cần trình bày nhu cầu bằng giọng nói. AI sẽ tiếp nhận yêu cầu, duy trì ngữ cảnh, thu thập và xác nhận thông tin cần thiết, thực hiện nghiệp vụ phù hợp và phản hồi kết quả. Khi yêu cầu vượt ngoài phạm vi xử lý hoặc cần đánh giá của con người, hệ thống sẽ chuyển tiếp cuộc hội thoại đến tổng đài viên theo mô hình Human-in-the-Loop.

## Bốn năng lực cốt lõi (Core Capabilities)

  - **Booking Services:** Thu thập và xác nhận điểm đón, điểm đến, sau đó thực hiện quy trình đặt xe.
  - **Information Services:** Tra cứu trạng thái chuyến đi, thông tin dịch vụ, giá tham khảo và các câu hỏi thường gặp.
  - **Conversation Management:** Duy trì ngữ cảnh, xử lý hội thoại nhiều lượt và xác nhận thông tin quan trọng.
  - **Human Handoff:** Chuyển tiếp cuộc hội thoại đến tổng đài viên khi người dùng yêu cầu trực tiếp, sau hai lần nhận diện hoặc xác nhận thất bại, khi độ tin cậy thấp, hoặc khi xuất hiện tình huống nhạy cảm (khiếu nại, thanh toán, tai nạn). Tổng đài viên nhận được tóm tắt và các thông tin đã xác nhận.

## Đối tượng sử dụng chính

  - **Khách hàng (Primary):** Người lớn tuổi chưa quen app, người ít thành thạo công nghệ, người gặp khó khăn khi thao tác trên thiết bị.
  - **Khách hàng (Secondary):** Người cần rảnh tay (mang hành lý, bế trẻ nhỏ); người dùng app thành thạo nhưng muốn tiện lợi hơn.
  - **Tổng đài viên (Operator):** Tiếp nhận các cuộc gọi phức tạp được chuyển từ AI, xử lý các trường hợp cần chuyên môn.
  - **Tài xế:** Nhận và cập nhật trạng thái chuyến từ hệ thống booking.
  - **Quản trị viên / AI Operations:** Quản lý cấu hình Agent, nội dung tri thức và chất lượng dịch vụ.

## Kết quả mong đợi sau MVP

  - Chứng minh AI Voice có thể tự động hóa hiệu quả các nghiệp vụ tiêu chuẩn (đặt xe, tra cứu, FAQ).
  - Thiết lập baseline để đo lường tỉ lệ hoàn thành tác vụ và chất lượng hội thoại.
  - Xác nhận mức độ chấp nhận của người dùng trước khi mở rộng kênh.
  - Nền tảng để phát triển thêm tính năng và mở rộng sang điện thoại, app mobile, kiosk.

# Bối cảnh và Cơ hội sản phẩm

## Bối cảnh thị trường

Ngành dịch vụ đang chuyển dịch mạnh từ các giao diện tương tác truyền thống sang các giải pháp Conversational AI. Thay vì yêu cầu người dùng thực hiện nhiều thao tác trên màn hình hoặc tuân theo các quy trình phức tạp, doanh nghiệp ngày càng hướng đến việc cho phép khách hàng giao tiếp bằng ngôn ngữ tự nhiên thông qua giọng nói.

Xu hướng này đặc biệt phù hợp với các doanh nghiệp có quy mô khách hàng lớn và hệ thống chăm sóc khách hàng hoạt động liên tục như ngân hàng, hàng không, bảo hiểm và dịch vụ gọi xe. AI Voice có thể tiếp nhận các yêu cầu phổ biến, tự động hóa quy trình hỗ trợ và giảm tải cho tổng đài viên.

## Tại sao đây là thời điểm phù hợp? (Why Now?)

Việt Nam có tỷ lệ sử dụng smartphone cao, nhưng khả năng tiếp cận dịch vụ số giữa các nhóm người dùng vẫn chưa đồng đều - tạo nên nhu cầu thực sự cho kênh giọng nói:

  - **Dân số cao tuổi lớn và tăng nhanh:** Tổng điều tra Dân số 2019 ghi nhận Việt Nam có **11,41 triệu người từ 60 tuổi trở lên** (11,86\% dân số). Đây là nhóm người dùng ưu tiên kênh giọng nói hơn ứng dụng.
  - **Khoảng cách số với người cao tuổi:** Nghiên cứu LSAHV (ERIA và PHAD, 2020) trên mẫu 6.050 người từ 60 tuổi cho thấy chỉ **12,7\%** có khả năng truy cập Internet - giảm từ 17,0\% (nhóm 60--69 tuổi) xuống 2,8\% (nhóm từ 80 tuổi trở lên).
  - **Nhu cầu gọi xe số đã được xác lập:** Khảo sát Rakuten Insight (2025) ghi nhận 66\% người trả lời từng đặt ô tô, 67\% từng đặt xe máy qua ứng dụng; AloSM là thương hiệu được sử dụng thường xuyên nhất bởi 32\% người trả lời.
  - **Quy mô dịch vụ đủ lớn để đánh giá AI Voice:** Hệ thống xử lý hơn **1 triệu chuyến mỗi ngày** và đã phục vụ hơn **100 triệu lượt khách** thông qua hotline 1555 và ứng dụng di động.

Trong bối cảnh nhu cầu gọi xe số phát triển nhưng khả năng tiếp cận công nghệ chưa đồng đều, đây là thời điểm phù hợp để AloSM bổ thẩm AI Voice như một kênh tương tác thêm cho ứng dụng và tổng đài truyền thống.

## Các vấn đề hiện tại

  - **Phụ thuộc vào nhân lực tổng đài:** Mỗi cuộc gọi đòi hỏi một tổng đài viên trực tiếp; chi phí vận hành cao và khó mở rộng.
  - **Nghẽn cuộc gọi giờ cao điểm:** Số lượng cuộc gọi tăng đột biến vào sáng sớm, chiều tối vượt khả năng phục vụ.
  - **Chất lượng phục vụ không đồng nhất:** Mỗi tổng đài viên xử lý khác nhau; thiếu chuẩn hóa.
  - **Câu hỏi lặp lại chiếm phần lớn cuộc gọi:** Hỏi giá, hỏi trạng thái, đặt xe đơn giản - những yêu cầu có thể tự động hóa chiếm tỷ trọng lớn.
  - **Người lớn tuổi và người ít quen app gặp rào cản:** Giao diện ứng dụng đòi hỏi kỹ năng thao tác không phải người dùng nào cũng có.
  - **Mất ngữ cảnh khi chuyển xử lý:** Khách hàng phải kể lại thông tin khi được chuyển sang người khác.

# Problem Statement

> **Problem Statement Tổng hợp**

> **Làm thế nào để AloSM mở rộng khả năng tiếp cận dịch vụ thông qua hội thoại bằng giọng nói, đồng thời tự động hóa các nghiệp vụ tiêu chuẩn nhằm giảm tải cho tổng đài viên, tối ưu nguồn lực vận hành và nâng cao trải nghiệm khách hàng, nhưng vẫn đảm bảo những tình huống phức tạp được xử lý bởi con người?**

Phân tích chi tiết theo từng nhóm stakeholder:

> > **Đối với khách hàng:** Từ góc độ người dùng, không phải tất cả khách hàng đều muốn hoặc có thể sử dụng ứng dụng di động. Người lớn tuổi, người ít thành thạo công nghệ hoặc người đang cần thao tác rảnh tay thường ưu tiên giao tiếp bằng giọng nói. Với họ, việc nói *``Tôi muốn đặt một xe từ Vincom Đồng Khởi về Landmark 81''* tự nhiên và thuận tiện hơn so với việc mở ứng dụng, nhập địa chỉ và thực hiện từng bước đặt xe.

> **Problem Statement - Tổng đài viên**

> **Đối với tổng đài:** Tổng đài phải tiếp nhận các yêu cầu như đặt xe, tra cứu trạng thái chuyến đi, giải đáp thông tin dịch vụ và hướng dẫn khách hàng. Nhiều nghiệp vụ có quy trình tương đối chuẩn hóa và là ứng viên phù hợp cho tự động hóa. Tổng đài viên nên tập trung vào các tình huống cần đánh giá, xử lý linh hoạt hoặc ra quyết định của con người như khiếu nại, tranh chấp và các trường hợp đặc biệt.

> **Problem Statement - Đơn vị vận hành**

> **Đối với vận hành:** Đơn vị vận hành chưa có công cụ đủ để đo lường chất lượng từng cuộc gọi, phân tích nguyên nhân booking thất bại hoặc theo dõi mức độ hài lòng theo thời gian thực. Lưu lượng, cơ cấu yêu cầu và chi phí tổng đài hiện tại chưa có dữ liệu công khai - các số liệu này cần được dùng làm baseline nội bộ trước khi đánh giá tác động kinh doanh của MVP.

# Product Vision

> > 
>     > "Nói một câu, AloSM lo phần còn lại.''"
>   
>   
>   AloSM Voice AI Agent hướng tới trở thành **cổng giao tiếp bằng hội thoại** cho hệ sinh thái dịch vụ AloSM. Sản phẩm giúp khách hàng tiếp cận dịch vụ một cách tự nhiên, thuận tiện và toàn diện thông qua giọng nói; đồng thời hỗ trợ doanh nghiệp tối ưu quy trình chăm sóc khách hàng và nâng cao hiệu quả vận hành. Về dài hạn, nền tảng này được xây dựng để trở thành **lớp giao tiếp bằng hội thoại thống nhất** cho nhiều dịch vụ trong hệ sinh thái AloSM.

# Product Principles và Core Values

## Product Principles

  - **Voice First.** Giọng nói là phương thức tương tác chính, cho phép người dùng tiếp cận dịch vụ bằng hội thoại tự nhiên. Luôn có phương án nhập bằng bàn phím khi microphone không hoạt động.
  - **Human-Centered AI.** AI xử lý các nghiệp vụ tiêu chuẩn; con người tiếp nhận những tình huống cần phán đoán hoặc hỗ trợ chuyên sâu. AI hỗ trợ con người, không thay thế con người.
  - **Reliable Automation.** Hệ thống chỉ tự động hóa những nghiệp vụ có quy trình rõ ràng, có thể kiểm soát và xác nhận. Các tình huống không rõ quy trình (khiếu nại, tranh chấp, tai nạn) phải được chuyển ngay sang người thật.
  - **Continuous Conversation.** AI duy trì ngữ cảnh trong nhiều lượt trao đổi, ghi nhớ thông tin trong phiên và phản hồi nhất quán. Người dùng không phải nhắc lại những gì đã nói trong cùng một cuộc gọi.
  - **Xác nhận trước hành động quan trọng.** Mọi booking, hủy chuyến, hoặc thay đổi thông tin quan trọng đều phải có bước xác nhận rõ ràng từ khách hàng trước khi thực hiện.
  - **Không tự suy đoán dữ liệu nghiệp vụ.** Khi thông tin còn thiếu hoặc mơ hồ, AI hỏi lại thay vì tự điền giá trị. Không tự chọn địa chỉ khi có nhiều kết quả tương đương.
  - **Chuyển người thật khi độ tin cậy thấp.** Sau hai lần nhận diện hoặc xác nhận thất bại, hoặc khi phát hiện tình huống nhạy cảm, hệ thống chuyển sang tổng đài viên với đầy đủ ngữ cảnh.
  - **Minh bạch về trạng thái xử lý.** Khách hàng luôn biết hệ thống đang lắng nghe, đang xử lý hay đang nói. Không để khách hàng chờ trong im lặng.
  - **Bảo vệ dữ liệu cá nhân.** Không đọc toàn bộ số điện thoại qua TTS. Che dữ liệu PII trong giao diện theo vai trò. Ghi âm chỉ khi có consent.
  - **Có phương án fallback khi voice không hoạt động.** Mất kết nối, lỗi microphone, hoặc ASR thất bại phải có xử lý dự phòng rõ ràng.

## Core Values

  - ****Accessibility**** Giúp nhiều nhóm khách hàng tiếp cận dịch vụ dễ dàng hơn thông qua giọng nói - đặc biệt người lớn tuổi, người ít thành thạo công nghệ và người gặp khó khăn khi thao tác trên thiết bị.
  - ****Convenience**** Đơn giản hóa quá trình sử dụng dịch vụ bằng hội thoại tự nhiên - người dùng chỉ cần trình bày nhu cầu, hệ thống lo phần còn lại.
  - ****Operational Efficiency**** Tự động hóa các nghiệp vụ chuẩn hóa nhằm giảm tải tổng đài, tối ưu nguồn lực và chuẩn hóa chất lượng phục vụ.
  - ****Human-Centered AI**** AI hỗ trợ con người thay vì thay thế con người. Các tình huống cần đánh giá, xử lý linh hoạt hoặc ra quyết định của con người luôn được chuyển đến tổng đài viên.

# Mục tiêu sản phẩm

## Mục tiêu người dùng

  - Khách hàng có thể đặt xe hoàn toàn bằng giọng nói, không cần nhập liệu thủ công.
  - Khách hàng không phải lặp lại thông tin đã cung cấp trong cùng một cuộc gọi.
  - Khách hàng nhận được phản hồi rõ ràng về giá, địa chỉ và trạng thái booking.
  - Khách hàng có thể sửa thông tin sai bất kỳ lúc nào trước khi xác nhận.
  - Khách hàng có thể yêu cầu gặp tổng đài viên bất kỳ lúc nào mà không phải cúp cuộc gọi.

## Mục tiêu kinh doanh

  - Chứng minh AI Voice có thể tự động hóa hiệu quả các nghiệp vụ tiêu chuẩn - đặt xe, tra cứu trạng thái, giải đáp FAQ.
  - Thiết lập baseline đo lường để đánh giá tác động giảm tải tổng đài sau pilot.
  - Tăng tổng số cuộc gọi có thể phục vụ đồng thời mà không tăng tương ứng nhân sự.
  - Chuẩn hóa chất lượng thông tin và quy trình phục vụ qua mỗi cuộc gọi.
  - Đo lường và cải thiện tỉ lệ hoàn thành đặt xe qua kênh giọng nói.

## Mục tiêu vận hành

  - Cung cấp công cụ theo dõi chất lượng từng cuộc gọi và phiên hội thoại.
  - Cho phép phân tích nguyên nhân thất bại để cải thiện Agent.
  - Quản lý tri thức tập trung, có phiên bản và kiểm soát xuất bản.
  - Cung cấp báo cáo đủ để đưa ra quyết định sản phẩm dựa trên dữ liệu.

# Non-goals (Ngoài phạm vi MVP)

Những hạng mục sau **không** thuộc phạm vi MVP:

  - **Thanh toán, hoàn tiền và xử lý giao dịch tài chính thực tế** - MVP chỉ mô phỏng hoặc liên kết sandbox.
  - **Khiếu nại, tranh chấp và đánh giá trách nhiệm** - phải do tổng đài viên xử lý.
  - **Điều phối tài xế hoặc can thiệp vào thuật toán ghép chuyến.**
  - **Tai nạn, tình huống khẩn cấp và các trường hợp đặc biệt** - phải chuyển ngay sang người thật và cơ quan có thẩm quyền.
  - Xây dựng nền tảng gọi xe thương mại hoàn chỉnh (tìm tài xế, theo dõi xe thời gian thực, thanh toán thực tế).
  - Tự động giải quyết khiếu nại phức tạp hoặc hoàn tiền.
  - Cam kết nhận diện chính xác mọi giọng vùng miền trong MVP.
  - Tự động huấn luyện toàn bộ mô hình ASR, TTS hay LLM từ đầu trong MVP.
  - Triển khai đa quốc gia hoặc đa ngôn ngữ (tiếng Anh, Khmer, v.v.) trong MVP.
  - Tích hợp kênh Zalo, Messenger, WhatsApp trong MVP.
  - Mobile app native (iOS/Android) - MVP chỉ hỗ trợ web.

# Stakeholder Analysis

| **Stakeholder** | **Vai trò** | **Mục tiêu** | **Ảnh hưởng** | **Quan tâm** | **Nhu cầu TT** | **Trách nhiệm** |
|-|-|-|-|-|-|-|
| Product Owner | Quyết định ưu tiên | Sản phẩm tạo giá trị | Cao | Cao | Roadmap, KPI | Phê duyệt FR, phạm vi MVP |
| Business Analyst | Phân tích nghiệp vụ | Yêu cầu rõ ràng | Cao | Cao | FR, BR, flow | Viết và xác nhận FR, BR |
| CS Manager | Quản lý tổng đài | Giảm tải, nâng chất | Cao | Cao | Handoff flow | Xác nhận luồng operator |
| Tổng đài viên | Hỗ trợ khách hàng | Nhận đúng context | TB | Cao | Console UI | Phản hồi UAT operator |
| Khách hàng | Người dùng cuối | Đặt xe dễ, tin cậy | Thấp | Cao | UX, flow | Tham gia UAT |
| Tài xế | Cung cấp dịch vụ | Nhận thông tin đúng | Thấp | TB | Driver flow | Tham gia UAT driver |
| AI/ML Team | Xây dựng mô hình | Mô hình đúng | Cao | Cao | NFR, data | Đánh giá tính khả thi |
| Engineering | Phát triển hệ thống | Yêu cầu rõ | Cao | TB | FR, contracts | Ước lượng và phát triển |
| UX/UI Team | Thiết kế trải nghiệm | Giao diện dễ dùng | TB | Cao | Persona, journey | Mockup và prototype |
| Data Protection | Bảo mật, tuân thủ | Bảo vệ PII | Cao | TB | Privacy, consent | Phê duyệt privacy req |
| Ban lãnh đạo | Chiến lược | ROI, tăng trưởng | Rất cao | Thấp | Executive summary | Phê duyệt ngân sách |

# Target Users và Personas

## Target Users

### Primary Users - Nhóm mục tiêu chính của MVP

AloSM Voice AI Agent được thiết kế cho những khách hàng ưu tiên hoặc cần tương tác bằng giọng nói thay vì thao tác trên ứng dụng:

  - **Người lớn tuổi** chưa quen sử dụng ứng dụng đặt xe. Hội thoại cần sử dụng câu ngắn, tốc độ vừa phải và xác nhận rõ các thông tin quan trọng.
  - **Người ít thành thạo công nghệ** gặp khó khăn khi thao tác trên điện thoại cảm ứng.
  - **Người gặp khó khăn khi thao tác** do hạn chế thị lực, vận động tay hoặc nhận thức.

### Secondary Users

  - **Người cần rảnh tay:** Đang mang hành lý, bế trẻ nhỏ hoặc thao tác trong khi di chuyển - thành thạo công nghệ nhưng tạm thời không thuận tiện dùng màn hình.
  - **Tổng đài viên:** AloSM Voice tiếp nhận và xử lý trước các yêu cầu có quy trình rõ ràng, giúp tổng đài viên tập trung vào những trường hợp cần hỗ trợ chuyên sâu.

## Personas

### Persona 1 - Bà Thanh Hương (Khách hàng lớn tuổi) { }

| **Bà Thanh Hương - Hưu trí, 67 tuổi - PRIMARY PERSONA MVP** |
|-|
| **Bà Thanh Hương - Hưu trí, 67 tuổi** |
| Bối cảnh | Sống tại Hà Nội, không quen dùng ứng dụng. Con cái đã cài đặt sẵn trên điện thoại và hướng dẫn cách gọi AI |
| Mục tiêu | Đặt được xe đến bệnh viện mà không cần con hỗ trợ |
| Hành vi | Nói từng câu chậm, có thể dừng giữa chừng để suy nghĩ |
| Pain points | Sợ nói sai địa chỉ; không biết phải làm gì khi AI hỏi câu không hiểu; lo lắng khi hệ thống im lặng |
| Nhu cầu | Câu hỏi đơn giản, xác nhận rõ ràng, có thể sửa, có thể gặp người thật |
| Thành thạo CN | Thấp |
| Kịch bản | Gọi AI và nói *``Tôi muốn đặt xe đi Bệnh viện Bạch Mai, tôi ở đường Trần Hưng Đạo, quận Hoàn Kiếm''* |

### Persona 2 - Minh Tuấn (Khách hàng trẻ, quen công nghệ)

| **Minh Tuấn - Nhân viên văn phòng, 28 tuổi** |
|-|
| Bối cảnh | Làm việc tại TP.HCM, thường xuyên di chuyển. Hay dùng app nhưng đôi khi bận tay |
| Mục tiêu | Đặt xe trong vòng 1 phút mà không cần nhìn màn hình |
| Hành vi | Nói nhanh, có thể dùng từ tắt hoặc địa danh quen thuộc |
| Pain points | Bực khi AI không hiểu địa danh thông dụng; không muốn lặp lại nhiều lần |
| Nhu cầu | Nhận diện tốt, phản hồi nhanh, xác nhận rõ ràng |
| Thành thạo CN | Cao |
| Kịch bản | Đang trong thang máy, nói *``Cho tôi đặt xe từ tòa Landmark 81 đến sân bay Tân Sơn Nhất''* |

### Persona 3 - Hồng Nhung (Tổng đài viên)

| **Hồng Nhung - Tổng đài viên cấp cao, 31 tuổi** |
|-|
| Bối cảnh | Làm tổng đài 4 năm, xử lý trung bình 60--80 cuộc gọi mỗi ngày |
| Mục tiêu | Tiếp nhận cuộc gọi chuyển từ AI và xử lý nhanh, không hỏi lại từ đầu |
| Hành vi | Cần công cụ hiển thị ngay context, tóm tắt và thông tin khách hàng khi tiếp nhận |
| Pain points | Khách phải kể lại từ đầu khi được chuyển; thiếu thông tin để xử lý; áp lực giờ cao điểm |
| Nhu cầu | Support Console rõ ràng, nhận context tức thì, tạo/sửa booking nhanh |
| Thành thạo CN | Trung bình |
| Kịch bản | Nhận cuộc gọi chuyển từ AI, thấy ngay transcript, tóm tắt và thông tin đặt xe đang dở |

### Persona 4 - Anh Quốc Hùng (Tài xế)

| **Anh Quốc Hùng - Tài xế đối tác, 42 tuổi** |
|-|
| Bối cảnh | Tài xế toàn thời gian, sử dụng điện thoại khi đang lái xe |
| Mục tiêu | Nhận chuyến mới rõ ràng và xác nhận/từ chối nhanh |
| Hành vi | Thao tác nhanh trong khi lái xe, cần giao diện tối giản |
| Pain points | Thông tin điểm đón không rõ; không biết khách ở tầng nào/cổng nào |
| Nhu cầu | Thông tin chuyến đầy đủ, nút xác nhận lớn, cập nhật trạng thái đơn giản |
| Thành thạo CN | Trung bình |
| Kịch bản | Nhận thông báo chuyến mới từ AI booking, xem chi tiết và nhấn xác nhận chuyến |

### Persona 5 - Trung Kiên (AI Operations / Admin)

| **Trung Kiên - AI Operations Engineer, 29 tuổi** |
|-|
| Bối cảnh | Kỹ sư vận hành AI, quản lý KB và cấu hình Agent cho AloSM |
| Mục tiêu | Đảm bảo Agent hoạt động đúng, cập nhật nội dung kịp thời, phát hiện lỗi sớm |
| Hành vi | Theo dõi dashboard hàng ngày, review transcript cuộc gọi thất bại, cập nhật KB khi có chính sách mới |
| Pain points | Không có công cụ kiểm thử truy xuất KB; khó biết Agent dùng thông tin nào để trả lời |
| Nhu cầu | Admin dashboard, KB editor, agent versioning, evaluation tools |
| Thành thạo CN | Cao |
| Kịch bản | Phát hiện tỉ lệ lỗi tool tăng qua dashboard, vào xem transcript, xác định nguyên nhân và cập nhật KB |

# Jobs To Be Done (JTBD)

| **JTBD** | **Khi...** | **Tôi muốn...** | **Để...** |
|-|-|-|-|
| JTBD-01 | Tôi cần đặt xe và đang bận tay | Nói yêu cầu đặt xe và AI hiểu ngay | Không mất thời gian thao tác màn hình |
| JTBD-02 | Tôi muốn biết giá chuyến trước khi đặt | Hỏi AI giá từ A đến B và nhận ngay câu trả lời | Quyết định có đặt xe không |
| JTBD-03 | Tôi đã đặt xe và muốn biết trạng thái | Hỏi AI chuyến của tôi đang ở đâu | Biết khi nào tài xế đến |
| JTBD-04 | Tôi muốn hủy chuyến vừa đặt | Nói với AI hủy chuyến và nhận xác nhận | Không bị tính phí sai |
| JTBD-05 | Tôi nói địa chỉ sai và muốn sửa | Nói lại địa chỉ đúng trước khi xác nhận | Tài xế đến đúng chỗ |
| JTBD-06 | AI không xử lý được yêu cầu | Gặp ngay người thật mà không cúp cuộc gọi | Vẫn được hỗ trợ mà không phải gọi lại |
| JTBD-07 | Là tổng đài viên nhận cuộc gọi từ AI | Thấy ngay transcript và tóm tắt cuộc gọi | Không hỏi lại khách từ đầu |
| JTBD-08 | Là AI Ops muốn cập nhật chính sách | Cập nhật tài liệu KB và kiểm thử trước khi xuất bản | Agent trả lời đúng chính sách mới |

# User Journey - Đặt xe bằng giọng nói

| **\#** | **Hành động** | **Mục tiêu** | **Touchpoint** | **Cảm xúc** | **Pain point** | **Cơ hội** | **Trạng thái** |
|-|-|-|-|-|-|-|-|
| 1 | Truy cập web | Vào hệ thống | Trang chủ | Trung tính | Không biết bắt đầu | Hướng dẫn rõ | Idle |
| 2 | Nhấn ``Gọi AI'' | Bắt đầu gọi | Nút CTA | Kỳ vọng | Lo ngại mic | Nút nổi bật | Khởi tạo |
| 3 | Cấp quyền mic | Cho phép ghi âm | Dialog trình duyệt | Lo ngại | Dữ liệu dùng thế nào | Giải thích consent | Chờ quyền |
| 4 | Nói yêu cầu | Truyền nhu cầu | Mic + UI | Hồi hộp | AI không nghe đúng | Hiển thị sóng âm | Đang nghe |
| 5 | Xem transcript | Kiểm tra AI hiểu | Transcript UI | Thích thú | Transcript sai | Cho phép sửa | Xử lý STT |
| 6 | Trả lời câu hỏi | Cung cấp thêm TT | Voice + Text | Tập trung | AI hỏi nhiều lần | Chỉ hỏi 1 TT/lượt | Hội thoại |
| 7 | Xác nhận địa chỉ | Đảm bảo đúng | Thẻ địa chỉ | Cẩn thận | Nhiều địa chỉ tương tự | Hiển thị danh sách | Chờ xác nhận |
| 8 | Xem giá dự kiến | Quyết định đặt | Thẻ giá | Quan tâm | Giá không rõ cơ sở | Giải thích ngắn | Tính giá |
| 9 | Xác nhận đặt xe | Tạo booking | Nút xác nhận | Quyết định | Lo ngại đặt nhầm | Xác nhận 2 chiều | Chờ xác nhận |
| 10 | Nhận kết quả | Biết booking tạo | Thẻ booking | Nhẹ nhõm | Không rõ bước tiếp | Thẻ rõ ràng | Tạo booking |
| 11 | Theo dõi chuyến | Biết tài xế đã nhận | Trip card | Chờ đợi | Không biết TX ở đâu | Trạng thái rõ | Đang xử lý |
| 12 | Kết thúc | Phản hồi trải nghiệm | Rating UI | Thoải mái | Không muốn đánh giá dài | Rating 1 chạm | Kết thúc |

# Product Scope

## MVP - In Scope

  - Tiếp nhận và phản hồi hội thoại bằng giọng nói tiếng Việt.
  - Hiểu ý định và duy trì ngữ cảnh trong nhiều lượt trao đổi.
  - **Đặt xe:** Thu thập điểm đón, điểm đến, loại xe; xác nhận thông tin; tạo booking.
  - **Tra cứu trạng thái chuyến đi:** Khách hỏi trạng thái chuyến, AI truy vấn qua tool.
  - **Giải đáp thông tin dịch vụ và FAQ:** Giá cước, chính sách, dịch vụ.
  - Xác nhận thông tin quan trọng trước khi thực hiện nghiệp vụ.
  - Xử lý địa chỉ mơ hồ: hiển thị danh sách, hỏi khách chọn - không tự chọn.
  - Báo giá dự kiến trước khi xác nhận booking.
  - Lưu lịch sử hội thoại trong phiên.
  - Chuyển tiếp tổng đài viên (HITL) khi cần.
  - Operator Queue và Support Console cơ bản.
  - Lịch sử cuộc gọi và lịch sử chuyến.
  - Knowledge Base cơ bản (upload tài liệu, tìm kiếm ngữ nghĩa).
  - Dashboard quản trị cơ bản với KPI chính.
  - Quản lý giọng trợ lý (chọn voice profile).
  - Tài xế nhận và xác nhận chuyến từ hệ thống.

## Out of Scope (MVP)

  - Thanh toán, hoàn tiền và xử lý giao dịch tài chính.
  - Khiếu nại, tranh chấp và đánh giá trách nhiệm.
  - Điều phối tài xế hoặc can thiệp vào thuật toán ghép chuyến.
  - Tai nạn, tình huống khẩn cấp và các trường hợp đặc biệt.

> > **Lưu ý:** AloSM Voice AI Agent không hướng đến việc thay thế tổng đài viên. MVP chỉ chứng minh rằng AI có thể tự động hóa hiệu quả các nghiệp vụ tiêu chuẩn, giúp con người tập trung vào những tình huống cần chuyên môn và khả năng đánh giá.

## Post-MVP

  - **Mở rộng nghiệp vụ:** Hủy chuyến đầy đủ, báo mất đồ, tiếp nhận phản ánh, hỗ trợ khuyến mãi và khách hàng doanh nghiệp.
  - **Kênh telephony:** Tích hợp đường dây điện thoại thật (SIP/VoIP); triển khai kiosk tự phục vụ.
  - **Mobile native app:** Tích hợp Voice Agent vào ứng dụng di động AloSM (iOS/Android).
  - **Cá nhân hóa:** Ghi nhớ lịch sử tương tác, địa chỉ thường dùng, sở thích giọng nói.
  - **Mở rộng kênh:** Website, Zalo OA, Messenger; đa ngôn ngữ (tiếng Anh, v.v.).
  - Theo dõi xe thời gian thực. \quad Kết nối CRM. \quad Kiến trúc multi-agent.
  - A/B testing cho cấu hình Agent. \quad Evaluation Lab tự động.

## Future Vision

  - Nền tảng Voice AI phục vụ nhiều dịch vụ trong hệ sinh thái AloSM.
  - **Lớp giao tiếp bằng hội thoại thống nhất** (Unified Conversational Layer) cho toàn bộ hệ sinh thái.
  - Cá nhân hóa trải nghiệm, lịch sử tương tác xuyên phiên, đa quốc gia.
  - Phân tích cuộc gọi nâng cao bằng AI; cải thiện liên tục mô hình qua dữ liệu thực tế.

# Information Architecture

  - **Customer Portal:** Trang chủ $\cdot$ Cuộc gọi AI $\cdot$ Lịch sử cuộc gọi $\cdot$ Lịch sử chuyến $\cdot$ Chi tiết chuyến $\cdot$ Cài đặt giọng nói $\cdot$ Hồ sơ cá nhân.
  - **Operator Console:** Dashboard $\cdot$ Hàng chờ (Queue) $\cdot$ Support Console $\cdot$ Hồ sơ khách hàng $\cdot$ Tạo và sửa booking $\cdot$ Lịch sử hỗ trợ $\cdot$ Ghi chú sau cuộc gọi.
  - **Driver Portal:** Trang chủ $\cdot$ Trạng thái sẵn sàng $\cdot$ Chuyến mới $\cdot$ Chi tiết chuyến $\cdot$ Chuyến đang thực hiện $\cdot$ Lịch sử chuyến.
  - **Admin \& AI Ops:** Dashboard $\cdot$ Users $\cdot$ Conversations $\cdot$ Bookings $\cdot$ Knowledge Base $\cdot$ Agent Configuration $\cdot$ Voice Library $\cdot$ Evaluation $\cdot$ Monitoring $\cdot$ Settings.

# Epic và Feature Breakdown

| **Epic ID** | **Tên Epic** | **Mục tiêu** | **Tính năng chính** | **Phạm vi** | **Chỉ số** |
|-|-|-|-|-|-|
| EP-01 | Auth \ | Access | Kiểm soát truy cập | Đăng nhập, phân quyền, consent |  | Tỉ lệ ĐK thành công |
| EP-02 | Customer Home | Điểm khởi đầu KH | Trang chủ, nút gọi AI, lịch sử |  | Tỉ lệ bắt đầu cuộc gọi |
| EP-03 | Voice Call Experience | Trải nghiệm hội thoại | Thu âm, transcript, TTS, trạng thái |  | CSAT, tỉ lệ hoàn thành |
| EP-04 | Conversation Context | Quản lý ngữ cảnh | Context memory, slot filling |  | Tỉ lệ hỏi lại |
| EP-05 | Ride Booking | Đặt xe thành công | Thu thập TT, xác nhận, tạo booking |  | Tỉ lệ booking thành công |
| EP-06 | Information Services | Giải đáp thông tin | Tra trạng thái, hỏi giá, FAQ |  | Tỉ lệ giải đáp đúng |
| EP-07 | Human Handoff | Chuyển người thật | Trigger HITL, queue, context transfer |  | TG chờ handoff |
| EP-08 | Operator Console | Hỗ trợ tổng đài viên | Queue, console, booking manual |  | TG xử lý mỗi ca |
| EP-09 | Driver Experience | Tài xế nhận chuyến | Nhận chuyến, cập nhật trạng thái |  | Tỉ lệ nhận chuyến |
| EP-10 | Call History | Lưu lịch sử | Danh sách, transcript, recording |  | Khả năng truy vết |
| EP-11 | Knowledge Base | Quản lý tri thức | Upload, tìm kiếm, xuất bản |  | Tỉ lệ câu trả lời đúng |
| EP-12 | Agent Management | Quản lý Agent | Cấu hình, phiên bản, deploy |  | Tỉ lệ lỗi tool |
| EP-13 | Voice Configuration | Cài đặt giọng nói | Voice library, preview, áp dụng |  | Tỉ lệ dùng voice default |
| EP-14 | Reporting \ | Analytics | Báo cáo | Dashboard, KPI, export |  | Dữ liệu đo được |
| EP-15 | Administration | Quản trị hệ thống | User mgmt, audit log, settings |  | Tính tuân thủ |
| EP-16 | Privacy \ | Consent | Bảo vệ dữ liệu | Consent, che PII, audit |  | Tuân thủ chính sách |
| EP-17 | Accessibility \ | Fallback | Khả năng tiếp cận | Text fallback, slow mode, retry |  | Tỉ lệ dùng fallback |

# Functional Requirements

\small

## Xác thực và Phân quyền (FR-AUTH)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-AUTH-001** | Đăng nhập | Đăng nhập bằng SĐT + OTP hoặc tài khoản | KH / Truy cập web |  | Thành công $\leq$3 bước; OTP sai hiện thông báo |
| **FR-AUTH-002** | Phân quyền | Giao diện phù hợp với vai trò | Hệ thống / Sau ĐK |  | KH không thấy Operator Console; Admin thấy toàn bộ |
| **FR-AUTH-003** | Consent ghi âm | Yêu cầu và ghi nhận đồng ý ghi âm trước cuộc gọi | KH / Pre-call |  | Không ghi âm khi chưa có consent; lưu timestamp |
| **FR-AUTH-004** | Đăng xuất | Đăng xuất bất kỳ lúc nào; phiên bị xóa | KH / Click ĐX |  | Xóa session; redirect về trang ĐK |
| **FR-AUTH-005** | Quản lý tài khoản | Admin tạo, sửa, vô hiệu hóa tài khoản Operator và Driver | Admin / Panel |  | Tài khoản vô hiệu hóa không ĐK được; có audit log |

## Trải nghiệm cuộc gọi Voice AI (FR-CALL)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-CALL-001** | Bắt đầu cuộc gọi | Kiểm tra quyền mic, consent, kết nối; khởi tạo phiên | KH / Click ``Gọi AI'' |  | Khởi tạo thành công; hiện trạng thái đang lắng nghe |
| **FR-CALL-002** | Cấp quyền mic | Yêu cầu quyền; xử lý từ chối | KH / Pre-call |  | Từ chối mic: hiện hướng dẫn fallback sang text |
| **FR-CALL-003** | Thu âm và ASR | Giọng nói chuyển thành văn bản realtime | KH / Đang nói |  | Transcript xuất hiện $\leq$3 giây sau khi khách dừng nói |
| **FR-CALL-004** | Hiển thị trạng thái AI | 3 trạng thái: đang lắng nghe / đang xử lý / đang nói | Hệ thống |  | 3 trạng thái phân biệt bằng icon và màu; không im lặng $>$3s |
| **FR-CALL-005** | Phát TTS | AI trả lời bằng giọng nói TTS tự nhiên | Hệ thống |  | Phát âm đúng địa danh và số tiền tiếng Việt |
| **FR-CALL-006** | Hiển thị transcript | Hội thoại hiển thị realtime, phân biệt giọng AI và khách | Hệ thống |  | Hai bên hội thoại phân biệt rõ màu/nhãn; có timestamp |
| **FR-CALL-007** | Text fallback | Khi mic không khả dụng, nhập bằng bàn phím | KH / Mic lỗi |  | Text input hoạt động đầy đủ; AI trả lời cả text và voice |
| **FR-CALL-008** | Kết thúc cuộc gọi | Khách kết thúc bất kỳ lúc nào | KH / Click KT |  | Phiên đóng; lưu lịch sử; hiện màn hình tóm tắt |
| **FR-CALL-009** | Xử lý mất kết nối | Lưu ngữ cảnh và thông báo khi kết nối gián đoạn | Hệ thống |  | Context lưu; thông báo rõ ràng; hỗ trợ kết nối lại |
| **FR-CALL-010** | Ngắt lời AI | Khách ngắt AI đang nói để nói lại | KH / AI nói |  | Nhấn nút hoặc nói ngắt; AI dừng và bắt đầu lắng nghe |

## Đặt xe (FR-BOOK)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-BOOK-001** | Thu thập TT | AI hỏi điểm đón, điểm đến, loại xe | AI / KH yêu cầu |  | Đủ thông tin bắt buộc mới chuyển sang xác nhận |
| **FR-BOOK-002** | Xác nhận địa chỉ mơ hồ | Khi địa chỉ nhiều kết quả, hiện danh sách để khách chọn | AI / Mơ hồ |  | Không tự chọn; luôn hiện $\geq$2 lựa chọn khi mơ hồ |
| **FR-BOOK-003** | Báo giá dự kiến | AI thông báo giá ước tính trước khi hỏi xác nhận | AI |  | Giá đọc rõ bằng TTS; ghi rõ là giá dự kiến |
| **FR-BOOK-004** | Xác nhận trước khi tạo | AI yêu cầu xác nhận toàn bộ trước khi tạo booking | AI |  | Không tạo booking khi chưa có xác nhận rõ ràng |
| **FR-BOOK-005** | Tạo booking | Tạo booking qua tool nghiệp vụ sau xác nhận | Hệ thống |  | Booking có mã duy nhất; không tạo trùng trong phiên |
| **FR-BOOK-006** | Hiển thị thẻ booking | Hiển thị thẻ booking với đầy đủ thông tin | Hệ thống |  | Thẻ có: mã booking, điểm đón, điểm đến, giá, loại xe |
| **FR-BOOK-007** | Chống booking trùng | Phát hiện và ngăn tạo booking trùng trong phiên | Hệ thống |  | Thông báo rõ khi trùng; không tạo booking thứ hai |
| **FR-BOOK-008** | Xử lý booking thất bại | Khi tool lỗi, AI thông báo và đề xuất thử lại / chuyển OP | AI / Error |  | Không để khách chờ im lặng; có phương án thay thế |
| **FR-BOOK-009** | Sửa thông tin | Khách sửa bất kỳ thông tin nào trước xác nhận | KH |  | Sửa cập nhật ngay; AI đọc lại thông tin đã sửa |
| **FR-BOOK-010** | Hủy luồng | Khách hủy luồng đặt xe bất kỳ lúc nào | KH |  | Booking không được tạo; context được reset |

## Information Services - Tra cứu và Giải đáp (FR-INFO)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-INFO-001** | Tra cứu trạng thái | Khách hỏi trạng thái chuyến; AI truy vấn qua tool | KH / Hỏi TT |  | AI đọc rõ trạng thái chuyến; hiển thị trong transcript |
| **FR-INFO-002** | Lịch sử chuyến | Khách xem danh sách các chuyến đã đặt | KH / Lịch sử |  | Danh sách có ngày, địa chỉ, trạng thái; click xem chi tiết |
| **FR-INFO-003** | Hỏi giá cước | Khách hỏi giá từ A đến B; AI trả lời | KH / Hỏi giá |  | AI ghi rõ là ước tính; không cam kết giá chính xác |
| **FR-INFO-004** | Giải đáp FAQ | Khách hỏi chính sách, khuyến mãi; AI truy xuất KB | KH / Hỏi CS |  | Câu trả lời căn cứ vào tài liệu đã được xuất bản |
| **FR-INFO-005** | Hủy chuyến | Khách yêu cầu hủy; AI xác nhận trước khi thực hiện | KH / Yêu cầu hủy |  | Hủy chỉ thực hiện sau khi có xác nhận ``đồng ý hủy'' |

## Human Handoff (FR-HITL)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-HITL-001** | KH yêu cầu HITL | KH yêu cầu gặp người thật bất kỳ lúc nào | KH / Yêu cầu |  | AI thông báo và chuyển ngay; không từ chối hoặc trì hoãn |
| **FR-HITL-002** | AI tự động chuyển | Sau **hai lần** nhận diện hoặc xác nhận thất bại, khi confidence thấp, hoặc tình huống nhạy cảm (khiếu nại, thanh toán, tai nạn) | AI / Ngưỡng |  | Ngưỡng 2 lần được cấu hình; thông báo rõ trước khi chuyển |
| **FR-HITL-003** | Hàng chờ operator | Cuộc gọi chờ trong queue; hiện vị trí hàng chờ | Hệ thống |  | Hiện vị trí; có âm thanh chờ; khách có thể hủy chờ |
| **FR-HITL-004** | Chuyển context | Operator nhận transcript đầy đủ, tóm tắt AI trước khi nói | Hệ thống |  | Context xuất hiện trước cuộc gọi kết nối |
| **FR-HITL-005** | Operator tiếp nhận | Operator thấy cuộc gọi mới trong queue và nhấn tiếp nhận | Operator |  | Tiếp nhận chỉ một lần; không chia cho nhiều operator |

## Operator Console (FR-OPS)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-OPS-001** | Xem hàng chờ | Danh sách cuộc gọi đang chờ kèm TG chờ | Operator |  | Cập nhật realtime; sắp xếp theo TG chờ |
| **FR-OPS-002** | Xem tóm tắt AI | Tóm tắt cuộc gọi từ AI trước khi nói | Operator |  | Tóm tắt gồm: ý định, TT đã thu thập, lý do chuyển |
| **FR-OPS-003** | Tạo booking thủ công | Operator tạo booking cho khách trong Support Console | Operator |  | Form tạo booking có đủ trường; xác nhận trước khi tạo |
| **FR-OPS-004** | Sửa booking | Operator sửa thông tin booking chưa hoàn thành | Operator |  | Có audit log khi sửa; khách được thông báo |
| **FR-OPS-005** | Ghi chú sau cuộc gọi | Operator ghi chú kết quả và vấn đề sau khi kết thúc | Operator |  | Ghi chú lưu vào lịch sử; hiển thị trong call history |

## Knowledge Base (FR-KB)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-KB-001** | Upload tài liệu | Admin upload tài liệu chính sách, FAQ vào KB | Admin |  | Hỗ trợ PDF, DOCX, TXT; hiện trạng thái xử lý |
| **FR-KB-002** | Tìm kiếm ngữ nghĩa | Tìm tài liệu phù hợp theo ngữ nghĩa | Hệ thống |  | Trả về top-k tài liệu phù hợp nhất |
| **FR-KB-003** | Kiểm thử truy xuất | Admin nhập câu hỏi và xem tài liệu nào KB trả về | Admin |  | Hiện tài liệu, điểm liên quan và đoạn trích |
| **FR-KB-004** | Kiểm soát xuất bản | Tài liệu phải qua bước xuất bản mới dùng trong production | Admin |  | Tài liệu draft không ảnh hưởng câu trả lời production |
| **FR-KB-005** | Quản lý phiên bản | Mỗi tài liệu có lịch sử phiên bản; có thể rollback | Admin |  | Rollback khôi phục nội dung cũ; phiên bản hiệu lực đánh dấu rõ |

## Quản trị, Agent và Báo cáo (FR-ADMIN)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-ADMIN-001** | Cấu hình Agent | Cấu hình prompt hệ thống, tool, ngưỡng tin cậy | AI Ops |  | Thay đổi lưu vào phiên bản mới; không ảnh hưởng cuộc gọi đang diễn ra |
| **FR-ADMIN-002** | Phiên bản Agent | Mỗi thay đổi tạo phiên bản mới; có thể rollback | AI Ops |  | Rollback khôi phục cấu hình cũ trong $\leq$5 phút |
| **FR-ADMIN-003** | Voice Library | Quản lý danh sách giọng TTS; preview trước áp dụng | Admin |  | Preview hoạt động; giọng áp dụng đúng cấu hình |
| **FR-ADMIN-004** | Dashboard tổng quan | KPI chính: số cuộc gọi, tỉ lệ hoàn thành, HITL rate, CSAT | Admin |  | Dữ liệu cập nhật theo chu kỳ; có filter theo ngày |
| **FR-ADMIN-005** | Quản lý cuộc gọi | Xem danh sách cuộc gọi, nghe lại, xem transcript | Admin |  | Lọc theo ngày, kết quả; xem chi tiết từng cuộc gọi |
| **FR-ADMIN-006** | Audit log | Mọi hành động quan trọng ghi vào audit log | Hệ thống |  | Log không thể xóa; có thể export; filter theo loại |
| **FR-ADMIN-007** | Xóa dữ liệu | Admin xử lý yêu cầu xóa dữ liệu khách hàng | Admin |  | Xóa PII theo yêu cầu; lưu audit record |
| **FR-ADMIN-008** | Feedback KH | Khách đánh giá cuộc gọi sau khi kết thúc | KH |  | Rating 1--5 sao; có ô bình luận tùy chọn |

## Trải nghiệm Tài xế (FR-DRV)

| **ID** | **Tên** | **Mô tả** | **Actor/Trigger** | **Priority** | **Acceptance** |
|-|-|-|-|-|-|
| **FR-DRV-001** | Nhận thông báo chuyến | Tài xế nhận thông báo khi có chuyến mới | TX / Booking |  | Thông báo xuất hiện trong $\leq$10s; có âm thanh |
| **FR-DRV-002** | Xem chi tiết chuyến | Tài xế xem điểm đón, điểm đến, thông hiện khách | TX |  | Địa chỉ hiển thị rõ và đầy đủ |
| **FR-DRV-003** | Nhận hoặc từ chối | Tài xế nhận hoặc từ chối chuyến mới | TX |  | Nhận: cập nhật trạng thái booking; từ chối: không ảnh hưởng |
| **FR-DRV-004** | Cập nhật trạng thái | Cập nhật: đã đến điểm đón, đã đón khách, hoàn thành | TX |  | Trạng thái cập nhật tức thì; khách hàng thấy được |

# User Stories

\small

| **Story ID** | **Epic** | **User Story** | **Business Value** | **Priority** | **Acceptance Criteria (GWT)** |
|-|-|-|-|-|-|
| **US-001** | EP-01 | Là khách hàng, tôi muốn đăng nhập bằng SĐT và OTP để truy cập an toàn | Bảo mật tài khoản |  | Given nhập SĐT hợp lệ, When nhập OTP đúng, Then vào trang chủ |
| **US-002** | EP-01 | Là khách hàng, tôi muốn được hỏi consent ghi âm trước cuộc gọi | Tuân thủ privacy |  | Given nhấn ``Gọi AI'', When dialog consent hiện, Then từ chối không bắt đầu ghi âm |
| **US-003** | EP-03 | Là khách hàng, tôi muốn thấy trạng thái AI đang lắng nghe | Giảm lo ngại |  | Given cuộc gọi diễn ra, When tôi nói, Then icon ``đang nghe'' và sóng âm chuyển động |
| **US-004** | EP-03 | Là khách hàng, tôi muốn thấy transcript để kiểm tra AI hiểu đúng chưa | Tăng tin cậy |  | Given AI nhận diện xong, When transcript xuất hiện, Then phân biệt rõ giọng AI và tôi |
| **US-005** | EP-17 | Là khách hàng, tôi muốn nhập bằng bàn phím khi microphone không hoạt động | Không bỏ lỡ khách |  | Given mic không khả dụng, When hệ thống phát hiện, Then hiện text input và hướng dẫn |
| **US-006** | EP-05 | Là khách hàng, tôi muốn AI hỏi từng thông tin thiếu một lần một để không bị rối | Trải nghiệm tốt |  | Given tôi chưa nói điểm đến, When AI hỏi, Then AI chỉ hỏi một thông tin mỗi lượt |
| **US-007** | EP-05 | Là khách hàng, tôi muốn được chọn từ danh sách khi địa chỉ mơ hồ | Giảm booking sai |  | Given tôi nói địa chỉ mơ hồ, When AI tìm nhiều KQ, Then hiện danh sách để tôi chọn |
| **US-008** | EP-05 | Là khách hàng, tôi muốn biết giá trước khi xác nhận để quyết định có đặt không | Giảm bỏ cuộc |  | Given đủ TT chuyến, When AI báo giá, Then giá đọc bằng TTS và hiện trong transcript |
| **US-009** | EP-05 | Là khách hàng, tôi muốn xác nhận toàn bộ thông tin trước khi tạo booking | Giảm booking sai |  | Given AI đọc lại TT, When tôi nói ``đồng ý'', Then booking được tạo |
| **US-010** | EP-05 | Là khách hàng, tôi muốn sửa thông tin sai trước khi xác nhận | Giảm lỗi |  | Given tôi yêu cầu sửa, When AI cập nhật, Then AI đọc lại thông tin đã sửa |
| **US-011** | EP-07 | Là khách hàng, tôi muốn yêu cầu gặp người thật bất kỳ lúc nào | Tăng tin cậy |  | Given nói ``gặp người thật'', When AI nhận, Then chuyển queue và thông báo tôi |
| **US-012** | EP-07 | Là khách hàng, tôi muốn AI tự động chuyển operator sau 2 lần thất bại | Không bị kẹt |  | Given AI thất bại 2 lần liên tiếp, When đạt ngưỡng, Then đề xuất chuyển operator |
| **US-013** | EP-08 | Là tổng đài viên, tôi muốn thấy transcript khi tiếp nhận để không hỏi lại khách | Giảm TG xử lý |  | Given cuộc gọi chuyển đến, When tôi tiếp nhận, Then thấy ngay transcript và tóm tắt AI |
| **US-014** | EP-08 | Là tổng đài viên, tôi muốn tạo booking thủ công trong Support Console | Đảm bảo phục vụ |  | Given mở form booking, When điền và xác nhận, Then booking tạo và liên kết cuộc gọi |
| **US-015** | EP-09 | Là tài xế, tôi muốn nhận thông báo chuyến mới rõ ràng | Tỉ lệ nhận chuyến cao |  | Given có booking mới, When hệ thống gửi TB, Then thấy TB với địa chỉ và giá |
| **US-016** | EP-09 | Là tài xế, tôi muốn cập nhật trạng thái chuyến để khách biết tôi ở đâu | Trải nghiệm KH tốt |  | Given nhấn ``Đã đến điểm đón'', When cập nhật, Then trạng thái đổi và khách nhận TB |
| **US-017** | EP-11 | Là AI Ops, tôi muốn upload tài liệu vào KB và kiểm thử trước khi xuất bản | Chất lượng KB |  | Given upload, When kiểm thử bằng câu hỏi, Then thấy tài liệu được truy xuất và đoạn trích |
| **US-018** | EP-11 | Là AI Ops, tôi muốn kiểm soát phiên bản tài liệu để rollback khi có lỗi | Giảm rủi ro |  | Given rollback, When xác nhận, Then phiên bản cũ kích hoạt trong $\leq$5 phút |
| **US-019** | EP-12 | Là AI Ops, tôi muốn thay đổi cấu hình Agent mà không ảnh hưởng cuộc gọi đang diễn ra | Triển khai an toàn |  | Given cuộc gọi đang diễn ra, When lưu cấu hình mới, Then chỉ áp dụng phiên tiếp theo |
| **US-020** | EP-14 | Là Product Owner, tôi muốn xem dashboard KPI theo ngày | Quyết định dữ liệu |  | Given vào Dashboard, When chọn khoảng ngày, Then thấy số cuộc gọi, tỉ lệ hoàn thành, CSAT |
| **US-021** | EP-06 | Là khách hàng, tôi muốn hỏi giá cước ước tính mà không cần đặt xe | Tăng chuyển đổi |  | Given hỏi ``giá từ A đến B'', When AI trả lời, Then nhận giá kèm ghi chú là ước tính |
| **US-022** | EP-06 | Là khách hàng, tôi muốn hủy chuyến và nhận xác nhận | Tin tưởng dịch vụ |  | Given yêu cầu hủy, When AI xác nhận và thực hiện, Then booking đổi trạng thái |
| **US-023** | EP-16 | Là khách hàng, tôi muốn yêu cầu xóa dữ liệu cá nhân của mình | Quyền riêng tư |  | Given gửi yêu cầu xóa, When Admin xử lý, Then PII được xóa và tôi nhận xác nhận |
| **US-024** | EP-17 | Là khách hàng lớn tuổi, tôi muốn hệ thống nhắc lại TT trước khi xác nhận | Giảm lỗi booking |  | Given sắp xác nhận, When AI tổng hợp, Then AI đọc lại đầy đủ trước khi tôi đồng ý |
| **US-025** | EP-03 | Là khách hàng, tôi muốn chọn giọng trợ lý yêu thích | Cá nhân hóa |  | Given vào Cài đặt giọng, When chọn và preview, Then giọng lưu và áp dụng lần gọi tiếp |
| **US-026** | EP-15 | Là Admin, tôi muốn xem audit log đầy đủ để phát hiện bất thường | Bảo mật |  | Given vào Audit Log, When lọc theo loại, Then thấy danh sách, actor và timestamp |
| **US-027** | EP-01 | Là Admin, tôi muốn vô hiệu hóa tài khoản operator ngay lập tức | Kiểm soát bảo mật |  | Given vô hiệu hóa tài khoản, When lưu, Then tài khoản đó không ĐK được |
| **US-028** | EP-10 | Là khách hàng, tôi muốn xem lịch sử cuộc gọi để tra cứu lại TT | Tăng tin cậy |  | Given vào lịch sử, When tải, Then thấy danh sách với ngày, TG và kết quả |
| **US-029** | EP-14 | Là CS Manager, tôi muốn xem tỉ lệ handoff và TG chờ | Quản lý hiệu suất |  | Given lọc theo tuần, When xem Dashboard, Then thấy HITL rate, TG chờ TB |
| **US-030** | EP-04 | Là khách hàng, tôi muốn AI nhớ thông tin tôi đã nói trong cuộc gọi hiện tại | Trải nghiệm liên tục |  | Given tôi đã nói địa chỉ, When AI hỏi thêm, Then AI không hỏi lại thông tin đã có |

# Business Rules

| **BR ID** | **Quy tắc** | **Bối cảnh** | **Priority** | **Hệ quả vi phạm** |
|-|-|-|-|-|
| BR-001 | Không tạo booking khi chưa có xác nhận rõ ràng từ khách hàng | Mọi luồng đặt xe |  | Booking sai, khiếu nại, mất tin tưởng |
| BR-002 | Không tự chọn địa chỉ khi có nhiều kết quả tương đương; luôn hỏi khách chọn | Xử lý địa chỉ |  | Booking sai địa điểm |
| BR-003 | Giá hiển thị là giá dự kiến, không phải giá chính thức; phải ghi rõ | Thông tin giá |  | Khiếu nại về giá |
| BR-004 | Mỗi booking phải có mã định danh duy nhất | Tạo booking |  | Không thể tra cứu, quản lý |
| BR-005 | Một yêu cầu tạo booking trong cùng phiên chỉ xử lý một lần | Chống duplicate |  | Tạo booking trùng |
| BR-006 | Khách hàng có thể yêu cầu gặp người thật bất kỳ lúc nào | Human handoff |  | Vi phạm quyền khách hàng |
| BR-007 | Hệ thống tự động chuyển operator sau **2 lần** nhận diện hoặc xác nhận thất bại | HITL trigger |  | Khách bị kẹt vô hạn với AI |
| BR-008 | Tình huống nhạy cảm (khiếu nại, thanh toán, tai nạn, khẩn cấp) phải chuyển ngay sang tổng đài viên | HITL safety |  | Rủi ro pháp lý và uy tín |
| BR-009 | Operator phải nhận được transcript và tóm tắt đầy đủ trước khi tiếp nhận cuộc gọi | Context transfer |  | Khách kể lại từ đầu, trải nghiệm kém |
| BR-010 | Không xưng hô theo giới tính nếu chưa có thông tin xác nhận | Xưng hô |  | Gây khó chịu, phân biệt |
| BR-011 | Không đọc toàn bộ số điện thoại qua TTS; chỉ đọc 4 số cuối | Bảo mật |  | Rò rỉ thông tin cá nhân |
| BR-012 | Chỉ hiển thị dữ liệu phù hợp với vai trò đã đăng nhập | Phân quyền |  | Lộ thông tin, vi phạm bảo mật |
| BR-013 | Ghi âm cuộc gọi chỉ khi có consent của khách hàng | Consent |  | Vi phạm luật bảo vệ dữ liệu |
| BR-014 | Tài liệu RAG phải có phiên bản hiệu lực và được xuất bản trước khi dùng production | Quản lý KB |  | AI dùng thông tin sai/cũ |
| BR-015 | Hủy chuyến chỉ thực hiện khi có xác nhận ``đồng ý hủy'' từ khách | Hủy chuyến |  | Hủy nhầm, khiếu nại |
| BR-016 | Thay đổi cấu hình Agent không ảnh hưởng đến cuộc gọi đang diễn ra | Agent mgmt |  | Hội thoại bị gián đoạn |
| BR-017 | Một cuộc gọi chuyển operator chỉ được tiếp nhận bởi một operator duy nhất | Operator console |  | Xử lý chồng chéo |

# Non-functional Requirements

## Usability

  - Người dùng phổ thông có thể bắt đầu cuộc gọi trong tối đa ba thao tác từ trang chủ.
  - Ba trạng thái cuộc gọi phân biệt rõ bằng cả màu sắc, icon và âm thanh.
  - Các hành động chính (Gọi AI, Xác nhận, Hủy, Gặp người thật) phải dễ tìm.
  - Giao diện hoạt động đúng trên màn hình desktop ($\geq$1024px) và mobile ($\geq$375px).

## Accessibility

  - Cỡ chữ tối thiểu 16px cho nội dung chính; tiêu đề không nhỏ hơn 14px.
  - Tỉ lệ tương phản màu sắc tối thiểu 4.5:1.
  - Nút hành động tối thiểu 44$\times$44px.
  - Có text fallback cho mọi trạng thái voice.
  - Hỗ trợ người lớn tuổi: cỡ chữ có thể tăng, tốc độ TTS có thể giảm.

## Performance (mức sản phẩm)

  - Hiển thị chỉ báo ``đang xử lý'' trong vòng 500ms kể từ khi người dùng dừng nói.
  - Giao diện không được đóng băng trong quá trình AI xử lý.
  - Có cơ chế timeout và retry rõ ràng cho kết nối chậm.

## Reliability

  - Không tạo booking trùng trong cùng phiên, dù người dùng kích hoạt nhiều lần.
  - Không mất context của cuộc gọi khi chuyển sang tổng đài viên.
  - Khi kết nối gián đoạn và khách kết nối lại, phiên và thông tin được khôi phục.
  - Lỗi tool AI được xử lý có kiểm soát; lỗi nội bộ không hiển thị ra người dùng.

## Privacy và Bảo mật

  - Ghi âm cuộc gọi chỉ khi có consent của khách hàng.
  - Dữ liệu PII (số CMND, số tài khoản) không được hiển thị đầy đủ.
  - Kiểm soát truy cập theo vai trò.
  - Hỗ trợ yêu cầu xóa dữ liệu cá nhân; có audit record về hành động xóa.

## Scalability

  - Kiến trúc sản phẩm hỗ trợ thêm kênh giao tiếp mới mà không phải viết lại luồng cốt lõi.
  - Hỗ trợ thêm ngôn ngữ mà không thay đổi cấu trúc Agent core.
  - Có thể thêm nghiệp vụ mới thông qua cấu hình Agent mới.

# KPI Framework và Success Criteria

> > **Lưu ý:** Tất cả giá trị mục tiêu là **mục tiêu đề xuất cho MVP/pilot** và chưa được xác minh bằng dữ liệu production thực tế. Các con số cần được hiệu chỉnh sau khi có dữ liệu từ pilot. Tác động giảm tải hoặc giảm chi phí chỉ được đánh giá sau khi có **baseline vận hành thực tế** của AloSM.

> **North Star Metric**

> **AI Resolution Rate - Tỉ lệ cuộc gọi được giải quyết thành công không cần chuyển người thật:**
>   Số cuộc gọi AI hoàn thành tác vụ chính (đặt xe, tra cứu, FAQ) $\div$ Tổng số cuộc gọi có tác vụ rõ ràng.
>   *Mục tiêu đề xuất MVP: $\geq$60\%*

## Pilot Success Criteria (từ Product Brief)

Trong pilot với đúng nhóm người dùng mục tiêu, MVP được xem là đạt mục tiêu ban đầu khi:

  - **Tối thiểu 80\%** người tham gia hoàn tất đúng kịch bản đặt xe bằng giọng nói.
  - **Tối thiểu 65\%** yêu cầu hợp lệ được hoàn tất không cần tổng đài viên và không xảy ra lỗi ở điểm đón, điểm đến hoặc hành động đặt xe.

*Đây là ngưỡng mục tiêu cần kiểm chứng trong pilot, không phải kết quả đã đạt. Tác động giảm tải hoặc giảm chi phí chỉ được đánh giá sau khi có baseline vận hành thực tế.*

## Bảng KPI chi tiết

| **Nhóm** | **KPI** | **Mục tiêu MVP*** | **Cách đo** | **Ghi chú** |
|-|-|-|-|-|
| Adoption | Số cuộc gọi AI / ngày | Thiết lập baseline | call\_started events | Đề xuất MVP |
| Task Success | Tỉ lệ booking thành công qua AI | $\geq$70\% intent đặt xe | booking\_created / intent | Đề xuất MVP |
| Task Success | Tỉ lệ booking sai | $\leq$5\% | Booking sai / tổng AI | Đề xuất MVP |
| Experience | CSAT cuộc gọi AI | $\geq$3.5/5 | call\_rated events | Đề xuất MVP |
| Experience | Tỉ lệ bỏ cuộc (drop-off) | $\leq$20\% | call\_ended trước confirm | Đề xuất MVP |
| Experience | Số lượt hội thoại TB / booking | $\leq$8 lượt | turns per conversation | Đề xuất MVP |
| Operations | HITL rate | $\leq$40\% | human\_handoff / call\_started | Đề xuất MVP |
| Operations | TG chờ TB tổng đài viên | $\leq$2 phút | Handoff đến connected | Đề xuất MVP |
| Quality | Tỉ lệ Agent chọn đúng hành động | $\geq$85\% | Đánh giá thủ công/tự động | Đề xuất MVP |
| Quality | Tỉ lệ câu trả lời có căn cứ từ KB | $\geq$80\% | KB retrieval success | Đề xuất MVP |
| Quality | Tỉ lệ lỗi tool | $\leq$5\% | tool\_error / tool\_call | Đề xuất MVP |
| Cost | Chi phí AI / phút cuộc gọi | Thiết lập baseline | Chi phí API / số phút | Đề xuất MVP |

 * Tất cả mục tiêu trên là đề xuất chưa được xác minh bằng dữ liệu production.

# Product Analytics - Event Taxonomy

| **Event** | **Trigger** | **Actor** | **Thuộc tính ghi nhận** | **KPI liên quan** |
|-|-|-|-|-|
| call\_started | Bắt đầu cuộc gọi | Customer | user\_id, session\_id, voice\_profile | Adoption |
| microphone\_granted | Cấp quyền mic | Customer | user\_id, permission\_state | Adoption |
| transcript\_generated | STT tạo transcript | System | session\_id, turn\_id, confidence | Quality |
| text\_fallback\_used | Dùng text thay voice | Customer | session\_id, reason | Accessibility |
| address\_candidate\_selected | Chọn địa chỉ | Customer | session\_id, count | Quality |
| fare\_displayed | Giá hiển thị | System | session\_id, fare\_amount | Task success |
| booking\_confirmed | Khách xác nhận đặt xe | Customer | session\_id, booking\_id | Task success |
| booking\_created | Booking tạo thành công | System | booking\_id, turn\_count | Task success, Cost |
| booking\_failed | Tạo booking thất bại | System | booking\_id, error\_reason | Quality |
| human\_handoff\_requested | Yêu cầu gặp người thật | Customer/AI | session\_id, trigger\_type | Operations |
| operator\_connected | Operator tiếp nhận | Operator | session\_id, wait\_time | Operations |
| call\_ended | Cuộc gọi kết thúc | Customer | session\_id, duration, outcome | All |
| call\_rated | Khách đánh giá | Customer | session\_id, rating | Experience |

# Risks and Mitigations

\small

| **Risk ID** | **Rủi ro** | **KN xảy ra** | **Tác động** | **Mức** | **Biện pháp giảm thiểu** | **Owner** |
|-|-|-|-|-|-|-|
| R-01 | Độ chính xác ASR tiếng Việt với người lớn tuổi, giọng vùng miền và tiếng ồn ngoài đường | Cao | Cao |  | Hiện và xác nhận transcript; cho phép sửa; hỏi lại khi confidence thấp; kiểm thử đa dạng | AI/ML |
| R-02 | Độ trễ hội thoại (STT+LLM+TTS) kéo dài, người lớn tuổi cảm thấy bị bỏ rơi | Cao | Cao |  | Hiển thị trạng thái xử lý; timeout rõ ràng; tối ưu latency | Engineering |
| R-03 | AI tạo booking sai thông tin (điểm đón, điểm đến) | TB | Rất cao |  | Bắt buộc xác nhận trước tạo; review transcript sau booking | PO, AI |
| R-04 | Tích hợp hệ thống đặt xe tạo booking trùng hoặc báo thành công sai | TB | Rất cao |  | Kiểm thử tích hợp chặt chẽ; có cơ chế idempotency; UAT với hệ thống thật | Engineering |
| R-05 | Khách hàng không tin tưởng AI | Cao | Cao |  | Luôn cho phép chuyển người thật; minh bạch; pilot nhỏ trước | PO, UX |
| R-06 | Người lớn tuổi khó sử dụng | Cao | TB |  | UX đơn giản; chế độ nói chậm; UAT với người dùng thật | UX |
| R-07 | RAG lấy chính sách cũ | TB | Cao |  | Phiên bản và ngày hiệu lực KB; kiểm soát xuất bản chặt | AI Ops |
| R-08 | Chuyển người thật thất bại (không có operator) | TB | Cao |  | Không có operator: thông báo rõ và ghi lại; có fallback | CS Mgr |
| R-09 | Chi phí AI cao | TB | Cao |  | Theo dõi cost/call ngay từ pilot; tối ưu prompt và chọn model | PO, Eng |
| R-10 | Lộ dữ liệu cá nhân (PII) | Thấp | Rất cao |  | Che PII, phân quyền chặt, audit log, privacy review định kỳ | Security |
| R-11 | Ghi âm không có consent | Thấp | Rất cao |  | Bắt buộc consent dialog trước ghi âm | Security, PO |
| R-12 | Lưu lượng, cơ cấu yêu cầu và chi phí tổng đài hiện tại chưa có baseline | Cao | Cao |  | Thu thập baseline nội bộ trước khi đánh giá tác động MVP | PO, CS Mgr |
| R-13 | TTS phát âm sai địa danh, số | Cao | TB |  | Kiểm thử TTS với bộ địa danh; danh sách ngoại lệ phát âm | AI Ops |

# Assumptions and Dependencies

## Giả định (Assumptions)

  - Người dùng có thiết bị với microphone hoạt động khi sử dụng kênh web.
  - Kết nối internet đủ ổn định để truyền âm thanh (tối thiểu 1Mbps).
  - Có dữ liệu địa chỉ Việt Nam đủ phủ ít nhất các thành phố trong phạm vi pilot.
  - Có dịch vụ booking nghiệp vụ (hoặc sandbox) để tích hợp trong MVP.
  - Có tổng đài viên trực ca để tiếp nhận HITL ít nhất trong giờ hành chính.
  - Có tài liệu chính sách, FAQ và giá cước đã được phê duyệt để nạp vào Knowledge Base.
  - Có giọng TTS hợp lệ theo giấy phép để sử dụng trong sản phẩm.
  - Khách hàng nói tiếng Việt - MVP không cam kết hỗ trợ tiếng Anh.

## Phụ thuộc (Dependencies)

  - **Hệ thống tài khoản:** API xác thực, quản lý phiên và phân quyền.
  - **Dịch vụ bản đồ / địa chỉ:** API tra cứu và gợi ý địa chỉ tiếng Việt.
  - **Booking service:** API tạo, sửa, hủy, tra cứu booking.
  - **Hạ tầng telephony:** Cần nhà cung cấp SIP/VoIP nếu mở rộng sang điện thoại (post-MVP).
  - **Knowledge Base pipeline:** Hệ thống embedding, vector store và retrieval.
  - **Đội vận hành tổng đài:** Ít nhất N operator để hỗ trợ HITL trong pilot.
  - **Đội bảo mật và DPO:** Phê duyệt chính sách consent, lưu trữ và xóa dữ liệu.
  - **Nhà cung cấp TTS/STT:** Giấy phép, SLA và khả năng tùy biến giọng tiếng Việt.
  - **Baseline vận hành:** Dữ liệu lưu lượng, cơ cấu yêu cầu và chi phí tổng đài hiện tại của AloSM - cần thiết trước khi đánh giá tác động MVP.

# Release Plan

| **Release** | **Mục tiêu** | **Phạm vi** | **Tiêu chí hoàn thành** | **KPI theo dõi** |
|-|-|-|-|-|
| R0 - Discovery | Xác nhận bài toán | Prototype UI, kịch bản hội thoại mẫu, phỏng vấn người dùng | Phản hồi từ $\geq$10 người dùng tiềm năng; xác nhận luồng đặt xe | Định tính |
| R1 - Text Agent MVP | Xác nhận Agent logic | Hội thoại text, tool nghiệp vụ, booking simulation | Luồng text-to-booking end-to-end | Task completion, lỗi tool |
| R2 - Web Voice MVP | Voice trên web | STT, TTS, Voice Call UI, transcript, booking sandbox | Luồng voice hoàn chỉnh; HITL cơ bản | CSAT, AI Res. Rate |
| R3 - Human Handoff | Chuyển người thật | Queue, Console, context transfer, post-call note | Operator nhận đủ context | TG chờ handoff |
| R4 - AI Operations | Vận hành AI | KB UI, Agent versioning, Voice Library, Eval Dashboard | AI Ops cập nhật KB không cần kỹ sư | KB accuracy |
| R5 - Pilot Telephony | Thử nghiệm điện thoại | Số điện thoại thật, pilot hạn chế $\geq$100 cuộc gọi | Đạt Pilot Success Criteria | Tất cả KPI production |

# UAT Plan

\small

| **UAT ID** | **Mục tiêu** | **Actor** | **Preconditions** | **Steps** | **Expected Result** | **Priority** |
|-|-|-|-|-|-|-|
| UAT-01 | Đặt xe thành công | Customer | Đã ĐK, cấp quyền mic | (1) Nhấn Gọi AI (2) Nói đủ TT (3) Xác nhận | Booking tạo có mã; thẻ booking hiện |  |
| UAT-02 | Thiếu điểm đón | Customer | Đã bắt đầu gọi | Nói chỉ có điểm đến | AI hỏi lại điểm đón; chỉ 1 TT/lượt |  |
| UAT-03 | Địa chỉ mơ hồ | Customer | Đang trong cuộc gọi | Nói địa chỉ không cụ thể | AI hiện danh sách chọn; không tự chọn |  |
| UAT-04 | Nhận diện sai, khách sửa | Customer | Đang trong cuộc gọi | Transcript sai; khách sửa | Cập nhật; AI xác nhận lại TT mới |  |
| UAT-05 | Sửa TT trước xác nhận | Customer | AI đủ TT | Đổi loại xe trước xác nhận | AI cập nhật và đọc lại TT đã sửa |  |
| UAT-06 | Hủy luồng đặt xe | Customer | Đang trong luồng đặt xe | Nói ``thôi, tôi không đặt nữa'' | AI không tạo booking; hỏi có cần gì khác |  |
| UAT-07 | Yêu cầu gặp người thật | Customer | Bất kỳ lúc nào | Nói ``gặp người thật'' | AI thông báo; chuyển queue; hiện vị trí chờ |  |
| UAT-08 | AI tự động chuyển sau 2 lần thất bại | Customer | Đang hội thoại | Cung cấp TT sai 2 lần liên tiếp | AI đề xuất chuyển operator |  |
| UAT-09 | Tool nghiệp vụ lỗi | Customer | Đang trong cuộc gọi | Tool tạo booking trả về lỗi | AI thông báo; đề xuất thử lại hoặc chuyển OP |  |
| UAT-10 | Mất kết nối | Customer | Đang trong cuộc gọi | Mô phỏng mất mạng | Thông báo mất kết nối; context được lưu |  |
| UAT-11 | Operator tiếp nhận đủ context | Operator | Cuộc gọi chuyển queue | Operator nhận tiếp nhận | Thấy transcript đầy đủ, tóm tắt AI, TT khách |  |
| UAT-12 | Tài xế nhận chuyến | Driver | Booking đã tạo | TX nhận TB và nhận | Booking đổi trạng thái; khách nhận TB |  |
| UAT-13 | Admin cập nhật KB | AI Ops | ĐK admin | Upload; kiểm thử; xuất bản | Tài liệu xuất hiện trong KB; câu hỏi test truy xuất đúng |  |
| UAT-14 | Từ chối consent ghi âm | Customer | Pre-call | Từ chối consent | Cuộc gọi diễn ra; không có file ghi âm |  |

# Definition of Ready (DOR)

Một feature chỉ được đưa vào sprint khi đáp ứng **tất cả** các tiêu chí sau:

  - **$\square$** Có mục tiêu rõ ràng và lý do kinh doanh được ghi nhận.
  - **$\square$** Có actor và người dùng cụ thể được xác định.
  - **$\square$** Có ít nhất một user story hoàn chỉnh.
  - **$\square$** Có acceptance criteria theo cấu trúc Given-When-Then.
  - **$\square$** Có business rule liên quan được liệt kê.
  - **$\square$** Có UI flow hoặc wireframe (nếu có tác động giao diện).
  - **$\square$** Có ít nhất một trường hợp lỗi và alternate flow được mô tả.
  - **$\square$** Dữ liệu đầu vào cần thiết được xác định.
  - **$\square$** Phụ thuộc kỹ thuật và sản phẩm được xác định và không chặn sprint.
  - **$\square$** Có chỉ số đo lường thành công hoặc KPI liên quan.
  - **$\square$** Được PO/BA xem xét và xác nhận đủ rõ để phát triển.

# Definition of Done (DOD)

Một feature chỉ được tuyên bố hoàn thành khi đáp ứng **tất cả** các tiêu chí sau:

  - **$\square$** Đáp ứng toàn bộ acceptance criteria đã định nghĩa.
  - **$\square$** Đã kiểm thử unit, integration (theo quy trình nhóm).
  - **$\square$** Đã xử lý tất cả error state và alternate flow được mô tả trong FR.
  - **$\square$** Analytics event tương ứng đã triển khai và xác minh hoạt động.
  - **$\square$** Kiểm tra phân quyền đã được test.
  - **$\square$** Kiểm tra accessibility cơ bản (contrast, nút, text fallback).
  - **$\square$** Tài liệu nội bộ cập nhật nếu có thay đổi luồng hoặc business rule.
  - **$\square$** UAT với người dùng hoặc đại diện người dùng đã thực hiện.
  - **$\square$** Không còn lỗi blocker hoặc critical.
  - **$\square$** Được Product Owner xem xét và chấp nhận chính thức.

# Traceability Matrix

> > Bảng dưới thể hiện các dòng mẫu đại diện cho các luồng quan trọng. Ma trận đầy đủ được duy trì trong công cụ quản lý yêu cầu (JIRA / Confluence).

\small

| **Business Objective** | **Epic** | **FR** | **US** | **Accept. Criteria** | **KPI** | **UAT** |
|-|-|-|-|-|-|-|
| Đặt xe bằng giọng nói | EP-05 | FR-BOOK-004,005 | US-009,010 | Booking sau xác nhận | Booking success | UAT-01,05 |
| Giảm tải tổng đài | EP-07,08 | FR-HITL-001,002,004 | US-011,012,013 | Operator đủ context | HITL rate | UAT-07,08,11 |
| Bảo vệ dữ liệu KH | EP-16 | FR-AUTH-003 | US-002,023 | Consent trước ghi âm | Privacy | UAT-14 |
| Đặt đúng địa chỉ | EP-05 | FR-BOOK-002 | US-007 | Không tự chọn | Booking error | UAT-03 |
| Fallback khi mic lỗi | EP-17 | FR-CALL-007 | US-005 | Text fallback hoạt động | Fallback usage | UAT-10 |
| Chất lượng KB | EP-11 | FR-KB-004,005 | US-017,018 | Draft không ảnh hưởng prod | KB accuracy | UAT-13 |
| Đo lường được KPI | EP-14 | FR-ADMIN-004 | US-020,029 | Dashboard hiện đúng | Đo được KPI | Sau release |

# Open Questions

> **Các câu hỏi cần xác nhận**

> Các câu hỏi dưới đây cần được xác nhận trước khi phát triển các tính năng liên quan. ``Mở'' nghĩa là chưa có quyết định chính thức.

| **OQ ID** | **Câu hỏi** | **Người quyết định** | **Thời hạn** | **Tác động nếu chưa** | **TT** |
|-|-|-|-|-|-|
| OQ-01 | Độ chính xác ASR tiếng Việt với người lớn tuổi, giọng vùng miền và tiếng ồn ngoài đường đạt mức nào? Có đủ cho MVP không? | AI/ML | Trước R2 | Nếu không đủ: cần fallback mạnh hơn hoặc thu hẹp phạm vi |  |
| OQ-02 | Độ trễ hội thoại (STT + LLM + TTS) có đủ thấp để người lớn tuổi không cảm thấy bị bỏ rơi? | Engineering, AI | Trước R2 | Ảnh hưởng UX và ngưỡng timeout |  |
| OQ-03 | Hệ thống tích hợp booking có đảm bảo không tạo trùng và không báo thành công sai không? | Engineering | Trước R2 | Ảnh hưởng BR-005 và FR-BOOK-007 |  |
| OQ-04 | Lưu lượng, cơ cấu yêu cầu và chi phí vận hành tổng đài hiện tại của AloSM là bao nhiêu? Đây là baseline cần thiết để đánh giá tác động kinh doanh sau MVP | PO, CS Mgr | Trước R1 | Nếu không có: không thể tính ROI và đặt KPI giảm tải thực tế |  |
| OQ-05 | Chính sách cụ thể về ghi âm, lưu transcript, thời gian giữ dữ liệu và bảo vệ SĐT / địa chỉ khách hàng là gì? | DPO, PO | Trước R2 | Ảnh hưởng consent flow, storage và tuân thủ pháp lý |  |
| OQ-06 | MVP dùng booking service thật hay sandbox/mô phỏng? | PO, Engineering | Trước R2 | Không thể thiết kế tool tích hợp và luồng booking |  |
| OQ-07 | Có ghi âm cuộc gọi hay chỉ lưu transcript? | PO, DPO | Trước R2 | Ảnh hưởng consent flow, storage và tính năng replay |  |
| OQ-08 | Thời gian lưu transcript và recording là bao lâu? | DPO, PO | Trước R2 | Không thể thiết kế chính sách retention |  |
| OQ-09 | Giá hiển thị là ước tính hay cố định? Nguồn giá lấy từ đâu? | PO, Business | Trước R2 | Không thể viết FR-BOOK-003 và BR-003 chính xác |  |
| OQ-10 | Khi nào bắt buộc phải chuyển người thật (ngưỡng tự động ngoài 2 lần thất bại)? | PO, CS Mgr | Trước R2 | Không cấu hình được trigger HITL tự động |  |
| OQ-11 | Tổng đài viên có thể sửa booking đến mức nào? | CS Mgr, PO | Trước R3 | Không xác định phạm vi form Sửa booking |  |
| OQ-12 | Ai có quyền xuất bản tài liệu lên Knowledge Base? | PO, AI Ops | Trước R4 | Không thiết lập workflow phê duyệt KB |  |
| OQ-13 | MVP hỗ trợ bao nhiêu thành phố/khu vực? | PO, Business | Trước R2 | Không xác định phạm vi dữ liệu địa chỉ |  |
| OQ-14 | Có bắt buộc đăng nhập mới được gọi AI không? | PO, Engineering | Trước R1 | Ảnh hưởng kiến trúc xác thực và lưu lịch sử |  |
| OQ-15 | Transcript có được dùng để cải thiện model không? | PO, DPO, AI | Trước R4 | Phải ghi rõ trong consent và chính sách dữ liệu |  |

# Tài liệu tham khảo

  - Tổng cục Thống kê và UNFPA Việt Nam (2021). *Population Ageing and Older Persons in Viet Nam*. Hà Nội: GSO.
  \url{https://vietnam.unfpa.org/sites/default/files/pub-pdf/ageing_report_from_census_2019_eng_final27082021.pdf}

  - Vu, N.C., Tran, M.T., Dang, L.T., Chei, C.L. \& Saito, Y. (chủ biên) (2020). *Ageing and Health in Viet Nam*. Jakarta: ERIA; Hà Nội: PHAD.
  \url{https://www.eria.org/uploads/media/Books/2020-Ageing-and-Health-VietNam/Ageing-and-Health-in-Viet-Nam-new.pdf}

  - Rakuten Insight Global (2025). *2025 Ride-Hailing App Landscape in Vietnam*.
  \url{https://insight.rakuten.com/2025-ride-hailing-app-landscape-in-vietnam/}

  - AloSM, số liệu doanh nghiệp công bố, truy cập ngày 02/08/2026.
  \url{https://www.alosm.vn}

  - GreenSM Voice Product Brief (2026). *AI Voice Customer Service Agent for Green SM*. Team T160. [Tài liệu nội bộ, dùng làm nền tảng cho PRD này.]

# Kết luận và Bước tiếp theo

Tài liệu PRD này xác định phạm vi, yêu cầu và định hướng sản phẩm cho **AloSM Voice AI Agent phiên bản MVP**, được xây dựng trên nền tảng của GreenSM Voice Product Brief và mở rộng thành PRD đầy đủ.

## Bước tiếp theo đề xuất

  - **Review PRD** với đầy đủ stakeholder; thu thập phản hồi.
  - **Giải quyết Open Questions** - đặc biệt OQ-01 (ASR), OQ-04 (baseline tổng đài), OQ-06 (booking service) là tiên quyết.
  - **UX/UI wireframe** cho các màn hình MVP dựa trên User Journey.
  - **Engineering ước lượng** và xác nhận tính khả thi kỹ thuật.
  - **AI/ML Team đánh giá** chất lượng ASR và TTS tiếng Việt với bộ kiểm thử đa dạng giọng (giọng vùng miền, người lớn tuổi, tiếng ồn).
  - **Khởi động R0** - Discovery và Prototype trước khi phát triển đầy đủ.
  - **Thiết lập tracking analytics** dựa trên Event Taxonomy từ ngày đầu.
  - **Thu thập baseline vận hành tổng đài** hiện tại - số liệu này là tiền điều kiện để đánh giá thành công thật sự của MVP.

> > **Tài liệu:** AloSM Voice AI Agent - PRD v1.0 (tham khảo GreenSM Voice Product Brief, Team T160)
>   **Ngày:** 02/08/2026 \qquad **Bảo mật:** Nội bộ - Không phân phối bên ngoài.
>   Mọi số liệu KPI trong tài liệu này là **mục tiêu đề xuất chưa xác minh bằng dữ liệu production**.