from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99h7fd717f73'
down_revision = '2a63457a2d7f'  # Previous migration hash
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('cars', sa.Column('external_url', sa.String(), nullable=True, unique=True))
    op.create_index('idx_cars_external_url', 'cars', ['external_url'])

def downgrade():
    op.drop_index('idx_cars_external_url')
    op.drop_column('cars', 'external_url')