import binascii
from datetime import datetime
import enum
import hashlib
import hmac
import json
import logging
import opentelemetry.trace
import os
from sqlalchemy import Column, ForeignKey, Index, TypeDecorator, MetaData, \
    UniqueConstraint, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import column_property, deferred, relationship
from sqlalchemy.sql import functions
from sqlalchemy.types import DateTime, Enum, Integer, String, Text

from .base import PROM_COMMAND


logger = logging.getLogger(__name__)
tracer = opentelemetry.trace.get_tracer(__name__)


meta = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})
Base = declarative_base(metadata=meta)


class JSON(TypeDecorator):
    """Platform-independent JSON type.
    """
    impl = Text

    def process_bind_param(self, value, dialect):
        return json.dumps(value, sort_keys=True)

    def process_result_value(self, value, dialect):
        return json.loads(value)


class User(Base):
    __tablename__ = 'users'

    login = Column(String(30), primary_key=True)
    created = Column(DateTime, nullable=False,
                     default=lambda: datetime.utcnow())
    hashed_password = Column(String(120), nullable=True)
    password_set_date = Column(DateTime, nullable=True)
    language = Column(String(10), nullable=True)
    email = Column(String(256), nullable=True, index=True, unique=True)
    email_sent = Column(DateTime, nullable=True)
    projects = relationship('Project', secondary='project_members')

    def set_password(self, password, method='pbkdf2'):
        if method == 'bcrypt':
            import bcrypt
            with tracer.start_as_current_span(
                'taguette/set_password',
                attributes={'method': method},
            ):
                h = bcrypt.hashpw(password.encode('utf-8'),
                                  bcrypt.gensalt())
                self.hashed_password = 'bcrypt:%s' % h.decode('utf-8')
        elif method == 'pbkdf2':
            ITERATIONS = 500000
            with tracer.start_as_current_span(
                'taguette/set_password',
                attributes={'method': method, 'iterations': ITERATIONS},
            ):
                salt = os.urandom(16)
                h = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                        salt, ITERATIONS)
                self.hashed_password = 'pbkdf2:%s$%d$%s' % (
                    binascii.hexlify(salt).decode('ascii'),
                    ITERATIONS,
                    binascii.hexlify(h).decode('ascii'),
                )
        else:
            raise ValueError("Unsupported encryption method %r" % method)
        self.password_set_date = datetime.utcnow()

    def check_password(self, password):
        if self.hashed_password is None:
            return False
        elif self.hashed_password.startswith('bcrypt:'):
            import bcrypt
            with tracer.start_as_current_span(
                'taguette/check_password',
                attributes={'method': 'bcrypt'},
            ):
                return bcrypt.checkpw(password.encode('utf-8'),
                                      self.hashed_password[7:].encode('utf-8'))
        elif self.hashed_password.startswith('pbkdf2:'):
            with tracer.start_as_current_span(
                'taguette/check_password',
                attributes={'method': 'pbkdf2'},
            ):
                pw = self.hashed_password[7:]
                salt, iterations, hash_pw = pw.split('$', 2)
                salt = binascii.unhexlify(salt.encode('ascii'))
                iterations = int(iterations, 10)
                hash_pw = binascii.unhexlify(hash_pw.encode('ascii'))
                return hmac.compare_digest(
                    hash_pw,
                    hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                        salt, iterations)
                )
        else:
            logger.warning("Password uses unknown encryption method")
            return False

    def __repr__(self):
        return '<%s.%s %r>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.login,
        )


class Project(Base):
    __tablename__ = 'projects'
    __table_args__ = ({'sqlite_autoincrement': True},)

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    created = Column(DateTime, nullable=False,
                     default=lambda: datetime.utcnow())
    members = relationship('User', secondary='project_members')
    commands = relationship('Command', cascade='all,delete-orphan',
                            passive_deletes=True)
    documents = relationship('Document', cascade='all,delete-orphan',
                             passive_deletes=True)
    tags = relationship('Tag', cascade='all,delete-orphan', order_by='Tag.id',
                        passive_deletes=True)

    def __repr__(self):
        return '<%s.%s %r %r>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.id,
            self.name,
        )


class Privileges(enum.Enum):
    ADMIN = 1
    MANAGE_DOCS = 3
    TAG = 2
    READ = 0

    # Admin operations
    def can_edit_project_meta(self):
        return self == Privileges.ADMIN

    def can_delete_project(self):
        return self == Privileges.ADMIN

    def can_edit_members(self):
        return self == Privileges.ADMIN

    # Document operations
    def can_edit_document(self):
        return self in (Privileges.ADMIN, Privileges.MANAGE_DOCS)
    can_delete_document = can_edit_document
    can_add_document = can_edit_document

    # Tagging operations
    def can_update_tag(self):
        return self in (Privileges.ADMIN, Privileges.MANAGE_DOCS,
                        Privileges.TAG)
    can_add_tag = can_update_tag
    can_delete_tag = can_update_tag
    can_merge_tags = can_update_tag

    def can_import_codebook(self):
        return self == Privileges.ADMIN

    def can_add_highlight(self):
        return self in (Privileges.ADMIN, Privileges.MANAGE_DOCS,
                        Privileges.TAG)
    can_delete_highlight = can_add_highlight


