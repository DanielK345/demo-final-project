# Tài liệu User Story — Tính năng AI Agent Tổng Đài Giọng Nói

**Dự án:** AloSM — Hệ thống đặt xe bằng giọng nói  
**Ngày cập nhật:** 2026-08-19  
**Trạng thái:** Sẵn sàng demo

---

## Tổng quan

Dự án xây dựng một **trợ lý giọng nói thông minh** thay thế tổng đài viên con người. Khách hàng gọi điện, nói yêu cầu đặt xe bằng tiếng Việt, hệ thống tự hiểu, xác nhận thông tin và đặt xe — không cần bấm app, không cần chờ nhân viên tổng đài.

### Vấn đề cần giải quyết

- Tổng đài truyền thống tốn nhiều nhân sự và hay bị nghẽn giờ cao điểm.
- Người lớn tuổi hoặc không quen app khó đặt xe qua smartphone.
- Hệ thống cần hiểu tiếng Việt tự nhiên, kể cả tên địa danh địa phương.

### Hướng giải quyết

Xây dựng một AI Agent hoạt động như tổng đài viên ảo:

1. Nhận cuộc gọi → chuyển giọng nói thành chữ (STT)
2. AI hiểu yêu cầu → hỏi thêm thông tin còn thiếu
3. Tìm địa điểm → báo giá → đọc lại để khách xác nhận
4. Khách đồng ý → đặt xe → thông báo kết quả bằng giọng nói (TTS)
5. Nếu AI không xử lý được → chuyển sang tổng đài viên người thật kèm đầy đủ ngữ cảnh

---

## Kiến trúc hệ thống (giải thích đơn giản)

```
Khách gọi điện
  → Giọng nói được chuyển thành văn bản (STT)
    → AI Agent đọc văn bản, hiểu ý định, quyết định bước tiếp theo
      → Tìm địa điểm / Báo giá / Đặt xe (qua các dịch vụ phụ trợ)
        → Kết quả được đọc lại thành giọng nói (TTS) trả về cho khách
```

**Nguyên tắc quan trọng:** AI Agent chỉ *ra quyết định* — không tự gọi API bên ngoài, không tự tạo giá hay mã chuyến. Mọi hành động thật (đặt xe, tìm địa điểm) đều do Backend thực hiện và trả kết quả về cho Agent.

---

## User Stories

---

### US-01 — Đặt xe bằng giọng nói (Happy Path)

> **Là** khách hàng gọi điện đến tổng đài,  
> **tôi muốn** nói địa chỉ đón và địa chỉ đến bằng tiếng Việt tự nhiên,  
> **để** hệ thống tự tìm địa điểm, báo giá và đặt xe mà không cần bấm app.

**Luồng hoạt động:**

| Bước | Khách nói | Hệ thống làm |
|------|-----------|--------------|
| 1 | "Cho tôi đặt xe" | AI bắt đầu luồng đặt xe, hỏi điểm đón |
| 2 | "Đón ở Hồ Hoàn Kiếm" | Tìm địa điểm, đọc lại tên để xác nhận |
| 3 | "Đúng rồi" | Lưu điểm đón, hỏi điểm đến |
| 4 | "Đến sân bay Nội Bài" | Tìm địa điểm, đọc lại |
| 5 | "Ừ đúng" | Lưu điểm đến, hỏi loại xe |
| 6 | "Xe bốn chỗ" | Tính giá, đọc lại toàn bộ thông tin |
| 7 | "Tôi xác nhận đặt chuyến này" | Tạo booking, thông báo mã chuyến |

**Tiêu chí chấp nhận (Acceptance Criteria):**

- [ ] Hệ thống hỏi đúng một thông tin mỗi lượt, không hỏi nhiều thứ cùng lúc
- [ ] Chỉ tạo booking sau khi khách nói xác nhận rõ ràng (không tạo khi khách chỉ nói "ừ", "được", "ok")
- [ ] Thay đổi địa điểm hoặc loại xe → giá cũ bị xóa, phải tính lại
- [ ] Không bịa địa chỉ, giá, ETA hoặc mã chuyến
- [ ] Toàn bộ luồng chạy được lặp lại ổn định trong demo

