import alembic.command
import alembic.config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
import bcrypt
import enum
import json
import logging
import os
import shutil
from sqlalchemy import Column, ForeignKey, Index, TypeDecorator, MetaData, \
    UniqueConstraint, create_engine, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import column_property, deferred, relationship, \
    sessionmaker
from sqlalchemy.sql import functions
from sqlalchemy.types import DateTime, Enum, Integer, String, Text
import sys


logger = logging.getLogger(__name__)


meta = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})
Base = declarative_base(metadata=meta)


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
    commands = relationship('Command', cascade='all,delete')
    documents = relationship('Document', cascade='all,delete')
    tags = relationship('Tag', cascade='all,delete')
    groups = relationship('Group', cascade='all,delete')


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
    highlights = relationship('Highlight', cascade='all,delete')


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
    document_id = Column(Integer,
                         nullable=True)  # Not ForeignKey, document can go away
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
            document_id=document.id,
            payload={'type': 'document_add',
                     'name': document.name,
                     'description': document.description},
        )

    @classmethod
    def document_delete(cls, user_login, document):
        assert isinstance(document, Document)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document_id=document.id,
            payload={'type': 'document_delete'},
        )

    @classmethod
    def highlight_add(cls, user_login, document, highlight, tags):
        assert isinstance(highlight.id, int)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document_id=document.id,
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
            document_id=document.id,
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
        [Command.id]
    ).where(
        Command.project_id == Project.id
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


class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    project = relationship('Project')

    path = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('project_id', 'path'),
    )

    documents = relationship('Document', secondary='document_groups')


class DocumentGroup(Base):
    __tablename__ = 'document_groups'

    document_id = Column(Integer, ForeignKey('documents.id',
                                             ondelete='CASCADE'),
                         primary_key=True)
    group_id = Column(Integer, ForeignKey('groups.id', ondelete='CASCADE'),
                      primary_key=True)


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    project = relationship('Project')

    path = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('project_id', 'path'),
    )

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

    alembic_cfg = alembic.config.Config()
    alembic_cfg.set_main_option('script_location', 'taguette:migrations')
    alembic_cfg.set_main_option('sqlalchemy.url', db_url)

    conn = engine.connect()
    if not engine.dialect.has_table(conn, Project.__tablename__):
        logger.warning("The tables don't seem to exist; creating")
        Base.metadata.create_all(bind=engine)

        # Mark this as the most recent Alembic version
        alembic.command.stamp(alembic_cfg, "head")
    else:
        # Perform Alembic migrations if needed
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        scripts = ScriptDirectory.from_config(alembic_cfg)
        if [current_rev] != scripts.get_heads():
            if db_url.startswith('sqlite:'):
                logger.warning("The database schema used by Taguette has "
                               "changed! We will try to update your workspace "
                               "automatically.")
                assert db_url.startswith('sqlite:///')
                assert os.path.exists(db_url[10:])
                backup = db_url[10:] + '.bak'
                shutil.copy2(db_url[10:], backup)
                logger.warning("A backup copy of your database file has been "
                               "created. If the update goes horribly wrong, "
                               "make sure to keep that file, and let us know: "
                               "%s", backup)
                alembic.command.upgrade(alembic_cfg, 'head')
            else:
                logger.critical("The database schema used by Taguette has "
                                "changed! Because you are not using SQLite, "
                                "we will not attempt a migration "
                                "automatically; back up your data and use "
                                "`taguette --database=%s migrate` if you want "
                                "to proceed.",
                                db_url)
                sys.exit(3)
        else:
            logger.info("Database is up to date: %s", current_rev)

    DBSession = sessionmaker(bind=engine)

    return DBSession


def migrate(db_url, revision):
    alembic_cfg = alembic.config.Config()
    alembic_cfg.set_main_option('script_location', 'taguette:migrations')
    alembic_cfg.set_main_option('sqlalchemy.url', db_url)

    logger.warning("Performing database upgrade")
    alembic.command.upgrade(alembic_cfg, revision)
