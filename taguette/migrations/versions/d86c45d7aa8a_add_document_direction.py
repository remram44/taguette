"""add document direction

Revision ID: d86c45d7aa8a
Revises: 43d6c240309d
Create Date: 2021-06-09 13:17:10.397016

"""
from alembic import op
import json
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'd86c45d7aa8a'
down_revision = '43d6c240309d'
branch_labels = None
depends_on = None


meta = sa.MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})

commands = sa.Table(
    'commands',
    meta,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('date', sa.DateTime, nullable=False),
    sa.Column('user_login', sa.String(30), nullable=False),
    sa.Column('project_id', sa.Integer, nullable=False),
    sa.Column('document_id', sa.Integer, nullable=True),
    sa.Column('payload', sa.Text, nullable=False),
)


def _do_map(map_func):
    """Map JSON payloads through the given function.
    """
    connection = op.get_bind()
    assert connection is not None

    payloads = connection.execute('''\
        SELECT id, payload FROM commands;
    ''')
    update = []
    for id, payload in payloads:
        payload = json.loads(payload)
        payload = map_func(payload)
        if payload is not None:
            payload = json.dumps(payload, sort_keys=True)
            update.append({'cmd_id': id, 'cmd_payload': payload})

    if update:
        with connection.begin():
            connection.execute(
                (
                    commands.update()
                    .where(commands.c.id == sa.bindparam('cmd_id'))
                    .values(payload=sa.bindparam('cmd_payload'))
                ),
                update,
            )


def upgrade():
    # Add textdirection enum type
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        direction_enum = postgresql.ENUM(
            'LEFT_TO_RIGHT', 'RIGHT_TO_LEFT',
            name='textdirection',
            create_type=False,
        )
        direction_enum.create(connection)
    else:
        direction_enum = sa.Enum(
            'LEFT_TO_RIGHT', 'RIGHT_TO_LEFT',
            name='textdirection',
        )

    # Add column to 'documents'
    op.add_column(
        'documents',
        sa.Column(
            'text_direction',
            direction_enum,
            nullable=True,
        ),
    )
    op.execute(
        '''\
        UPDATE documents SET text_direction = 'LEFT_TO_RIGHT';
        ''',
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.alter_column('text_direction', nullable=False)

    # Add field to commands
    def add_field(payload):
        if payload['type'] == 'document_add':
            payload['text_direction'] = 'LEFT_TO_RIGHT'
        return payload

    _do_map(add_field)


def downgrade():
    # Remove field from commands
    def remove_field(payload):
        payload.pop('text_direction', None)
        return payload

    _do_map(remove_field)

    # Remove column from 'documents'
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_column('text_direction')

    # Remove textdirection enum type
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        op.execute("DROP TYPE textdirection;")
