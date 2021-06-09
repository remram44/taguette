"""remove invalid hltags

Revision ID: 807c0cc0ecf6
Revises: b23f3b7a638e
Create Date: 2021-02-17 13:04:13.809606

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '807c0cc0ecf6'
down_revision = 'b23f3b7a638e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        '''\
        DELETE FROM highlight_tags
        WHERE
            -- Project of the highlight
            (
                SELECT documents.project_id
                FROM highlights
                    INNER JOIN documents
                        ON highlights.document_id = documents.id
                WHERE highlights.id = highlight_tags.highlight_id
            )
            NOT IN
            -- Project of the tag
            (
                SELECT tags.project_id
                FROM tags
                WHERE tags.id = highlight_tags.tag_id
            );
        ''',
    )


def downgrade():
    pass
