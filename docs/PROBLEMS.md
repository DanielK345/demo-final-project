#Backend

Process chậm: đặt xe, kết thúc phiên (kiểm tra phần query DB)

#Voice

Latency cao, chưa có VAD, user barge-in

#Agent

Mất context khi user đòi chuyển địa điểm: VD: gợi ý 1 list địa chỉ, user chọn cái số 1, sau đó đổi lại cái số 2 nhưng agent ko hiểu phải hỏi lại

Mất thông tin khi user đòi chuyển thông tin: ban đầu user nói luôn điểm đón A, điểm đến B, xe loại C, nhưng khi đổi điếm đến, điểm đón thì mất luôn loại xe, phải hỏi lại

Optional: Confirm điểm đón, điểm đi, phương tiện mỗi lượt trước khi đến thông tin tiếp theo, ví dụ confirm điểm đón (địa chỉ chính xác) là A trước khi hỏi địa chỉ chính xác của điểm đến B.
