import hashlib

import pytest

from src.backend.services.knowledge_service import KnowledgeService
from src.backend.services.policy_service import PolicyService, load_policy_catalog


def test_policy_catalog_is_versioned_approved_and_source_is_immutable():
    service = PolicyService()
    catalog = service.catalog
    source = service.source_text()

    assert catalog.catalog_version == "2026-08-16"
    assert catalog.status == "APPROVED_PROJECT_POLICY"
    assert catalog.approved_by == "PROJECT_OWNER_SELF_REVIEW"
    assert catalog.source_identity_preserved is True
    assert catalog.identity_substitution_allowed is False
    assert hashlib.sha256(source.encode("utf-8")).hexdigest().upper() == catalog.source_sha256
    assert "Green SM" in source
    assert "không phải thông tin liên hệ AloSM" in catalog.legal_notice


def test_policy_loader_is_cached_and_has_unique_operational_rules():
    catalog = load_policy_catalog()
    assert catalog is load_policy_catalog()
    assert len(catalog.operational_rules) == len({rule.id for rule in catalog.operational_rules})
    assert {"privacy", "pricing", "safety", "support"}.issubset({rule.category for rule in catalog.operational_rules})


def test_registration_acceptance_must_match_current_version():
    service = PolicyService()
    service.assert_acceptance(terms_version="2026-08-16", privacy_version="2026-08-16")
    with pytest.raises(ValueError, match="POLICY_VERSION_MISMATCH"):
        service.assert_acceptance(terms_version="old", privacy_version="2026-08-16")


@pytest.mark.asyncio
async def test_policy_rag_returns_versioned_citation_for_refund():
    documents = await KnowledgeService().retrieve("Tôi muốn yêu cầu hoàn tiền", top_k=3)

    assert documents
    assert documents[0]["citation_id"] == "policy-refund"
    assert documents[0]["version"] == "2026-08-16"
    assert documents[0]["effective_at"] is not None
    assert "Agent chỉ tiếp nhận" in documents[0]["content"]
    assert documents[0]["metadata"]["source_sha256"] == PolicyService().catalog.source_sha256


@pytest.mark.asyncio
async def test_policy_rag_never_claims_green_sm_contact_is_alosm_contact():
    documents = await KnowledgeService().retrieve("hotline pháp nhân liên hệ AloSM", top_k=3)
    legal = next(item for item in documents if item["citation_id"] == "policy-legal-identity")
    assert "Không dùng hotline" in legal["content"]
    assert "Green SM/GSM" in legal["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "citation_id"),
    [
        ("Tôi muốn yêu cầu hoàn tiền, xử lý trong bao lâu?", "policy-refund"),
        ("Sau khi xác nhận giá, giá có được tự ý thay đổi không?", "policy-price-change"),
        ("Chính sách hủy chuyến và phí hủy là gì?", "policy-cancellation"),
    ],
)
async def test_policy_rag_understands_natural_faq_questions(question: str, citation_id: str):
    documents = await KnowledgeService().retrieve(question, top_k=1)

    assert documents[0]["citation_id"] == citation_id
