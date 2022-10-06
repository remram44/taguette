"""increase password hash size

Revision ID: 6489b5f9cfb5
Revises: 09c662cd9483
Create Date: 2022-10-06 17:17:36.212586

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6489b5f9cfb5'
down_revision = '09c662cd9483'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'hashed_password',
            existing_type=sa.String(120),
            type_=sa.String(192),
        )


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'hashed_password',
            existing_type=sa.String(192),
            type_=sa.String(120),
        )
