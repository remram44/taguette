"""rename fields in Command JSON payload

Revision ID: bc8e0e0677e9
Revises: ecb4065de575
Create Date: 2021-06-05 18:24:28.756510

"""
from alembic import op
import json


# revision identifiers, used by Alembic.
revision = 'bc8e0e0677e9'
down_revision = 'ecb4065de575'
branch_labels = None
depends_on = None


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
            update.append({'id': id, 'payload': payload})

    if update:
        with connection.begin():
            connection.execute(
                '''\
                    UPDATE commands SET payload=:payload WHERE id=:id;
                ''',
                update,
            )


def upgrade():
    def _map_forward(payload):
        if payload['type'] == 'project_meta':
            payload['project_name'] = payload.pop('name')
        elif payload['type'] == 'document_add':
            payload['document_name'] = payload.pop('name')
        elif payload['type'] in ('highlight_add', 'highlight_delete'):
            payload['highlight_id'] = payload.pop('id')
        elif payload['type'] in ('tag_add', 'tag_delete'):
            if payload['type'] == 'tag_add':
                payload['tag_path'] = payload.pop('path')
            payload['tag_id'] = payload.pop('id')
        elif payload['type'] == 'tag_merge':
            payload['src_tag_id'] = payload.pop('src')
            payload['dest_tag_id'] = payload.pop('dest')
        elif 'id' in payload:
            raise ValueError(
                "Unknown command type with 'id' field: %r" % payload['type']
            )
        elif 'name' in payload:
            raise ValueError(
                "Unknown command type with 'name' field: %r" % payload['type']
            )
        else:
            return None
        return payload

    _do_map(_map_forward)


def downgrade():
    def _map_back(payload):
        if 'id' in payload:
            raise ValueError(
                "Command type with 'id' field: %r" % payload['type']
            )
        elif 'name' in payload:
            raise ValueError(
                "Command type with 'name' field: %r" % payload['type']
            )
        elif payload['type'] == 'project_meta':
            payload['name'] = payload.pop('project_name')
        elif payload['type'] == 'document_add':
            payload['name'] = payload.pop('document_name')
        elif payload['type'] in ('highlight_add', 'highlight_delete'):
            payload['id'] = payload.pop('highlight_id')
        elif payload['type'] in ('tag_add', 'tag_delete'):
            if payload['type'] == 'tag_add':
                payload['path'] = payload.pop('tag_path')
            payload['id'] = payload.pop('tag_id')
        elif payload['type'] == 'tag_merge':
            payload['src'] = payload.pop('src_tag_id')
            payload['dest'] = payload.pop('dest_tag_id')
        else:
            return None
        return payload

    _do_map(_map_back)
