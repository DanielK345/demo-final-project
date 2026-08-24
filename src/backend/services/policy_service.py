from __future__ import annotations

import hashlib
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"
POLICY_CATALOG_PATH = POLICY_DIR / "catalog.json"


class PolicyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_effective_date: str | None = None


class OperationalRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    citation: str = Field(min_length=1)


class PolicyCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    source_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    source_attribution: str
    source_identity_preserved: bool
    identity_substitution_allowed: bool
    legal_notice: str
    documents: list[PolicyDocument]
    operational_rules: list[OperationalRule]

    @model_validator(mode="after")
    def validate_policy_identity(self) -> PolicyCatalog:
        if not self.source_identity_preserved or self.identity_substitution_allowed:
            raise ValueError("third-party legal identity must be preserved and cannot be substituted")
        if len({rule.id for rule in self.operational_rules}) != len(self.operational_rules):
            raise ValueError("operational rule ids must be unique")
        return self


class PolicyService:
    def __init__(self, catalog: PolicyCatalog | None = None) -> None:
        self.catalog = catalog or load_policy_catalog()

    @property
    def source_path(self) -> Path:
        return POLICY_DIR / self.catalog.source_file

    def source_text(self) -> str:
        source = self.source_path
        if not source.is_file():
            raise RuntimeError(f"policy source not found: {source}")
        payload = source.read_bytes()
        digest = hashlib.sha256(payload).hexdigest().upper()
        if digest != self.catalog.source_sha256:
            raise RuntimeError("policy source checksum mismatch")
        return payload.decode("utf-8")

    def current(self, *, include_rules: bool = True) -> dict[str, object]:
        payload = self.catalog.model_dump(mode="json")
        if not include_rules:
            payload.pop("operational_rules", None)
        payload["source_endpoint"] = "/api/v1/policies/current/source"
        return payload

    def rule(self, rule_id: str) -> OperationalRule | None:
        return next((rule for rule in self.catalog.operational_rules if rule.id == rule_id), None)

    def assert_acceptance(self, *, terms_version: str, privacy_version: str) -> None:
        expected = self.catalog.catalog_version
        if terms_version != expected or privacy_version != expected:
            raise ValueError("POLICY_VERSION_MISMATCH")


@lru_cache(maxsize=1)
def load_policy_catalog(path: str | Path = POLICY_CATALOG_PATH) -> PolicyCatalog:
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise RuntimeError(f"policy catalog not found: {catalog_path}")
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog = PolicyCatalog.model_validate(raw)
        PolicyService(catalog).source_text()
        return catalog
    except Exception as exc:
        raise RuntimeError(f"invalid policy catalog {catalog_path}: {exc}") from exc
