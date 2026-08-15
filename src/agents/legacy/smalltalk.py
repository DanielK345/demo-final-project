import re
from dataclasses import dataclass


@dataclass(frozen=True)
class UnsupportedUtteranceResponse:
    message: str
    reason: str


_GREETING_PATTERNS = (
    re.compile(r"^(?:xin\s+)?chào(?:\s+(?:bạn|anh|chị|em|alo))?[!.?]*$", re.IGNORECASE),
    re.compile(r"^(?:alo|hello|hi|hey)[!.?]*$", re.IGNORECASE),
)
_NEGATIVE_SENTIMENT_PATTERNS = (
    re.compile(r"\b(?:không|chẳng)\s+(?:thích|ưa|muốn)\b", re.IGNORECASE),
    re.compile(r"\b(?:tệ|chán|bực|khó chịu|thất vọng)\b", re.IGNORECASE),
)
_OFF_TOPIC_PATTERNS = (
    re.compile(r"\b(?:đi ngủ|ngủ|ăn cơm|mua xe|bán xe|xem phim)\b", re.IGNORECASE),
)
_GARBAGE_PATTERNS = (
    re.compile(r"^[a-z]{3,}$", re.IGNORECASE),
    re.compile(r"^[^\w\s]+$"),
)


def unsupported_utterance_response(transcript: str) -> UnsupportedUtteranceResponse:
    normalized = " ".join(transcript.strip().split())
    if not normalized:
        return UnsupportedUtteranceResponse(
            message="Tôi chưa nghe rõ. Bạn muốn đặt xe, tra cứu chuyến đi hay hỏi thông tin dịch vụ?",
            reason="The user input is empty or inaudible.",
        )
    if any(pattern.search(normalized) for pattern in _GREETING_PATTERNS):
        return UnsupportedUtteranceResponse(
            message="Chào bạn. Tôi có thể hỗ trợ đặt xe, tra cứu chuyến đi hoặc trả lời thông tin dịch vụ.",
            reason="The user greeted the assistant without a task.",
        )
    if any(pattern.search(normalized) for pattern in _NEGATIVE_SENTIMENT_PATTERNS):
        return UnsupportedUtteranceResponse(
            message=(
                "Tôi hiểu. Nếu bạn đang gặp vấn đề với dịch vụ, tôi có thể hỗ trợ tra cứu chuyến, "
                "giải đáp thông tin hoặc chuyển tổng đài viên."
            ),
            reason="The user expressed negative sentiment without a supported task.",
        )
    if any(pattern.search(normalized) for pattern in _OFF_TOPIC_PATTERNS):
        return UnsupportedUtteranceResponse(
            message="Tôi chỉ hỗ trợ đặt xe, tra cứu chuyến đi và thông tin dịch vụ AloSM. Bạn muốn tôi hỗ trợ mục nào?",
            reason="The user asked for something outside supported workflows.",
        )
    if len(normalized) < 4 or any(pattern.search(normalized) for pattern in _GARBAGE_PATTERNS):
        return UnsupportedUtteranceResponse(
            message="Tôi chưa hiểu nội dung đó. Bạn có thể nói rõ là muốn đặt xe, tra cứu chuyến đi hay hỏi thông tin dịch vụ không?",
            reason="The user input is not meaningful enough to select a workflow.",
        )
    return UnsupportedUtteranceResponse(
        message="Tôi chưa xác định được yêu cầu. Bạn muốn đặt xe, tra cứu chuyến đi hay hỏi thông tin dịch vụ?",
        reason="The user's intent is not clear enough to select a workflow.",
    )
