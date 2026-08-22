"""merge_livekit_voice_state_and_route_snapshots

Revision ID: acc88dbc1e83
Revises: 0005_livekit_voice_state, fc877ccd583a
Create Date: 2026-08-20 15:30:16.242678
"""

from collections.abc import Sequence

revision: str = "acc88dbc1e83"
down_revision: str | tuple[str, str] | None = ("0005_livekit_voice_state", "fc877ccd583a")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
