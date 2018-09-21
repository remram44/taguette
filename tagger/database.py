import bcrypt
import enum
import json
import logging
import os
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
                                  self.password.encode('utf-8'))
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
    hltags = relationship('HlTag')


class Privileges(enum.Enum):
    READ = 0
    ADMIN = 1
    TAG = 2
    MANAGE_DOCS = 3


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
    doctags = relationship('DocTag', secondary='document_doctags')
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
    def highlight_add(cls, user_login, document, highlight, hltags):
        assert isinstance(highlight.id, int)
        return cls(
            user_login=user_login,
            project_id=document.project_id,
            document=document,
            payload={'type': 'highlight_add',
                     'id': highlight.id,
                     'start_offset': highlight.start_offset,
                     'end_offset': highlight.end_offset,
                     'hltags': hltags},
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
    hltags = relationship('HlTag', secondary='highlight_hltags')


class Tag(object):
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


class DocTag(Base, Tag):
    __tablename__ = 'doctags'

    documents = relationship('Document', secondary='document_doctags')


class DocumentDocTag(Base):
    __tablename__ = 'document_doctags'

    document_id = Column(Integer, ForeignKey('documents.id',
                                             ondelete='CASCADE'),
                         primary_key=True)
    doctag_id = Column(Integer, ForeignKey('doctags.id', ondelete='CASCADE'),
                       primary_key=True)


class HlTag(Base, Tag):
    __tablename__ = 'hltags'

    documents = relationship('Highlight', secondary='highlight_hltags')


class HighlightHlTag(Base):
    __tablename__ = 'highlight_hltags'

    highlight_id = Column(Integer, ForeignKey('highlights.id',
                                              ondelete='CASCADE'),
                          primary_key=True)
    highlight = relationship('Highlight')
    hltag_id = Column(Integer, ForeignKey('hltags.id',
                                          ondelete='CASCADE'),
                      primary_key=True)
    hltag = relationship('HlTag')


def connect():
    """Connect to the database using an environment variable.
    """
    logger.info("Connecting to SQL database")
    if 'POSTGRES_HOST' in os.environ:
        url = 'postgresql://{user}:{password}@{host}/{database}'.format(
            user=os.environ['POSTGRES_USER'],
            password=os.environ['POSTGRES_PASSWORD'],
            host=os.environ['POSTGRES_HOST'],
            database=os.environ['POSTGRES_DB'],
        )
    else:
        if 'SQLITE_DB' in os.environ:
            fname = os.path.abspath(os.environ['SQLITE_DB'])
        else:
            fname = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'db.sqlite3')
        url = 'sqlite:///%s' % fname

    engine = create_engine(url, echo=False)

    if not engine.dialect.has_table(engine.connect(), Project.__tablename__):
        logger.warning("The tables don't seem to exist; creating")
        Base.metadata.create_all(bind=engine)

    DBSession = sessionmaker(bind=engine)

    db = DBSession()
    if db.query(User).count() == 0:
        logger.warning("Creating user 'admin'")
        user = User(login='admin')
        #import getpass
        #passwd = getpass.getpass("Enter password for admin user: ")
        #user.set_password(passwd)
        db.add(user)
        db.commit()

    return DBSession
