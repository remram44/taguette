"""add more indexes

Revision ID: 491de2dc7cd7
Revises: d86c45d7aa8a
Create Date: 2021-11-09 16:50:41.582391

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '491de2dc7cd7'
down_revision = 'd86c45d7aa8a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('commands', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_commands_document_id'),
            ['document_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_commands_user_login'),
            ['user_login'],
            unique=False,
        )

    with op.batch_alter_table('highlight_tags', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_highlight_tags_highlight_id'),
            ['highlight_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_highlight_tags_tag_id'),
            ['tag_id'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('highlight_tags', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_highlight_tags_tag_id'))
        batch_op.drop_index(batch_op.f('ix_highlight_tags_highlight_id'))

    with op.batch_alter_table('commands', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_commands_user_login'))
        batch_op.drop_index(batch_op.f('ix_commands_document_id'))
