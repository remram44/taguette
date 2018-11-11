"""unique_tags

Revision ID: dd37d9027a24
Revises: e4e090a5b511
Create Date: 2018-11-10 21:45:13.844011

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'dd37d9027a24'
down_revision = 'e4e090a5b511'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tags') as batch_op:
        batch_op.create_index(batch_op.f('ix_tags_path'), ['path'],
                              unique=True)

    # We assume no one created those, table is unused so far
    with op.batch_alter_table('groups') as batch_op:
        batch_op.create_index(batch_op.f('ix_groups_path'), ['path'],
                              unique=True)


def downgrade():
    with op.batch_alter_table('groups') as batch_op:
        batch_op.drop_index(batch_op.f('ix_groups_path'))

    with op.batch_alter_table('tags') as batch_op:
        batch_op.drop_index(batch_op.f('ix_tags_path'))
