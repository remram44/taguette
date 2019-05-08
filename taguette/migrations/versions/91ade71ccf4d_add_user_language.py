"""add User.language

Revision ID: 91ade71ccf4d
Revises: bce44849c2f2
Create Date: 2019-05-09 14:02:38.185065

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91ade71ccf4d'
down_revision = 'bce44849c2f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users',
                  sa.Column('language', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('language')
