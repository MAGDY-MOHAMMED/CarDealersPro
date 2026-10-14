"""add ml feature columns to cars

Revision ID: a7f1c2d3e4b5
Revises: 2969f1906e98
Create Date: 2026-10-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f1c2d3e4b5'
down_revision: Union[str, Sequence[str], None] = '2969f1906e98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add the columns the ML feature pipeline needs."""
    op.add_column('cars', sa.Column('mileage', sa.Integer(), nullable=True))
    op.add_column('cars', sa.Column('fuel_type', sa.String(), nullable=True))
    op.add_column('cars', sa.Column('transmission', sa.String(), nullable=True))
    op.add_column('cars', sa.Column('body_type', sa.String(), nullable=True))
    op.add_column('cars', sa.Column('engine_capacity', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cars', 'engine_capacity')
    op.drop_column('cars', 'body_type')
    op.drop_column('cars', 'transmission')
    op.drop_column('cars', 'fuel_type')
    op.drop_column('cars', 'mileage')
