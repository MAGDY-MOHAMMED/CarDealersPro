"""add external_url to cars

Revision ID: 2969f1906e98
Revises: 858cd49fd906
Create Date: 2026-05-20 19:09:34.729110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2969f1906e98'
down_revision: Union[str, Sequence[str], None] = '858cd49fd906'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cars', sa.Column('external_url', sa.String(), nullable=True))
    op.create_unique_constraint('uq_cars_external_url', 'cars', ['external_url'])
    op.create_index('idx_cars_external_url', 'cars', ['external_url'])


def downgrade() -> None:
    op.drop_index('idx_cars_external_url')
    op.drop_constraint('uq_cars_external_url', 'cars')
    op.drop_column('cars', 'external_url')
