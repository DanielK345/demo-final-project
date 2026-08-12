from pydantic import BaseModel, Field


class AgentPolicy(BaseModel):
    low_confidence_threshold: float = Field(default=0.5, ge=0, le=1)
    max_retry_count: int = Field(default=3, ge=1)
    max_spoken_message_characters: int = Field(default=600, ge=1)
