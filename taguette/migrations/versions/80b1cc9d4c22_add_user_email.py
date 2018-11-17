"""add User.email

Revision ID: 80b1cc9d4c22
Revises: 679f625e6e6a
Create Date: 2018-11-17 11:46:29.572383

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '80b1cc9d4c22'
down_revision = '679f625e6e6a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users',
                  sa.Column('email', sa.String(), nullable=True))
    op.add_column('users',
                  sa.Column('email_sent', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_column('email_sent')
        batch_op.drop_column('email')
