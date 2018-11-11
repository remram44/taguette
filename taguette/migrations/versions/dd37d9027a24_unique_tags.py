"""unique_tags

Revision ID: dd37d9027a24
Revises: e4e090a5b511
Create Date: 2018-11-10 21:45:13.844011

"""
from alembic import op
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision = 'dd37d9027a24'
down_revision = 'e4e090a5b511'
branch_labels = None
depends_on = None


def upgrade():
    # Change the paths of tags that collide, before adding the unique index
    bind = op.get_bind()
    session = Session(bind=bind)
    # https://stackoverflow.com/a/7416624
    session.execute('''\
        UPDATE tags
        SET path = path || ' ' || id
        WHERE
            id NOT IN (
                SELECT MIN(t3.id)
                FROM tags t3
                GROUP BY project_id, path
                HAVING count(t3.id) > 1
            ) AND id IN (
                SELECT t1.id
                FROM tags AS t1
                INNER JOIN tags AS t2
                ON t1.path = t2.path AND
                    t1.project_id = t2.project_id AND
                    t1.id <> t2.id
            );
        ''')
    session.commit()

    # Add the indexes
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
