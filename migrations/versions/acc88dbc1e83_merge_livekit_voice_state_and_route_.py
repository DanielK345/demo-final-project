"""merge_livekit_voice_state_and_route_snapshots

Revision ID: acc88dbc1e83
Revises: 0005_livekit_voice_state, fc877ccd583a
Create Date: 2026-08-20 15:30:16.242678

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acc88dbc1e83'
down_revision: Union[str, None] = ('0005_livekit_voice_state', 'fc877ccd583a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
