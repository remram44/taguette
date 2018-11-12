"""fix_unique_tags

Revision ID: 679f625e6e6a
Revises: dd37d9027a24
Create Date: 2018-11-12 17:20:50.420807

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '679f625e6e6a'
down_revision = 'dd37d9027a24'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tags') as batch_op:
        batch_op.create_unique_constraint(batch_op.f('uq_groups_project_id'),
                                          ['project_id', 'path'])
        batch_op.drop_index('ix_tags_path')
        batch_op.create_index(batch_op.f('ix_tags_path'), ['path'],
                              unique=False)

    with op.batch_alter_table('groups') as batch_op:
        batch_op.create_unique_constraint(batch_op.f('uq_groups_project_id'),
                                          ['project_id', 'path'])
        batch_op.drop_index('ix_groups_path')
        batch_op.create_index(batch_op.f('ix_groups_path'), ['path'],
                              unique=False)


def downgrade():
    with op.batch_alter_table('groups') as batch_op:
        batch_op.drop_index(batch_op.f('ix_groups_path'))
        batch_op.create_index('ix_groups_path', ['path'], unique=True)
        batch_op.drop_constraint(batch_op.f('uq_groups_project_id'),
                                 type_='unique')

    with op.batch_alter_table('tags') as batch_op:
        batch_op.drop_index(batch_op.f('ix_tags_path'))
        batch_op.create_index('ix_tags_path', ['path'], unique=True)
        batch_op.drop_constraint(batch_op.f('uq_groups_project_id'),
                                 type_='unique')
