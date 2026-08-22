from __future__ import annotations

import re

from src.agents.faq_intent import faq_aliases, normalize_faq_text
from src.agents.rag import BaseRetriever, KnowledgeDocument, RetrievalResult
from src.backend.services.policy_service import PolicyCatalog, load_policy_catalog

_STOPWORDS = frozenset(
    """
    tôi bạn mình có thể là và hoặc của cho được này đó như thế nào bao nhiêu gì sao
    vậy rất thì mà để khi sẽ đã đang với về trong trên dưới một các những ạ à ơi dạ
    xin cho hỏi muốn cần làm ơn giúp chính sách điều khoản
    """.split()
)

_CATEGORY_HINTS: dict[str, str] = {
    "account": "tài khoản đăng ký độ tuổi mật khẩu gian lận sử dụng",
    "privacy": "riêng tư dữ liệu cá nhân cookie ghi âm audio transcript marketing quảng cáo consent đồng ý",
    "pricing": "giá cước phí phụ phí cầu đường đỗ xe lộ trình xác nhận",
    "booking": "đặt chuyến hủy chuyến điểm đón tài xế",
    "payment": "thanh toán hoàn tiền bồi thường hóa đơn tranh chấp",
    "safety": "an toàn tai nạn dây an toàn trẻ em hành khách tài xế quấy rối hút thuốc",
    "support": "khiếu nại tổng đài hỗ trợ mất đồ tranh chấp chuyển nhân viên",
    "governance": "pháp luật pháp nhân hotline email liên hệ cập nhật hiệu lực tòa án",
}


def _meaningful_tokens(text: str) -> set[str]:
    words = re.findall(r"[\w]+", text.casefold(), re.UNICODE)
    return {word for word in words if word and word not in _STOPWORDS}


def _score(query: str, query_tokens: set[str], document: KnowledgeDocument) -> float:
    normalized_query = normalize_faq_text(query)
    aliases = document.metadata.get("faq_aliases", ())
    alias_score = max(
        (
            0.9 + min(0.099, len(alias) / 1000)
            for alias in aliases
            if re.search(rf"\b{re.escape(alias)}\b", normalized_query)
        ),
        default=0.0,
    )
    searchable = f"{document.content} {document.metadata.get('search_hints', '')}"
    document_tokens = _meaningful_tokens(searchable)
    if not query_tokens or not document_tokens:
        return alias_score
    overlap = query_tokens & document_tokens
    if not overlap:
        return 0.0
    coverage = len(overlap) / len(query_tokens)
    if len(overlap) >= 2:
        coverage = max(coverage, 0.75)
    return round(max(alias_score, min(1.0, coverage)), 4)


def _documents(catalog: PolicyCatalog) -> tuple[KnowledgeDocument, ...]:
    return tuple(
        KnowledgeDocument(
            document_id=f"policy-{rule.id}",
            content=f"{rule.title}. {rule.content}",
            source=f"AloSM Policy {catalog.catalog_version} — {rule.citation}",
            metadata={
                "category": rule.category,
                "rule_id": rule.id,
                "citation": rule.citation,
                "catalog_status": catalog.status,
                "source_sha256": catalog.source_sha256,
                "source_attribution": catalog.source_attribution,
                "legal_notice": catalog.legal_notice,
                "search_hints": _CATEGORY_HINTS.get(rule.category, ""),
                "faq_aliases": faq_aliases(rule.id),
            },
            version=catalog.catalog_version,
            effective_at=catalog.effective_from,
        )
        for rule in catalog.operational_rules
    )


class PolicyCatalogRetriever(BaseRetriever):
    """Deterministic retrieval over owner-approved, versioned operational rules."""

    def __init__(self, catalog: PolicyCatalog | None = None) -> None:
        self.catalog = catalog or load_policy_catalog()
        self.documents = _documents(self.catalog)

    async def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        query_tokens = _meaningful_tokens(query)
        scored = [
            RetrievalResult(document=document, score=_score(query, query_tokens, document))
            for document in self.documents
        ]
        scored = [result for result in scored if result.score > 0]
        scored.sort(key=lambda result: (-result.score, result.document.document_id))
        return scored[:top_k]


# Compatibility name retained for integrations that imported the old class.
KeywordFaqRetriever = PolicyCatalogRetriever


class KnowledgeService:
    def __init__(self, retriever: BaseRetriever | None = None) -> None:
        self.retriever = retriever or PolicyCatalogRetriever()

    async def retrieve(self, query: str, *, top_k: int = 3) -> list[dict[str, object]]:
        results = await self.retriever.retrieve(query, top_k=top_k)
        return [
            {
                "content": result.document.content,
                "source": result.document.source,
                "score": result.score,
                "metadata": result.document.metadata,
                "citation_id": result.document.document_id,
                "version": result.document.version,
                "effective_at": result.document.effective_at,
                "expires_at": result.document.expires_at,
            }
            for result in results
        ]
