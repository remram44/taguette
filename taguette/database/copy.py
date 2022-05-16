import logging
import opentelemetry.trace

from .models import Project, Privileges, ProjectMember, TextDirection, \
    Document, Command, Highlight, Tag, HighlightTag
from .. import convert
from ..utils import DefaultMap
from .. import validate


logger = logging.getLogger(__name__)
tracer = opentelemetry.trace.get_tracer(__name__)


@tracer.start_as_current_span('taguette/copy_project')
def copy_project(
    src_db, dest_db,
    project_id, user_login,
):
    def copy(
        model, pkey, fkeys, size,
        *, condition=None, transform=None, validators=None
    ):
        return copy_table(
            src_db, dest_db,
            model.__table__, pkey, fkeys,
            batch_size=size,
            condition=condition, transform=transform, validators=validators,
        )

    def insert(model, values):
        ins = dest_db.execute(
            model.__table__.insert(),
            values,
        )
        return ins

    # Copy project
    project = src_db.execute(
        Project.__table__.select().where(Project.id == project_id)
    ).fetchone()
    if project is None:
        raise KeyError("project ID not found")
    validate.project_name(project['name'])
    validate.description(project['description'])
    project = dict(project)
    project.pop('id')
    new_project_id, = insert(Project, project).inserted_primary_key
    mapping_project = {project_id: new_project_id}

    # Add member
    insert(
        ProjectMember,
        dict(
            project_id=new_project_id,
            user_login=user_login,
            privileges=Privileges.ADMIN,
        ),
    )

    # Copy documents
    mapping_document = copy(
        Document, 'id',
        dict(project_id=mapping_project),
        2,
        condition=Document.project_id == project_id,
        validators=dict(
            name=validate.document_name,
            description=validate.description,
            filename=validate.filename,
            contents=convert.is_html_safe,
        ),
    )

    # Copy tags
    mapping_tags = copy(
        Tag, 'id',
        dict(project_id=mapping_project),
        50,
        condition=Tag.project_id == project_id,
        validators=dict(
            path=validate.tag_path,
            description=validate.description,
        ),
    )

    # Copy highlights
    mapping_highlights = copy(
        Highlight, 'id',
        dict(document_id=mapping_document),
        50,
        condition=Highlight.document_id.in_(mapping_document.keys()),
        validators=dict(
            start_offset=lambda v: isinstance(v, int) and v >= 0,
            end_offset=lambda v: isinstance(v, int) and v > 0,
            snippet=convert.is_html_safe,
        ),
    )

    # Copy highlight tags
    copy(
        HighlightTag, None,
        dict(highlight_id=mapping_highlights, tag_id=mapping_tags),
        200,
        condition=HighlightTag.tag_id.in_(mapping_tags.keys()),
    )

    def validate_text_direction(direction):
        try:
            TextDirection[direction]
        except KeyError:
            raise ValueError("Invalid text direction")
        return True

    # Copy commands
    def transform_command(cmd):
        payload = cmd['payload']

        if payload['type'] not in Command.TYPES:
            raise ValueError("Unknown command %r" % payload['type'])

        method = getattr(Command, payload['type'])
        expected_columns = (
            set(method.columns)
            | {'date', 'user_login', 'payload'}
        )
        expected_payload_fields = set(method.payload_fields) | {'type'}

        # Check that the right columns are set
        if {k for k, v in cmd.items() if v is not None} != expected_columns:
            raise ValueError("Command doesn't have expected columns")

        # Check that the right JSON fields are set
        if payload.keys() != expected_payload_fields:
            raise ValueError("Command doesn't have expected fields")

        # Map an ID, using negative ID if it's unknown
        def mv(mapping, value):
            return mapping.get(value, -abs(value))

        field_validators = dict(
            type=lambda v: True,  # Already checked above
            description=validate.description,
            project_name=validate.project_name,
            document_name=validate.document_name,
            text_direction=validate_text_direction,
            highlight_id=lambda v: isinstance(v, int),
            start_offset=lambda v: isinstance(v, int) and v >= 0,
            end_offset=lambda v: isinstance(v, int) and v > 0,
            tags=lambda v: (
                isinstance(v, list)
                and all(isinstance(e, int) for e in v)
            ),
            tag_id=lambda v: isinstance(v, int),
            tag_path=validate.tag_path,
            src_tag_id=lambda v: isinstance(v, int),
            dest_tag_id=lambda v: isinstance(v, int),
            member=validate.user_login,
            privileges=lambda v: v in Privileges.__members__,
        )

        field_transformers = dict(
            highlight_id=lambda v: mv(mapping_highlights, v),
            tag_id=lambda v: mv(mapping_tags, v),
            src_tag_id=lambda v: mv(mapping_tags, v),
            tags=lambda tags: [mv(mapping_tags, t) for t in tags],
        )

        # Map JSON fields
        for field, value in list(payload.items()):
            try:
                if not field_validators[field](value):
                    raise ValueError("Invalid field %r in command" % field)
            except validate.InvalidFormat:
                raise ValueError("Invalid field %r in command" % field)
            if field in field_transformers:
                payload[field] = field_transformers[field](value)

        return dict(cmd.items(), payload=payload)

    copy(
        Command, 'id',
        dict(
            # Map all users to the importing user
            user_login=DefaultMap(lambda key: user_login, {}),
            project_id=mapping_project,
            # Map None to None and unknown keys (deleted documents) to negative
            document_id=DefaultMap(
                lambda key: None if key is None else -abs(key),
                mapping_document,
            ),
        ),
        100,
        condition=Command.project_id == project_id,
        transform=transform_command,
    )

    dest_db.commit()

    return new_project_id


