from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def test_sqlite_migration_chain_supports_foreign_keys_and_round_trip(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"

    _run_alembic(database_path, "upgrade", "head")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("select version_num from alembic_version").fetchone() == (
            "0005_livekit_voice_state",
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
            "0005_livekit_voice_state",
        )
        assert list(connection.execute("pragma foreign_key_check")) == []
