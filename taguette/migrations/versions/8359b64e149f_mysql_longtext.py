"""mysql longtext

Revision ID: 8359b64e149f
Revises: db5e31a0233d
Create Date: 2024-10-08 16:16:40.763362

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8359b64e149f'
down_revision = 'db5e31a0233d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('documents') as batch_op:
        batch_op.alter_column(
            'contents',
            existing_type=sa.TEXT(),
            existing_nullable=False,
        )


def downgrade():
    pass
