from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Core Agent language understanding
    agent_llm_enabled: bool = True
    agent_llm_provider: Literal["openai"] = "openai"
    agent_llm_model: str = "gpt-5.6-luna"
    agent_llm_base_url: str | None = None
    agent_llm_timeout_seconds: float = Field(default=5.0, gt=0)
    agent_llm_reasoning_effort: Literal["none", "low", "medium"] = "none"

    # Core Agent contextual user-message rewrite (từ feature/agentic-ai — rollout độc
    # lập với "understanding" ở trên: bật riêng để LLM viết lại câu người dùng cho rõ
    # nghĩa hơn theo ngữ cảnh hội thoại trước khi hiểu ý định, tắt mặc định).
    agent_rewrite_enabled: bool = False
    agent_rewrite_provider: Literal["openai"] = "openai"
    agent_rewrite_model: str = "gpt-5.6-luna"
    agent_rewrite_base_url: str | None = None
    agent_rewrite_timeout_seconds: float = Field(default=5.0, gt=0)
    agent_rewrite_reasoning_effort: Literal["none", "low", "medium"] = "none"

    # Voice prototype (STT/TTS)
    google_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    )
    voice_provider: Literal["auto", "openai", "gemini"] = "auto"
    voice_stt_model: str = "gpt-4o-transcribe"
    voice_tts_model: str = "tts-1"
    voice_tts_voice: str = "nova"
    voice_gemini_model: str = "gemini-2.0-flash"
    voice_timeout_seconds: float = Field(default=30.0, gt=0)

    # Post-ASR Vietnamese correction. Only the current transcript is sent and
    # phone/email/ID/number values are replaced with immutable placeholders.
    voice_transcript_rewrite_enabled: bool = True
    voice_transcript_rewrite_model: str = "gpt-5.6-luna"
    voice_transcript_rewrite_base_url: str | None = None
    voice_transcript_rewrite_timeout_seconds: float = Field(default=5.0, gt=0)
    voice_transcript_rewrite_reasoning_effort: Literal["none", "low", "medium"] = "none"
    voice_transcript_rewrite_minimum_confidence: float = Field(default=0.85, ge=0.0, le=1.0)

    # Database — DATABASE_URL dùng cho app runtime (Supabase Transaction Pooler,
    # cổng 6543, driver async asyncpg khi deploy thật — xem docs/database_supabase.md).
    # DATABASE_URL_MIGRATIONS (optional) dùng riêng cho Alembic (Direct Connection,
    # cổng 5432, driver sync psycopg2) — để trống thì Alembic dùng lại DATABASE_URL.
    database_url: str = "sqlite:///./data/app.db"
    database_url_migrations: str = ""

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
