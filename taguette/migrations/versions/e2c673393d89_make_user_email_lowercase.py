"""lowercase emails

Revision ID: e2c673393d89
Revises: db5e31a0233d
Create Date: 2024-07-01 19:19:08.447896

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e2c673393d89'
down_revision = 'db5e31a0233d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('UPDATE users SET email = lower(email);')


def downgrade():
    pass
