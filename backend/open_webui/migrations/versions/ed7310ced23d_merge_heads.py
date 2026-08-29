"""merge subscription tables and user variables branches

Revision ID: ed7310ced23d
Revises: a7b8c9d0e1f2, f0bd01a18a3d
Create Date: 2026-08-14 04:53:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'ed7310ced23d'
down_revision: Union[str, Sequence[str], None] = ['a7b8c9d0e1f2', 'f0bd01a18a3d']
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
