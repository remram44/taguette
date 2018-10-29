"""remove commands.document_id fk

Revision ID: e4e090a5b511
Revises:
Create Date: 2018-10-28 22:54:11.833009

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e4e090a5b511'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    naming_convention = {
        "fk":
            "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    }
    with op.batch_alter_table('commands',
                              naming_convention=naming_convention) as batch_op:
        batch_op.drop_constraint('fk_commands_document_id_documents',
                                 type_='foreignkey')


def downgrade():
    with op.batch_alter_table('commands') as batch_op:
        batch_op.create_foreign_key(None, 'documents', ['document_id'], ['id'])
