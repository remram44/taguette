"""Don't use server_default=now(), timezone issues

Revision ID: ecb4065de575
Revises: 807c0cc0ecf6
Create Date: 2021-02-27 11:12:36.221364

"""
from alembic import op
from sqlalchemy.sql import functions

from taguette.database import no_sqlite_pragma_check


# revision identifiers, used by Alembic.
revision = 'ecb4065de575'
down_revision = '807c0cc0ecf6'
branch_labels = None
depends_on = None


def upgrade():
    with no_sqlite_pragma_check():
        with op.batch_alter_table('users') as batch_op:
            batch_op.alter_column('created', server_default=None)

        with op.batch_alter_table('projects') as batch_op:
            batch_op.alter_column('created', server_default=None)

        with op.batch_alter_table('documents') as batch_op:
            batch_op.alter_column('created', server_default=None)

        with op.batch_alter_table('commands') as batch_op:
            batch_op.alter_column('date', server_default=None)


def downgrade():
    with no_sqlite_pragma_check():
        with op.batch_alter_table('users') as batch_op:
            batch_op.alter_column('created', server_default=functions.now())

        with op.batch_alter_table('projects') as batch_op:
            batch_op.alter_column('created', server_default=functions.now())

        with op.batch_alter_table('documents') as batch_op:
            batch_op.alter_column('created', server_default=functions.now())

        with op.batch_alter_table('commands') as batch_op:
            batch_op.alter_column('date', server_default=functions.now())