class ProjectMember(Base):
    __tablename__ = 'project_members'

    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        primary_key=True, index=True)
    project = relationship('Project')
    user_login = Column(String(30),
                        ForeignKey('users.login',
                                   ondelete='CASCADE', onupdate='CASCADE'),
                        primary_key=True, index=True)
    user = relationship('User')
    privileges = Column(Enum(Privileges), nullable=False)

    def __repr__(self):
        return '<%s.%s project_id=%r user_login=%r>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.project_id,
            self.user_login,
        )


class TextDirection(enum.Enum):
    LEFT_TO_RIGHT = 0
    RIGHT_TO_LEFT = 1


class Document(Base):
    __tablename__ = 'documents'
    __table_args__ = ({'sqlite_autoincrement': True},)

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    filename = Column(String(200), nullable=False)
    created = Column(DateTime, nullable=False,
                     default=lambda: datetime.utcnow())
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    project = relationship('Project', back_populates='documents')
    text_direction = Column(Enum(TextDirection), nullable=False)
    contents = deferred(Column(Text, nullable=False))
    highlights = relationship('Highlight', cascade='all,delete-orphan',
                              passive_deletes=True)

    def __repr__(self):
        return '<%s.%s %r %r project_id=%r>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.id,
            self.name,
            self.project_id,
        )


def command_fields(columns, payload_fields):
    def wrapper(func):
        func.columns = columns
        func.payload_fields = payload_fields
        return func
    return wrapper


class Command(Base):
    __tablename__ = 'commands'
    __table_args__ = ({'sqlite_autoincrement': True},)

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False,
                  default=lambda: datetime.utcnow(), index=True)
    user_login = Column(String(30),
                        ForeignKey('users.login', onupdate='CASCADE'),
                        nullable=False, index=True)
    user = relationship('User')
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    project = relationship('Project')
    document_id = Column(Integer,  # Not ForeignKey, document can go away
                         nullable=True, index=True)
    payload = Column(JSON, nullable=False)

    tag_count_changes = None

    __table_args__ = (
        Index('idx_project_document', 'project_id', 'document_id'),
        Index('idx_project_id', 'project_id', 'id'),
    ) + __table_args__

    def __init__(self, **kwargs):
        if 'payload' in kwargs:
            PROM_COMMAND.labels(kwargs['payload']['type']).inc()
        super(Command, self).__init__(**kwargs)

    def to_json(self):
        cmd_json = dict(self.payload)
        cmd_json['id'] = self.id
        cmd_json['user_login'] = self.user_login
        cmd_json['project_id'] = self.project_id
        if self.document_id is not None:
            cmd_json['document_id'] = self.document_id
        if self.tag_count_changes is not None:
            cmd_json['tag_count_changes'] = self.tag_count_changes
        return cmd_json

    TYPES = {'project_meta', 'document_add', 'document_delete',
             'highlight_add', 'highlight_delete', 'tag_add', 'tag_delete',
             'tag_merge', 'member_add', 'member_remove', 'project_import'}

    for n in TYPES:
        PROM_COMMAND.labels(n).inc(0)

    @classmethod
    @command_fields(
        columns=['project_id'],
        payload_fields=['project_name', 'description'],
    )
    def project_meta(cls, user_login, project_id, name, description):
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'project_meta',  # keep in sync above
                     'project_name': name,
                     'description': description},
        )

    @classmethod
    @command_fields(
        columns=['project_id', 'document_id'],
        payload_fields=['document_name', 'description', 'text_direction'],
    )
    def document_add(cls, user_login, document):
        assert isinstance(document.id, int)
        return cls(
            user_login=user_login,
            project=document.project,
            document_id=document.id,
            payload={'type': 'document_add',  # keep in sync above
                     'document_name': document.name,
                     'description': document.description,
                     'text_direction': document.text_direction.name},
        )

    @classmethod
    @command_fields(
        columns=['project_id', 'document_id'],
        payload_fields=[],
    )
    def document_delete(cls, user_login, document):
        assert isinstance(document, Document)
        assert isinstance(document.id, int)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document_id=document.id,
            payload={'type': 'document_delete'},  # keep in sync above
        )

    @classmethod
    @command_fields(
        columns=['project_id', 'document_id'],
        payload_fields=[
            'highlight_id', 'start_offset', 'end_offset', 'tags',
        ],
    )
    def highlight_add(cls, user_login, document, highlight, tags):
        assert isinstance(highlight.id, int)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document_id=document.id,
            payload={'type': 'highlight_add',  # keep in sync above
                     'highlight_id': highlight.id,
                     'start_offset': highlight.start_offset,
                     'end_offset': highlight.end_offset,
                     'tags': tags},
        )

    @classmethod
    @command_fields(
        columns=['project_id', 'document_id'],
        payload_fields=['highlight_id'],
    )
    def highlight_delete(cls, user_login, document, highlight_id):
        assert isinstance(highlight_id, int)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document_id=document.id,
            payload={'type': 'highlight_delete',  # keep in sync above
                     'highlight_id': highlight_id},
        )

    @classmethod
    @command_fields(
        columns=['project_id'],
        payload_fields=['tag_id', 'tag_path', 'description'],
    )
    def tag_add(cls, user_login, tag):
        assert isinstance(tag, Tag)
        assert isinstance(tag.id, int)
        return cls(
            user_login=user_login,
            project_id=tag.project_id,
            payload={'type': 'tag_add',  # keep in sync above
                     'tag_id': tag.id,
                     'tag_path': tag.path,
                     'description': tag.description},
        )

    @classmethod
    @command_fields(
        columns=['project_id'],
        payload_fields=['tag_id'],
    )
    def tag_delete(cls, user_login, project_id, tag_id):
        assert isinstance(project_id, int)
        assert isinstance(tag_id, int)
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'tag_delete',  # keep in sync above
                     'tag_id': tag_id},
        )

    @classmethod
    @command_fields(
        columns=['project_id'],
        payload_fields=['src_tag_id', 'dest_tag_id'],
    )
    def tag_merge(cls, user_login, project_id, tag_src, tag_dest):
        assert isinstance(project_id, int)
        assert isinstance(tag_src, int)
        assert isinstance(tag_dest, int)
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'tag_merge',  # keep in sync above
                     'src_tag_id': tag_src,
                     'dest_tag_id': tag_dest},
        )

    @classmethod
    @command_fields(
        columns=['project_id'],
        payload_fields=['member', 'privileges'],
    )
    def member_add(cls, user_login, project_id, member_login, privileges):
        assert isinstance(project_id, int)
        assert isinstance(privileges, Privileges)
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'member_add',  # keep in sync above
                     'member': member_login,
                     'privileges': privileges.name}
        )

    @classmethod
    @command_fields(
        columns=['project_id'],
        payload_fields=['member'],
    )
    def member_remove(cls, user_login, project_id, member_login):
        assert isinstance(project_id, int)
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'member_remove',  # keep in sync above
                     'member': member_login}
        )

    @classmethod
    @command_fields(
        columns=['project_id'],
        payload_fields=[],
    )
    def project_import(cls, user_login, project_id):
        assert isinstance(project_id, int)
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'project_import'}  # keep in sync above
        )

    def __repr__(self):
        return (
            '<%s.%s %r %r user_login=%r project_id=%r document_id=%r type=%r>'
        ) % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.id,
            self.date,
            self.user_login,
            self.project_id,
            self.document_id,
            self.payload.get('type'),
        )


