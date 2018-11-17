"""cascades

Revision ID: 447d636f72c5
Revises: 80b1cc9d4c22
Create Date: 2018-11-17 13:50:51.570871

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '447d636f72c5'
down_revision = '80b1cc9d4c22'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('commands') as batch_op:
        batch_op.drop_constraint('fk_commands_project_id_projects',
                                 type_='foreignkey')
        batch_op.create_foreign_key(
            batch_op.f('fk_commands_project_id_projects'),
            'projects', ['project_id'], ['id'],
            ondelete='CASCADE')


def downgrade():
    with op.batch_alter_table('commands') as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_commands_project_id_projects'), type_='foreignkey')
        batch_op.create_foreign_key('fk_commands_project_id_projects',
                                    'projects', ['project_id'], ['id'])
