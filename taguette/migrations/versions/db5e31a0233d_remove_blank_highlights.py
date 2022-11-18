"""remove blank highlights

Revision ID: db5e31a0233d
Revises: 382db36f20f4
Create Date: 2022-11-18 15:03:03.154401

"""
from alembic import op
import sqlalchemy as sa
import sys


# revision identifiers, used by Alembic.
revision = 'db5e31a0233d'
down_revision = '382db36f20f4'
branch_labels = None
depends_on = None


meta = sa.MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})

highlights = sa.Table(
    'highlights',
    meta,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('document_id', sa.Integer, nullable=False),
    sa.Column('start_offset', sa.Integer, nullable=False),
    sa.Column('end_offset', sa.Integer, nullable=False),
    sa.Column(
        'snippet', sa.Text,
        sa.ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
    ),
)

highlight_tags = sa.Table(
    'highlight_tags',
    meta,
    sa.Column(
        'highlight_id', sa.Integer,
        sa.ForeignKey('highlights.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    sa.Column(
        'tag_id', sa.Integer,
        sa.ForeignKey('tags.id', ondelete='CASCADE'),
        primary_key=True,
    ),
)


def upgrade():
    bind = op.get_bind()

    # Find blank highlights
    rows = bind.execute(
        sa.select([highlights.c.id, highlights.c.snippet])
        .select_from(highlights)
    )
    to_delete = []
    for id, snippet in rows:
        if all(c in '\r\n\t' for c in snippet):
            to_delete.append(id)

    # Delete them
    if to_delete:
        print(
            "%d blank highlights to delete" % len(to_delete),
            file=sys.stderr,
        )
        bind.execute(
            highlight_tags.delete()
            .where(highlight_tags.c.highlight_id.in_(to_delete))
        )
        bind.execute(
            highlights.delete()
            .where(highlights.c.id.in_(to_delete))
        )


def downgrade():
    pass
