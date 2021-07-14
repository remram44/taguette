"""remove document groups

Revision ID: 43d6c240309d
Revises: bc8e0e0677e9
Create Date: 2021-07-14 17:54:23.308674

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43d6c240309d'
down_revision = 'bc8e0e0677e9'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('document_groups')

    op.drop_index('ix_groups_path')
    op.drop_index('ix_groups_project_id')
    op.drop_table('groups')


def downgrade():
    op.create_table(
        'groups',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('project_id', sa.INTEGER(), nullable=False),
        sa.Column('path', sa.VARCHAR(length=200), nullable=False),
        sa.Column('description', sa.TEXT(), nullable=False),
        sa.ForeignKeyConstraint(
            ['project_id'],
            ['projects.id'],
            name='fk_groups_project_id_projects',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'project_id',
            'path',
            name='uq_groups_project_id',
        ),
    )
    op.create_index(
        'ix_groups_project_id',
        'groups',
        ['project_id'],
        unique=False,
    )
    op.create_index(
        'ix_groups_path',
        'groups',
        ['path'],
        unique=False,
    )

    op.create_table(
        'document_groups',
        sa.Column('document_id', sa.INTEGER(), nullable=False),
        sa.Column('group_id', sa.INTEGER(), nullable=False),
        sa.ForeignKeyConstraint(
            ['document_id'],
            ['documents.id'],
            name='fk_document_groups_document_id_documents',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['group_id'],
            ['groups.id'],
            name='fk_document_groups_group_id_groups',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint(
            'document_id',
            'group_id',
            name='pk_document_groups',
        ),
    )
