"""add index

Revision ID: e4cf92942271
Revises: 491de2dc7cd7
Create Date: 2021-11-18 10:38:47.124630

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e4cf92942271'
down_revision = '491de2dc7cd7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('commands', schema=None) as batch_op:
        batch_op.create_index(
            'idx_project_id',
            ['project_id', 'id'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('commands', schema=None) as batch_op:
        batch_op.drop_index('idx_project_id')
