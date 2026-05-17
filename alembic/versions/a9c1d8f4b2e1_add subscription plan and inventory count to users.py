"""add subscription plan and inventory count to users

Revision ID: a9c1d8f4b2e1
Revises: f73ee17257c0
Create Date: 2026-05-15 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9c1d8f4b2e1"
down_revision: Union[str, Sequence[str], None] = "f73ee17257c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("subscription_plan", sa.String(), nullable=False, server_default="FREE"),
    )
    op.add_column(
        "users",
        sa.Column("inventory_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        """
        UPDATE users
        SET inventory_count = sub.car_count
        FROM (
            SELECT owner_id, COUNT(*) AS car_count
            FROM cars
            WHERE is_deleted = FALSE AND owner_id IS NOT NULL
            GROUP BY owner_id
        ) AS sub
        WHERE users.id = sub.owner_id
        """
    )


def downgrade() -> None:
    op.drop_column("users", "inventory_count")
    op.drop_column("users", "subscription_plan")