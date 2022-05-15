"""add user disabled

Revision ID: 382db36f20f4
Revises: 09c662cd9483
Create Date: 2022-05-14 23:33:03.709256

"""
from alembic import op
from datetime import datetime
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '382db36f20f4'
down_revision = '6489b5f9cfb5'
branch_labels = None
depends_on = None


meta = sa.MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


def upgrade():
    # Add column as NULL
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disabled', sa.Boolean(), nullable=True))

    users = sa.Table(
        'users',
        meta,
        sa.Column('login', sa.String(30), primary_key=True),
        sa.Column('created', sa.DateTime, nullable=False,
                  default=lambda: datetime.utcnow()),
        sa.Column('hashed_password', sa.String(120), nullable=True),
        sa.Column('disabled', sa.Boolean, nullable=False, default=False),
        sa.Column('password_set_date', sa.DateTime, nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('email', sa.String(256), nullable=True,
                  index=True, unique=True),
        sa.Column('email_sent', sa.DateTime, nullable=True),
    )

    # Set all values to False
    connection = op.get_bind()
    assert connection is not None
    with connection.begin():
        connection.execute(users.update().values(disabled=False))

    # Set column to NOT NULL
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'disabled',
            existing_type=sa.BOOLEAN(),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('disabled')
