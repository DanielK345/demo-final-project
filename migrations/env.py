"""Alembic env — chạy migration bằng driver SYNC (psycopg2 cho Postgres/Supabase,
sqlite3 cho local dev) dù app runtime dùng async engine (`src/backend/db/base.py`).
Đây là pattern chuẩn — Alembic tự nó chạy sync, và migration/DDL không nên chạy qua
Supabase Transaction Pooler (xem docs/database_supabase.md), nên tách hẳn khỏi engine
async của app.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.config import get_settings  # noqa: E402
from src.backend.db.base import to_sync_url  # noqa: E402
from src.backend.db.models import Base  # noqa: E402  (import để đăng ký hết model vào Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    settings = get_settings()
    raw = settings.database_url_migrations or settings.database_url
    return to_sync_url(raw)


def run_migrations_offline() -> None:
    url = _sync_database_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
