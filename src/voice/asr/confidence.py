"""Risk-weighted ASR confidence gate — Phần 3 (`docs/voice-ai/voice_ai_overview.md` §5/§6).

BR-001 bắt buộc xác nhận bằng lời nói trước khi gọi Booking API, nên ngưỡng
tin cậy khi user đang ở bước xác nhận đặt xe phải cao hơn ngưỡng bình thường
(0.80 so với 0.60 — xem `config.py`: `voice_asr_confidence_threshold`,
`voice_asr_booking_confidence_threshold`).

`gateway.py` (Phần 2) chỉ gọi qua `passes()`, không tự so sánh threshold —
đổi logic nghiệp vụ ở đây, không cần sửa gateway.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.voice.schemas import ASRResult


@dataclass
class ConfidenceGate:
    default_threshold: float = 0.60
    booking_confirmation_threshold: float = 0.80

    def threshold_for(self, *, is_booking_confirmation: bool = False) -> float:
        return self.booking_confirmation_threshold if is_booking_confirmation else self.default_threshold

    def passes(self, asr_result: ASRResult, *, is_booking_confirmation: bool = False) -> bool:
        if not asr_result.text.strip():
            return False
        return asr_result.confidence >= self.threshold_for(is_booking_confirmation=is_booking_confirmation)
