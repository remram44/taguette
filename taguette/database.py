import bcrypt
import enum
import json
import logging
from sqlalchemy import Column, ForeignKey, Index, TypeDecorator, \
    create_engine, select
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import column_property, deferred, relationship, \
    sessionmaker
from sqlalchemy.sql import functions
from sqlalchemy.types import DateTime, Enum, Integer, String, Text


logger = logging.getLogger(__name__)


Base = declarative_base()


class JSON(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = String

    def process_bind_param(self, value, dialect):
        return json.dumps(value, sort_keys=True)

    def process_result_value(self, value, dialect):
        return json.loads(value)


class User(Base):
    __tablename__ = 'users'

    login = Column(String, primary_key=True)
    created = Column(DateTime, nullable=False,
                     server_default=functions.now())
    hashed_password = Column(String, nullable=True)
    projects = relationship('Project', secondary='project_members')

    def set_password(self, password, method='bcrypt'):
        if method == 'bcrypt':
            h = bcrypt.hashpw(password.encode('utf-8'),
                              bcrypt.gensalt())
            self.hashed_password = 'bcrypt:%s' % h.decode('utf-8')
        else:
            raise ValueError("Unsupported encryption method %r" % method)

    def check_password(self, password):
        if self.hashed_password is None:
            return False
        elif self.hashed_password.startswith('bcrypt:'):
            return bcrypt.checkpw(password.encode('utf-8'),
                                  self.hashed_password[7:].encode('utf-8'))
        else:
            logger.warning("Password uses unknown encryption method")
            return False


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created = Column(DateTime, nullable=False,
                     server_default=functions.now())
    members = relationship('User', secondary='project_members')
    documents = relationship('Document')
    tags = relationship('Tag')
    groups = relationship('Group')


class Privileges(enum.Enum):
    ADMIN = 1
    MANAGE_DOCS = 3
    TAG = 2
    READ = 0


class ProjectMember(Base):
    __tablename__ = 'project_members'

    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        primary_key=True, index=True)
    project = relationship('Project')
    user_login = Column(Integer, ForeignKey('users.login', ondelete='CASCADE'),
                        primary_key=True, index=True)
    user = relationship('User')
    privileges = Column(Enum(Privileges), nullable=False)


class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    filename = Column(String, nullable=True)
    created = Column(DateTime, nullable=False,
                     server_default=functions.now())
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    project = relationship('Project', back_populates='documents')
    contents = deferred(Column(Text, nullable=False))
    group = relationship('Group', secondary='document_groups')
    highlights = relationship('Highlight')


class Command(Base):
    __tablename__ = 'commands'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False,
                  server_default=functions.now(), index=True)
    user_login = Column(String, ForeignKey('users.login'), nullable=False)
    user = relationship('User')
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False,
                        index=True)
    project = relationship('Project')
    document_id = Column(Integer, ForeignKey('documents.id'),
                         nullable=True)
    document = relationship('Document')
    payload = Column(JSON, nullable=False)

    __table_args__ = (
        Index('idx_project_document', 'project_id', 'document_id'),
    )

    @classmethod
    def project_meta(cls, user_login, project_id, name, description):
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'project_meta',
                     'name': name,
                     'description': description},
        )

    @classmethod
    def document_add(cls, user_login, document):
        return cls(
            user_login=user_login,
            project=document.project,
            document=document,
            payload={'type': 'document_add',
                     'name': document.name,
                     'description': document.description},
        )

    @classmethod
    def highlight_add(cls, user_login, document, highlight, tags):
        assert isinstance(highlight.id, int)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document=document,
            payload={'type': 'highlight_add',
                     'id': highlight.id,
                     'start_offset': highlight.start_offset,
                     'end_offset': highlight.end_offset,
                     'tags': tags},
        )

    @classmethod
    def highlight_delete(cls, user_login, document, highlight_id):
        assert isinstance(highlight_id, int)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document=document,
            payload={'type': 'highlight_delete',
                     'id': highlight_id},
        )

    @classmethod
    def tag_add(cls, user_login, tag):
        assert isinstance(tag, Tag)
        return cls(
            user_login=user_login,
            project_id=tag.project_id,
            payload={'type': 'tag_add',
                     'id': tag.id,
                     'path': tag.path,
                     'description': tag.description},
        )

    @classmethod
    def tag_delete(cls, user_login, project_id, tag_id):
        assert isinstance(project_id, int)
        assert isinstance(tag_id, int)
        return cls(
            user_login=user_login,
            project_id=project_id,
            payload={'type': 'tag_delete',
                     'id': tag_id},
        )


Project.last_event = column_property(
    select(
        [Command.date]
    ).where(
        Command.project_id == 1
    ).order_by(
        Command.id.desc()
    ).as_scalar()
)


class Highlight(Base):
    __tablename__ = 'highlights'

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id',
                                             ondelete='CASCADE'),
                         nullable=False, index=True)
    document = relationship('Document', back_populates='highlights')
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    snippet = Column(Text, nullable=False)
    tags = relationship('Tag', secondary='highlight_tags')


class BaseHierarchy(object):
    id = Column(Integer, primary_key=True)

    @declared_attr
    def project_id(cls):
        return Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                      nullable=False, index=True)

    @declared_attr
    def project(cls):
        return relationship('Project')

    path = Column(String, nullable=False)
    description = Column(Text, nullable=False)


class Group(Base, BaseHierarchy):
    __tablename__ = 'groups'

    documents = relationship('Document', secondary='document_groups')


class DocumentGroup(Base):
    __tablename__ = 'document_groups'

    document_id = Column(Integer, ForeignKey('documents.id',
                                             ondelete='CASCADE'),
                         primary_key=True)
    group_id = Column(Integer, ForeignKey('groups.id', ondelete='CASCADE'),
                      primary_key=True)


class Tag(Base, BaseHierarchy):
    __tablename__ = 'tags'

    documents = relationship('Highlight', secondary='highlight_tags')


class HighlightTag(Base):
    __tablename__ = 'highlight_tags'

    highlight_id = Column(Integer, ForeignKey('highlights.id',
                                              ondelete='CASCADE'),
                          primary_key=True)
    highlight = relationship('Highlight')
    tag_id = Column(Integer, ForeignKey('tags.id',
                                        ondelete='CASCADE'),
                    primary_key=True)
    tag = relationship('Tag')


def connect(db_url):
    """Connect to the database using an environment variable.
    """
    logger.info("Connecting to SQL database %r", db_url)
    engine = create_engine(db_url, echo=False)

    if not engine.dialect.has_table(engine.connect(), Project.__tablename__):
        logger.warning("The tables don't seem to exist; creating")
        Base.metadata.create_all(bind=engine)

    DBSession = sessionmaker(bind=engine)

    return DBSession
