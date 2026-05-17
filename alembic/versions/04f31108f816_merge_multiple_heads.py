"""merge multiple heads

Revision ID: 04f31108f816
Revises: 0e8dcb7a8e94, 99h7fd717f73
Create Date: 2026-05-17 08:05:32.956597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04f31108f816'
down_revision: Union[str, Sequence[str], None] = ('0e8dcb7a8e94', '99h7fd717f73')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
