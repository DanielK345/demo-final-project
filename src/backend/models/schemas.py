from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    # turn_id: bắt buộc theo contract mới của Core Agent (feature/agentic-ai) — xem
    # src/agents/schemas.py::AgentInput. Route /chat này là legacy, giữ lại chỉ để
    # tương thích test suite cũ (xem routes/__init__.py).
    turn_id: str = Field(..., min_length=1, description="ID ổn định cho 1 lượt xử lý")
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhắn từ user")

    @field_validator("turn_id")
    @classmethod
    def normalize_turn_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("turn_id cannot be blank")
        return normalized


class ChatResponse(BaseModel):
    response: str = Field(..., description="Phản hồi từ agent")
    analysis: str = Field(default="", description="Phân tích nội bộ")
