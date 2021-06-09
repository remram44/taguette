"""add password change date

Revision ID: b23f3b7a638e
Revises: 91ade71ccf4d
Create Date: 2020-04-03 15:54:14.870029

"""
from alembic import op
import sqlalchemy as sa

from taguette.database import no_sqlite_pragma_check


# revision identifiers, used by Alembic.
revision = 'b23f3b7a638e'
down_revision = '91ade71ccf4d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('password_set_date', sa.DateTime(), nullable=True),
    )

    # Set the password set time to now if a password is set
    op.execute(
        '''\
        UPDATE users SET password_set_date=DATETIME()
        WHERE hashed_password IS NOT NULL;
        ''',
    )


def downgrade():
    with no_sqlite_pragma_check():
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('password_set_date')
