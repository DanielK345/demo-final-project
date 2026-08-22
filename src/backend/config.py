from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
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
    openrouter_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Core Agent language understanding
    agent_llm_enabled: bool = True
    agent_llm_provider: Literal["openai"] = "openai"
    agent_llm_model: str = "openai/gpt-5.6-luna-pro"
    agent_llm_base_url: str | None = "https://openrouter.ai/api/v1"
    agent_llm_timeout_seconds: float = Field(default=5.0, gt=0)
    agent_llm_reasoning_effort: Literal["none", "low", "medium"] = "none"

    # Core Agent contextual user-message rewrite (từ feature/agentic-ai — rollout độc
    # lập với "understanding" ở trên: bật riêng để LLM viết lại câu người dùng cho rõ
    # nghĩa hơn theo ngữ cảnh hội thoại trước khi hiểu ý định, tắt mặc định).
    agent_rewrite_enabled: bool = False
    agent_rewrite_provider: Literal["openai"] = "openai"
    agent_rewrite_model: str = "openai/gpt-5.6-luna-pro"
    agent_rewrite_base_url: str | None = "https://openrouter.ai/api/v1"
    agent_rewrite_timeout_seconds: float = Field(default=5.0, gt=0)
    agent_rewrite_reasoning_effort: Literal["none", "low", "medium"] = "none"

    # Post-ASR Vietnamese correction. Only the current transcript is sent and
    # phone/email/ID/number values are replaced with immutable placeholders.
    voice_transcript_rewrite_enabled: bool = True
    voice_transcript_rewrite_model: str = "openai/gpt-5.6-luna-pro"
    voice_transcript_rewrite_base_url: str | None = "https://openrouter.ai/api/v1"
    voice_transcript_rewrite_timeout_seconds: float = Field(default=5.0, gt=0)
    voice_transcript_rewrite_reasoning_effort: Literal["none", "low", "medium"] = "none"
    voice_transcript_rewrite_minimum_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    # Bounded, privacy-redacted conversational memory for ASR normalization.
    # One turn is at most one user and one assistant message.
    voice_transcript_rewrite_context_window_turns: int = Field(default=3, ge=0, le=8)
    voice_transcript_rewrite_memory_max_corrections: int = Field(default=6, ge=0, le=20)

    def llm_api_key_for(self, base_url: str | None) -> str:
        """Select a gateway credential without reusing it for speech APIs."""
        if base_url and "openrouter.ai" in base_url.lower():
            return self.openrouter_api_key
        return self.openai_api_key

    # Database — persistent backends should use a Supabase direct/session endpoint
    # (port 5432) with the bounded application pool below. Transaction endpoints
    # (port 6543) are detected and kept on NullPool unless explicitly overridden.
    # DATABASE_URL_MIGRATIONS (optional) dùng riêng cho Alembic (Direct Connection,
    # cổng 5432, driver sync psycopg2) — để trống thì Alembic dùng lại DATABASE_URL.
    database_url: str = "sqlite:///./data/app.db"
    database_url_migrations: str = ""
    database_readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    database_pool_mode: Literal["auto", "bounded", "null"] = "auto"
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_pool_max_overflow: int = Field(default=5, ge=0, le=50)
    database_pool_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    database_pool_recycle_seconds: int = Field(default=300, ge=30, le=3600)
    quote_signing_key: str = ""
    field_encryption_key: str = ""

    # ---- Maps / Geocoding / Routing ----
    # Provider-neutral config. MAPS_PROVIDER selects the active stack.
    maps_provider: str = ""  # "osm" to enable Nominatim + OSRM
    maps_api_key: str = ""  # Not required for self-hosted Nominatim/OSRM
    maps_base_url: str = ""

    # Geocoding (Nominatim)
    geocoding_provider: str = "nominatim"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "AloSM/1.0 (ride-hailing; ops@alosm.vn)"
    nominatim_country_code: str = "vn"
    nominatim_timeout_seconds: float = Field(default=5.0, gt=0, le=30)

    # Routing (OSRM)
    routing_provider: str = "osrm"
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_profile: str = "driving"
    osrm_timeout_seconds: float = Field(default=10.0, gt=0, le=30)

    # Search / display / defaults
    map_default_country: str = "Vietnam"
    map_default_city: str = "Hà Nội"
    map_country_code: str = "vn"
    map_search_limit: int = Field(default=5, ge=1, le=20)
    map_request_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    map_candidate_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    map_route_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    map_cache_enabled: bool = True
    map_cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    maps_cache_backend: str = "memory"  # memory (dev/test) or redis (production)
    maps_cache_redis_url: str = ""

    # Service area — optional polygon boundary check
    maps_service_area_id: str = ""
    maps_service_area_path: str = ""  # path to GeoJSON Polygon/MultiPolygon

    # OSM data version metadata (informational)
    osm_data_version: str = ""

    # Tile provider — for frontend basemap rendering (separate from geocoding/routing)
    map_tile_url: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    map_tile_attribution: str = "© OpenStreetMap contributors"

    def production_readiness_errors(self) -> list[str]:
        """Return safe configuration error codes; never include secret values."""
        if self.app_env != "production":
            return []
        # Durable repositories are implemented. Keep production fail-closed until the live
        # migration, PostgreSQL acceptance, least-privilege role and multi-instance gate
        # are completed; no environment flag may bypass this code gate.
        errors: list[str] = ["DURABLE_SERVICE_PERSISTENCE_REQUIRED"]
        if not self.database_url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
            errors.append("DATABASE_URL_MUST_BE_POSTGRES")
        if not self.database_url_migrations.startswith(("postgres://", "postgresql://", "postgresql+psycopg2://")):
            errors.append("DATABASE_URL_MIGRATIONS_REQUIRED")
        if len(self.quote_signing_key) < 32:
            errors.append("QUOTE_SIGNING_KEY_REQUIRED")
        if len(self.field_encryption_key) < 32:
            errors.append("FIELD_ENCRYPTION_KEY_REQUIRED")
        if self.maps_provider and self.maps_cache_backend != "redis":
            errors.append("MAPS_DISTRIBUTED_CACHE_REQUIRED")
        if self.maps_provider and not self.maps_cache_redis_url:
            errors.append("MAPS_CACHE_REDIS_URL_REQUIRED")
        if self.maps_provider and not self.maps_service_area_path:
            errors.append("MAPS_SERVICE_AREA_REQUIRED")
        if self.maps_provider and not self.osm_data_version:
            errors.append("OSM_DATA_VERSION_REQUIRED")
        origins = {origin.strip() for origin in self.cors_origins.split(",") if origin.strip()}
        if not origins or "*" in origins:
            errors.append("CORS_ORIGINS_MUST_BE_EXPLICIT")
        return errors

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
