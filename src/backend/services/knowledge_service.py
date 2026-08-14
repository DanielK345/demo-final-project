from __future__ import annotations

import re

from src.agents.rag import BaseRetriever, KnowledgeDocument, RetrievalResult

# src/agents/rag/ (từ nhánh feature/agentic-ai) chỉ định nghĩa interface trừu tượng
# (BaseRetriever, KnowledgeDocument) — chưa có bộ nội dung + retriever cụ thể nào.
# Bản cũ của AgentToolExecutor hardcode đúng 2 câu FAQ làm toàn bộ "knowledge base".
# Đây là 1 bộ nội dung thật (khớp đúng chính sách đã hiển thị nơi khác trong app:
# ProfilePage/PaymentPage/TrackingPage) + 1 retriever thật (so khớp từ khoá, không
# cần embedding/API ngoài) — không phải giả lập. Mỗi tài liệu viết theo đúng khuôn
# FAQ thật (câu hỏi + câu trả lời trong cùng nội dung) vì FAQWorkflow.min_score=0.75
# (src/agents/workflows/faq.py) chặn khá gắt — cố tình giữ nguyên ngưỡng đó (chống
# trả lời bừa/hallucination), không hạ thấp để "lách" — mà viết nội dung khớp từ khoá
# tự nhiên hơn, đúng cách một trang FAQ thật vẫn hay được viết.
_DOCUMENTS: tuple[KnowledgeDocument, ...] = (
    KnowledgeDocument(
        document_id="faq-payment",
        content="Thanh toán bằng cách nào? Khách có thể thanh toán bằng tiền mặt hoặc AloSM Pay (liên kết ví/thẻ ngân hàng). Giá cước được hiển thị rõ trước khi xác nhận đặt xe, không phát sinh phụ phí ẩn.",
        source="AloSM FAQ — Thanh toán",
    ),
    KnowledgeDocument(
        document_id="faq-cancellation",
        content="Chính sách huỷ chuyến như thế nào? Khách có thể huỷ chuyến miễn phí trước khi tài xế xác nhận nhận chuyến. Sau khi tài xế đã di chuyển tới điểm đón, huỷ chuyến có thể tính phí huỷ theo chính sách hiển thị trong ứng dụng.",
        source="AloSM FAQ — Huỷ chuyến",
    ),
    KnowledgeDocument(
        document_id="faq-pricing",
        content="Giá cước tính như thế nào? Giá cước ước tính dựa trên khoảng cách và loại xe (xe máy, ô tô 4 chỗ, ô tô 7 chỗ), hiển thị trước khi khách xác nhận đặt xe nên không đổi bất ngờ giữa chuyến trừ khi lộ trình thực tế thay đổi.",
        source="AloSM FAQ — Giá cước",
    ),
    KnowledgeDocument(
        document_id="faq-safety",
        content="Đi xe có an toàn không? Mọi chuyến đi đều có bảo hiểm chuyến đi tự động kích hoạt, hiển thị biển số và thông tin tài xế trước khi lên xe, và có thể liên hệ tổng đài viên bất cứ lúc nào trong hành trình nếu cần hỗ trợ khẩn cấp.",
        source="AloSM FAQ — An toàn",
    ),
    KnowledgeDocument(
        document_id="faq-contact",
        content="Có cần cung cấp số điện thoại hay email không? Agent không hỏi số điện thoại hay email trong hội thoại — số điện thoại liên hệ tài xế được lấy tự động từ số đã đăng ký tài khoản, không thu thập thêm thông tin cá nhân qua trò chuyện.",
        source="AloSM FAQ — Quyền riêng tư",
    ),
    KnowledgeDocument(
        document_id="faq-pickup-change",
        content="Đổi điểm đón hoặc điểm đến bằng cách nào? Khách có thể đổi điểm đón hoặc điểm đến bằng cách nói lại địa điểm mới trước khi xác nhận đặt xe; sau khi đã xác nhận, cần liên hệ tổng đài viên để điều chỉnh.",
        source="AloSM FAQ — Đổi điểm đón/đến",
    ),
)

# Từ dừng tiếng Việt phổ biến (đại từ, hư từ, từ hỏi chung chung) — loại khỏi câu hỏi
# trước khi so khớp, để tỉ lệ trùng từ khoá phản ánh đúng các từ MANG NGHĨA thay vì bị
# pha loãng bởi "tôi", "có thể", "như thế nào" xuất hiện trong hầu hết mọi câu hỏi.
_STOPWORDS = frozenset(
    """
    tôi bạn mình có thể là và hoặc của cho được này đó như thế nào bao nhiêu gì sao
    vậy rất thì mà để khi sẽ đã đang với về trong trên dưới một các những ạ à ơi dạ
    xin cho hỏi muốn cần làm ơn giúp
    """.split()
)


def _meaningful_tokens(text: str) -> set[str]:
    words = re.findall(r"[\w]+", text.casefold(), re.UNICODE)
    return {word for word in words if word and word not in _STOPWORDS}


def _keyword_overlap_score(query_tokens: set[str], content: str) -> float:
    content_tokens = _meaningful_tokens(content)
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = query_tokens & content_tokens
    return round(len(overlap) / len(query_tokens), 4)


class KeywordFaqRetriever(BaseRetriever):
    """Retriever thật, deterministic: so khớp từ khoá MANG NGHĨA (đã lọc từ dừng tiếng
    Việt, không phân biệt hoa/thường, không cần embedding hay API ngoài) giữa câu hỏi
    và nội dung FAQ, xếp hạng theo tỉ lệ trùng. Đơn giản hơn embedding-based RAG thật
    nhưng là logic có căn cứ, không phải trả cố định vài tài liệu bất kể câu hỏi như
    bản cũ."""

    def __init__(self, documents: tuple[KnowledgeDocument, ...] = _DOCUMENTS) -> None:
        self.documents = documents

    async def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        query_tokens = _meaningful_tokens(query)
        scored = [
            RetrievalResult(document=document, score=_keyword_overlap_score(query_tokens, document.content))
            for document in self.documents
        ]
        scored = [result for result in scored if result.score > 0]
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]


class KnowledgeService:
    def __init__(self, retriever: BaseRetriever | None = None) -> None:
        self.retriever = retriever or KeywordFaqRetriever()

    async def retrieve(self, query: str, *, top_k: int = 3) -> list[dict[str, object]]:
        results = await self.retriever.retrieve(query, top_k=top_k)
        return [
            {
                "content": result.document.content,
                "source": result.document.source,
                "score": result.score,
                "metadata": result.document.metadata,
                "citation_id": result.document.document_id,
            }
            for result in results
        ]
