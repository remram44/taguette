"""lowercase logins

Revision ID: bce44849c2f2
Revises: 447d636f72c5
Create Date: 2019-04-04 21:50:36.046753

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'bce44849c2f2'
down_revision = '447d636f72c5'
branch_labels = None
depends_on = None


def upgrade():
    # Add ON UPDATE CASCADE to foreign keys
    with op.batch_alter_table('project_members') as batch_op:
        batch_op.drop_constraint(
            'fk_project_members_user_login_users',
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_project_members_user_login_users'),
            'users', ['user_login'], ['login'],
            onupdate='CASCADE', ondelete='CASCADE',
        )
    with op.batch_alter_table('commands') as batch_op:
        batch_op.drop_constraint(
            'fk_commands_user_login_users',
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_commands_user_login_users'),
            'users', ['user_login'], ['login'],
            onupdate='CASCADE',
        )

    # Update the login
    op.execute('UPDATE users SET login = lower(login);')
    # Should update via the cascade:
    # op.execute('UPDATE project_members SET user_login = lower(user_login);')
    # op.execute('UPDATE commands SET user_login = lower(user_login);')


def downgrade():
    with op.batch_alter_table('project_members') as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_project_members_user_login_users'),
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_project_members_user_login_users',
            'users', ['user_login'], ['login'],
            ondelete='CASCADE',
        )
    with op.batch_alter_table('commands') as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_commands_user_login_users'),
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_commands_user_login_users',
            'users', ['user_login'], ['login'],
        )
