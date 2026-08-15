from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class RewriteReason(StrEnum):
    DEICTIC_REFERENCE = "DEICTIC_REFERENCE"
    ORDINAL_SELECTION = "ORDINAL_SELECTION"
    PREVIOUS_TURN_REFERENCE = "PREVIOUS_TURN_REFERENCE"
    AMBIGUOUS_CORRECTION = "AMBIGUOUS_CORRECTION"
    SHORT_CONTEXTUAL_REPLY = "SHORT_CONTEXTUAL_REPLY"


class ResolvedReference(BaseModel):
    original_phrase: str = Field(min_length=1)
    resolved_value: str = Field(min_length=1)
    source_turn_id: str = Field(min_length=1)

    @field_validator("original_phrase", "resolved_value", "source_turn_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resolved reference fields cannot be blank")
        return normalized


class RewriteResult(BaseModel):
    original_text: str = Field(min_length=1)
    rewritten_text: str = Field(min_length=1)
    changed: bool
    confidence: float = Field(ge=0, le=1)
    resolved_references: list[ResolvedReference] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)

    @field_validator("original_text", "rewritten_text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rewrite text cannot be blank")
        return value

    @field_validator("ambiguities")
    @classmethod
    def normalize_ambiguities(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("rewrite ambiguities cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("rewrite ambiguities must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_rewrite_semantics(self) -> "RewriteResult":
        if not self.changed and self.rewritten_text != self.original_text:
            raise ValueError("unchanged rewrite must preserve original text")
        if self.changed and self.rewritten_text == self.original_text:
            raise ValueError("changed rewrite must modify original text")

        reference_keys = [
            (
                reference.original_phrase.casefold(),
                reference.resolved_value.casefold(),
                reference.source_turn_id,
            )
            for reference in self.resolved_references
        ]
        if len(reference_keys) != len(set(reference_keys)):
            raise ValueError("resolved references must be unique")
        return self

    @classmethod
    def unchanged(
        cls,
        original_text: str,
        *,
        ambiguity: str | None = None,
    ) -> "RewriteResult":
        ambiguities = [ambiguity] if ambiguity else []
        return cls(
            original_text=original_text,
            rewritten_text=original_text,
            changed=False,
            confidence=1.0 if ambiguity is None else 0.0,
            ambiguities=ambiguities,
        )


class RewriteDecision(BaseModel):
    should_rewrite: bool
    reasons: list[RewriteReason] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision(self) -> "RewriteDecision":
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("rewrite reasons must be unique")
        if self.should_rewrite != bool(self.reasons):
            raise ValueError("rewrite decision and reasons must agree")
        return self
