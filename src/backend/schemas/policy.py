from datetime import datetime

from pydantic import BaseModel


class PolicyDocumentDTO(BaseModel):
    slug: str
    title: str
    source_effective_date: str | None = None


class OperationalRuleDTO(BaseModel):
    id: str
    category: str
    title: str
    content: str
    citation: str


class PolicyCatalogDTO(BaseModel):
    schema_version: str
    catalog_version: str
    approved_at: datetime
    effective_from: datetime
    status: str
    approved_by: str
    target_product: str
    jurisdiction: str
    language: str
    source_file: str
    source_sha256: str
    source_attribution: str
    source_identity_preserved: bool
    identity_substitution_allowed: bool
    legal_notice: str
    documents: list[PolicyDocumentDTO]
    operational_rules: list[OperationalRuleDTO]
    source_endpoint: str


class PolicySourceDTO(BaseModel):
    catalog_version: str
    sha256: str
    attribution: str
    legal_notice: str
    content: str
