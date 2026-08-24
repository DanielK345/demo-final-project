"""Async SQLAlchemy engine/session setup for Supabase Postgres.

Thiết kế (xem `docs/database_supabase.md` để có bản đầy đủ + hướng dẫn tạo project
Supabase):

- Persistent app/LiveKit workers → use a direct or session endpoint (port 5432)
  and SQLAlchemy's bounded async pool so TLS connections survive between jobs.
- Temporary/serverless runtimes → use Supavisor transaction mode (port 6543).
  Transaction mode does not support prepared statements, so disable caches
  (`statement_cache_size=0`, `prepared_statement_cache_size=0`) — thiếu bước này sẽ
  gặp lỗi `prepared statement "..." already exists` ngẫu nhiên khi có nhiều request
  đồng thời (lỗi kinh điển asyncpg + PgBouncer/Supavisor transaction mode).
- Alembic migration (DDL, chạy không thường xuyên, cần connection ổn định) → nối qua
  **Direct Connection** (cổng 5432) bằng driver sync `psycopg2` — KHÔNG chạy DDL qua
  transaction pooler (dễ lỗi do pooler không đảm bảo cùng 1 session cho toàn bộ
  migration). Xem `migrations/env.py`.
- Local dev/test mặc định vẫn dùng SQLite (`sqlite+aiosqlite`/`sqlite`) — không cần
  Supabase để chạy `pytest`, giữ đúng tinh thần test-double đã dùng xuyên suốt project
  (không gọi network thật trong test, xem `tests/test_voice/fake_providers.py`).

Không đụng `src/backend/config.py` ngoài việc dùng field `database_url` đã có sẵn
(mặc định SQLite) — additive.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from src.backend.config import get_settings


class Base(DeclarativeBase):
    """Base class cho mọi ORM model — xem `src/backend/db/models.py`."""


def to_async_url(raw_url: str) -> str:
    """Chuẩn hoá connection string (Postgres của Supabase hoặc SQLite local) về dạng
    driver async mà SQLAlchemy hiểu. Supabase dashboard cho URL dạng `postgresql://`
    hoặc `postgres://` — cả 2 đều map về `postgresql+asyncpg://`."""
    if raw_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + raw_url[len("postgres://") :]
    if raw_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + raw_url[len("postgresql://") :]
    if raw_url.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + raw_url[len("sqlite:///") :]
    return raw_url


def to_sync_url(raw_url: str) -> str:
    """Bản sync (psycopg2) của connection string — dùng riêng cho Alembic
    (`migrations/env.py`), KHÔNG dùng cho app runtime."""
    if raw_url.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw_url[len("postgres://") :]
    if raw_url.startswith("postgresql://") and "+psycopg2" not in raw_url:
        return "postgresql+psycopg2://" + raw_url[len("postgresql://") :]
    return raw_url


def _is_transaction_pooler(async_url: str) -> bool:
    """Supabase reserves port 6543 for transaction pooling."""

    return async_url.startswith("postgresql+asyncpg://") and make_url(async_url).port == 6543


def _connect_args(async_url: str) -> dict[str, object]:
    if _is_transaction_pooler(async_url):
        # Transaction pooler (Supavisor) không hỗ trợ prepared statement — tắt hẳn
        # statement cache để asyncpg không tự tạo prepared statement ngầm.
        return {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
    return {}


def _engine_options(async_url: str) -> dict[str, object]:
    """Choose the documented pool type for the endpoint and runtime mode."""

    if async_url.startswith("sqlite+aiosqlite://"):
        return {}

    settings = get_settings()
    use_null_pool = settings.database_pool_mode == "null" or (
        settings.database_pool_mode == "auto" and _is_transaction_pooler(async_url)
    )
    if use_null_pool:
        return {"poolclass": NullPool}

    return {
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_pool_max_overflow,
        "pool_timeout": settings.database_pool_timeout_seconds,
        "pool_recycle": settings.database_pool_recycle_seconds,
        "pool_pre_ping": True,
        "pool_use_lifo": True,
    }


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        async_url = to_async_url(settings.database_url)
        _engine = create_async_engine(
            async_url,
            echo=False,
            connect_args=_connect_args(async_url),
            **_engine_options(async_url),
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: `db: AsyncSession = Depends(get_db)`."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def reset_engine_for_tests() -> None:
    """Đóng engine hiện tại và xoá cache — dùng trong test fixture khi cần đổi
    `DATABASE_URL` giữa các test (vd test với SQLite in-memory riêng biệt)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
