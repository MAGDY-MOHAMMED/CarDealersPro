"""
add car_features and ai_confidence
"""


from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '2a63457a2d7f'
down_revision = '4f3a7d53aa6d'  # Previous migration hash
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('car_features',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('car_id', UUID(as_uuid=True), sa.ForeignKey('cars.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('feature_vector', sa.ARRAY(sa.Float()), nullable=True),  # تخزين الـ embeddings
        sa.Column('predicted_price', sa.Float(), nullable=True),
        sa.Column('damage_score', sa.Float(), nullable=True),  # نسبة الخبط من AI
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    op.create_index('idx_car_features_car_id', 'car_features', ['car_id'])

    op.add_column('car_ratings', sa.Column('ai_confidence', sa.Float(), nullable=True, server_default=None))

def downgrade() -> None:
    op.drop_index('idx_car_features_car_id')
    op.drop_table('car_features')
    op.drop_column('car_ratings', 'ai_confidence')