def copy_table(
    src_db, dest_db, table,
    pkey, fkeys,
    *, batch_size=50, condition=None, transform=None, validators=None
):
    """Copy all data in a table across database connections.

    :param src_db: The SQLAlchemy ``Connection`` or ``Session`` to copy from.
    :param dest_db: The SQLAlchemy ``Connection`` or ``Session`` to copy into.
    :param table: The SQLAlchemy ``Table`` we are copying. It should exist on
        both the source and destination databases.
    :param pkey: The field in the table that is the primary key and should be
        reset during the copy (so new values get generated when inserting in
        the destination and no conflict occurs).
    :param fkeys: A dictionary associating the name of the fields that are
        foreign keys to a dictionary mapping the keys.
    :param transform: Function to apply on each row.
    """
    query = table.select()
    if pkey is not None:
        query = query.order_by(pkey)
    if condition is not None:
        query = query.where(condition)
    query = src_db.execute(query)
    assert pkey is None or pkey in query.keys()
    assert all(field in query.keys() for field in fkeys)
    mapping = {}
    batch = query.fetchmany(batch_size)
    orig_pkey = None  # Avoids warning
    while batch:
        for row in batch:
            row = dict(row)
            # Get primary key, remove it
            if pkey is not None:
                orig_pkey = row[pkey]
                row = dict(row)
                row.pop(pkey)
            # Map foreign keys
            for field, fkey_map in fkeys.items():
                row[field] = fkey_map[row[field]]
            # Generic transform
            if transform is not None:
                row = transform(row)
            # Validate
            if validators:
                for key, value in row.items():
                    if key in validators:
                        try:
                            if not validators[key](value):
                                raise ValueError(
                                    "Data failed validation (column %r)" % key,
                                )
                        except validate.InvalidFormat:
                            raise ValueError(
                                "Data failed validation (column %r)" % key,
                            )

            # Have to insert one-by-one for inserted_primary_key
            ins = dest_db.execute(
                table.insert(),
                row,
            )
            # Store new primary key
            if pkey is not None:
                mapping[orig_pkey], = ins.inserted_primary_key
        batch = query.fetchmany(batch_size)
    return mapping