---

### US-02 — Xác nhận địa điểm khi có nhiều lựa chọn

> **Là** khách hàng nói địa chỉ chưa đủ rõ,  
> **tôi muốn** AI đọc cho tôi các lựa chọn địa điểm gần đúng,  
> **để** tôi chọn đúng điểm đón/đến mà không bị nhầm.

**Tiêu chí chấp nhận:**

- [ ] Nếu tìm được nhiều kết quả → AI đọc danh sách và hỏi khách chọn số mấy
- [ ] Nếu chỉ có một kết quả → AI đọc tên địa điểm và hỏi "có đúng không?"
- [ ] Nếu không tìm được kết quả nào → AI hỏi khách nói lại hoặc nói rõ hơn
- [ ] Không tự chọn địa điểm mà không có xác nhận từ khách

---

### US-03 — Nhận diện giọng nói tiếng Việt kém → yêu cầu nói lại

> **Là** khách hàng đang gọi điện trong môi trường ồn hoặc nói không rõ,  
> **tôi muốn** hệ thống nhận biết khi không nghe rõ và yêu cầu tôi nói lại,  
> **để** không bị đặt xe sai địa điểm do nhận dạng nhầm.

**Tiêu chí chấp nhận:**

- [ ] Khi độ tin cậy nhận dạng giọng nói thấp hơn ngưỡng → AI hỏi khách nói lại hoặc nhập tay
- [ ] Không lưu địa điểm khi chưa vượt ngưỡng tin cậy cho địa danh quan trọng
- [ ] Không tự "đoán" địa chỉ và tiếp tục mà không hỏi lại khách

---

### US-04 — Sửa thông tin trước khi xác nhận

> **Là** khách hàng vừa cung cấp thông tin sai,  
> **tôi muốn** sửa lại điểm đón, điểm đến hoặc loại xe bất kỳ lúc nào trước khi xác nhận,  
> **để** booking cuối cùng chính xác với yêu cầu thật của tôi.

**Tiêu chí chấp nhận:**

- [ ] Khách nói "đổi điểm đón thành X" → AI tìm lại địa điểm mới, xóa giá cũ, tính lại
- [ ] Khách sửa loại xe → AI cập nhật và tính lại giá
- [ ] Sau mỗi lần sửa → AI đọc lại toàn bộ thông tin trước khi hỏi xác nhận
- [ ] Xác nhận cũ mất hiệu lực khi có thay đổi → phải xác nhận lại từ đầu

---

### US-05 — Chuyển sang tổng đài viên người thật

> **Là** khách hàng có vấn đề phức tạp mà AI không xử lý được,  
> **tôi muốn** được chuyển sang nhân viên tổng đài thật,  
> **để** vấn đề của tôi được giải quyết đầy đủ và tôi không phải kể lại từ đầu.

**Khi nào chuyển người:**

- Khách yêu cầu gặp người thật
- AI không nghe rõ quá nhiều lần liên tiếp
- Khách báo khẩn cấp hoặc tai nạn
- Công cụ hệ thống bị lỗi nghiêm trọng
- Khách khiếu nại cần phán đoán con người

**Tiêu chí chấp nhận:**

- [ ] Khi chuyển người → gửi kèm: lý do chuyển, tóm tắt hội thoại, thông tin đã thu thập
- [ ] Thông tin nhạy cảm được che một phần trước khi gửi sang tổng đài viên
- [ ] Khách không phải kể lại từ đầu với tổng đài viên
- [ ] AI không tiếp tục xử lý booking sau khi đã chuyển người

---

### US-06 — Khôi phục phiên khi mất kết nối

> **Là** khách hàng bị rớt kết nối giữa chừng khi đang đặt xe,  
> **tôi muốn** gọi lại và tiếp tục từ chỗ đã dừng,  
> **để** không phải bắt đầu lại toàn bộ quy trình.

**Tiêu chí chấp nhận:**