Project.last_event = column_property(
    select(
        [Command.id]
    ).where(
        Command.project_id == Project.id
    ).order_by(
        Command.id.desc()
    ).limit(1)
    .as_scalar()
)


class Highlight(Base):
    __tablename__ = 'highlights'
    __table_args__ = ({'sqlite_autoincrement': True},)

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id',
                                             ondelete='CASCADE'),
                         nullable=False, index=True)
    document = relationship('Document', back_populates='highlights')
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    snippet = Column(Text, nullable=False)
    tags = relationship('Tag', secondary='highlight_tags')

    def __repr__(self):
        return '<%s.%s %r document_id=%r tags=[%s]>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.id,
            self.document_id,
            ' '.join(sorted(str(t.id) for t in self.tags)),
        )


class Tag(Base):
    __tablename__ = 'tags'
    __table_args__ = ({'sqlite_autoincrement': True},)

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    project = relationship('Project')

    path = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('project_id', 'path'),
    ) + __table_args__

    highlights = relationship('Highlight', secondary='highlight_tags')

    def __repr__(self):
        return '<%s.%s %r %r project_id=%r>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.id,
            self.path,
            self.project_id,
        )


class HighlightTag(Base):
    __tablename__ = 'highlight_tags'

    highlight_id = Column(Integer, ForeignKey('highlights.id',
                                              ondelete='CASCADE'),
                          primary_key=True, index=True)
    highlight = relationship('Highlight')
    tag_id = Column(Integer, ForeignKey('tags.id',
                                        ondelete='CASCADE'),
                    primary_key=True, index=True)
    tag = relationship('Tag')

    def __repr__(self):
        return '<%s.%s highlight_id=%r tag_id=%r>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.highlight_id,
            self.tag_id,
        )


Tag.highlights_count = column_property(
    select(
        [functions.count(HighlightTag.highlight_id)],
    )
    .where(
        HighlightTag.tag_id == Tag.id,
    )
    .correlate_except(HighlightTag)
    .scalar_subquery()
)
