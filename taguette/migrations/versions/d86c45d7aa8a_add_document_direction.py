"""add document direction

Revision ID: d86c45d7aa8a
Revises: 43d6c240309d
Create Date: 2021-06-09 13:17:10.397016

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd86c45d7aa8a'
down_revision = '43d6c240309d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'documents',
        sa.Column(
            'text_direction',
            sa.Enum('LEFT_TO_RIGHT', 'RIGHT_TO_LEFT', name='textdirection'),
            nullable=True,
        ),
    )
    op.execute(
        '''\
        UPDATE documents SET text_direction = 'LEFT_TO_RIGHT';
        ''',
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.alter_column('text_direction', nullable=False)


def downgrade():
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_column('text_direction')