- [ ] Khi gọi lại → hệ thống nhận ra khách và đọc lại trạng thái trước đó
- [ ] Thông tin địa điểm và loại xe đã nhập không bị mất
- [ ] Nếu không khôi phục được → AI thông báo rõ và bắt đầu lại, không im lặng

---

## Definition of Done (Tiêu chí "Xong thật sự")

Một tính năng chỉ được coi là **hoàn thành** khi đáp ứng đủ các mục sau:

### Kỹ thuật

| # | Tiêu chí | Kiểm tra bằng cách nào |
|---|----------|------------------------|
| 1 | Tất cả test tự động pass | Chạy `pytest`, không có test đỏ |
| 2 | Code không có lỗi style | Chạy `ruff check`, không cảnh báo |
| 3 | Không có thông tin nhạy cảm trong code | Kiểm tra Git, không thấy password/API key |
| 4 | Cấu trúc dữ liệu Frontend và Backend khớp nhau | Kiểm tra schema/type definition |

### Chất lượng sản phẩm

| # | Tiêu chí | Mô tả |
|---|----------|-------|
| 5 | Luồng happy path chạy ổn định | Demo được 3 lần liên tiếp không lỗi |
| 6 | Dữ liệu demo được đánh nhãn rõ | Giá/địa điểm demo phải ghi rõ "DEMO", không giả vờ là thật |
| 7 | Mọi thay đổi quan trọng có xác nhận | Booking không tạo tự động khi chưa có "xác nhận đặt chuyến" |
| 8 | Lỗi được xử lý lịch sự | Khi AI không hiểu → hỏi lại, không crash |

### Tài liệu

| # | Tiêu chí | Mô tả |
|---|----------|-------|
| 9 | Blocker bên ngoài ghi vào `mustdo.md` | Ví dụ: cần API key thật, cần bật dịch vụ maps thật |
| 10 | Tính năng chưa hoàn thiện không được tuyên bố là xong | Dữ liệu fake phải ghi trạng thái `DEMO` hoặc `EXTERNAL_BLOCKED` |

---

## Trạng thái hiện tại

| Tính năng | Trạng thái | Ghi chú |
|-----------|------------|---------|
| US-01 Đặt xe happy path | ✅ DEMO | Luồng đầy đủ, dùng dữ liệu fake có nhãn |
| US-02 Chọn địa điểm | ✅ DEMO | Tìm trong bộ dữ liệu mẫu |
| US-03 ASR tin cậy thấp | ✅ IMPLEMENTED | Phát hiện và yêu cầu nói lại |
| US-04 Sửa thông tin | ✅ IMPLEMENTED | Tự động xóa giá cũ khi sửa |
| US-05 Chuyển người thật | ✅ DEMO | Lifecycle đủ, chuyển điện thoại thật là bước tiếp theo |
| US-06 Khôi phục phiên | ✅ IMPLEMENTED | Đọc lại trạng thái khi gọi lại |
| Maps API thật | ⏳ EXTERNAL_BLOCKED | Cần chọn provider và API key — xem `mustdo.md` |
| Giá/ETA thật | ⏳ EXTERNAL_BLOCKED | Cần dữ liệu nghiệp vụ từ Product/Finance |
| Chuyển điện thoại thật | ⏳ RELEASE_GATED | Cần hạ tầng telephony/SIP |

---

## Ghi chú cho buổi demo

1. **Dữ liệu địa điểm:** Dùng bộ mẫu có sẵn — tên địa điểm thật, tọa độ thật, nhưng là dữ liệu tĩnh.
2. **Giá và ETA:** Được tính theo công thức đơn giản để demo — gắn nhãn ước tính, không phải giá thật từ nhà cung cấp.
3. **Booking:** Tạo được mã booking, lưu trong phiên — chưa kết nối hệ thống dispatch thật.
4. **Giọng nói:** Hoạt động qua trình duyệt web — chưa phải số điện thoại thật.

Tất cả giới hạn trên đều được ghi rõ trong code và tài liệu — không có phần nào giả vờ là production mà chưa đủ điều kiện.
