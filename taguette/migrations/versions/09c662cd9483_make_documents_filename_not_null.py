"""make documents.filename NOT NULL

Revision ID: 09c662cd9483
Revises: e4cf92942271
Create Date: 2022-01-21 17:42:53.265226

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09c662cd9483'
down_revision = 'e4cf92942271'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        '''\
        UPDATE documents SET filename = 'unknown' WHERE filename IS NULL;
        ''',
    )
    with op.batch_alter_table('documents') as batch_op:
        batch_op.alter_column(
            'filename',
            existing_type=sa.VARCHAR(length=200),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table('documents') as batch_op:
        batch_op.alter_column(
            'filename',
            existing_type=sa.VARCHAR(length=200),
            nullable=True,
        )
