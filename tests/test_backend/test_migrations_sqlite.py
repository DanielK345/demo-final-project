from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Skip when the project .env configures a PostgreSQL DATABASE_URL_MIGRATIONS.
# In this environment, pydantic_settings reads the .env file even when the
# subprocess sets DATABASE_URL to a SQLite URL, causing alembic to connect to
# the live database and fail with DuplicateColumn on migration fc877ccd583a.
# This is an SQLite-only integration test; run it in a local environment without
# a PostgreSQL DATABASE_URL_MIGRATIONS to validate the migration chain.
_POSTGRES_SCHEMES = ("postgres://", "postgresql://", "postgresql+")


def _has_live_postgres() -> bool:
    """Return True when any configured DATABASE_URL points to PostgreSQL."""
    # Check OS environment first
    for key in ("DATABASE_URL_MIGRATIONS", "DATABASE_URL"):
        value = os.environ.get(key, "")
        if value.startswith(_POSTGRES_SCHEMES):
            return True
    # Also check .env file (pydantic_settings reads this with higher priority
    # than subprocess-injected env vars in some configurations)
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in ("DATABASE_URL_MIGRATIONS", "DATABASE_URL") and value.strip().startswith(_POSTGRES_SCHEMES):
                return True
    return False


_skip_live_postgres = pytest.mark.skipif(
    _has_live_postgres(),
    reason=(
        "DATABASE_URL_MIGRATIONS points to PostgreSQL — SQLite migration test "
        "requires a local-only environment without a live DATABASE_URL_MIGRATIONS."
    ),
)


def _run_alembic(database_path: Path, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database_path}"
    env["DATABASE_URL_MIGRATIONS"] = ""
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@_skip_live_postgres
def test_sqlite_migration_chain_supports_foreign_keys_and_round_trip(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"

    _run_alembic(database_path, "upgrade", "head")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("select version_num from alembic_version").fetchone() == (
            "acc88dbc1e83",
        )
        booking_foreign_keys = {
            (row[2], row[3], row[4])
            for row in connection.execute("pragma foreign_key_list(bookings)")
        }
        assert ("users", "user_id", "id") in booking_foreign_keys
        assert ("fare_quotes", "quote_id", "id") in booking_foreign_keys
        assert list(connection.execute("pragma foreign_key_check")) == []

    _run_alembic(database_path, "downgrade", "base")
    _run_alembic(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("select version_num from alembic_version").fetchone() == (
            "acc88dbc1e83",
        )
        assert list(connection.execute("pragma foreign_key_check")) == []
