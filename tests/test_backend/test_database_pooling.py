from sqlalchemy.pool import NullPool

from src.backend.config import get_settings
from src.backend.db.base import _connect_args, _engine_options, _is_transaction_pooler


def test_direct_supabase_endpoint_uses_bounded_async_pool(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_POOL_MODE", "auto")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "3")
    monkeypatch.setenv("DATABASE_POOL_MAX_OVERFLOW", "2")
    get_settings.cache_clear()
    url = "postgresql+asyncpg://user:secret@db.project.supabase.co:5432/postgres"

    options = _engine_options(url)

    assert options["pool_size"] == 3
    assert options["max_overflow"] == 2
    assert options["pool_pre_ping"] is True
    assert options["pool_use_lifo"] is True
    assert _connect_args(url) == {}
    get_settings.cache_clear()


def test_transaction_pooler_keeps_null_pool_and_disables_statement_cache(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_POOL_MODE", "auto")
    get_settings.cache_clear()
    url = "postgresql+asyncpg://user:secret@region.pooler.supabase.com:6543/postgres"

    assert _is_transaction_pooler(url) is True
    assert _engine_options(url) == {"poolclass": NullPool}
    assert _connect_args(url) == {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
    get_settings.cache_clear()


def test_sqlite_keeps_dialect_default_pool(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_POOL_MODE", "bounded")
    get_settings.cache_clear()

    assert _engine_options("sqlite+aiosqlite:///data/test.db") == {}
    get_settings.cache_clear()
