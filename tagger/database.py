import bcrypt
import enum
import logging
import os
from sqlalchemy import Column, ForeignKey, Index, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import deferred, relationship, sessionmaker
from sqlalchemy.sql import functions
from sqlalchemy.types import DateTime, Enum, Integer, String, Text


logger = logging.getLogger(__name__)


Base = declarative_base()


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
    meta_updated = Column(DateTime, nullable=False,
                          server_default=functions.now())
    documents_updated = Column(DateTime, nullable=False,
                               server_default=functions.now())
    documents = relationship('Document')
    members = relationship('User', secondary='project_members')

    @property
    def last_event(self):
        return max(self.meta_updated, self.documents_updated)


class Privileges(enum.Enum):
    READ = 0
    ADMIN = 1
    TAG = 2
    MANAGE_DOCS = 3


class ProjectMember(Base):
    __tablename__ = 'project_members'

    project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True,
                        index=True)
    project = relationship('Project')
    user_login = Column(Integer, ForeignKey('users.login'), primary_key=True,
                        index=True)
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
    project_id = Column(Integer, ForeignKey('projects.id'), index=True)
    project = relationship('Project', back_populates='documents')
    contents = deferred(Column(Text, nullable=False))
    doctags = relationship('DocTag', secondary='document_doctags')
    highlights = relationship('Highlight')


class Highlight(Base):
    __tablename__ = 'highlights'

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), index=True)
    document = relationship('Document', back_populates='highlights')
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    doctags = relationship('HlTag', secondary='highlight_hltags')


class Tag(object):
    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=False)
    description = Column(Text, nullable=False)


class DocTag(Base, Tag):
    __tablename__ = 'doctags'

    documents = relationship('Document', secondary='document_doctags')


class DocumentDocTag(Base):
    __tablename__ = 'document_doctags'

    document_id = Column(Integer, ForeignKey('documents.id'),
                         primary_key=True)
    doctag_id = Column(Integer, ForeignKey('doctags.id'),
                       primary_key=True)


class HlTag(Base, Tag):
    __tablename__ = 'hltags'

    documents = relationship('Highlight', secondary='highlight_hltags')


class HighlightHlTag(Base):
    __tablename__ = 'highlight_hltags'

    highlight_id = Column(Integer, ForeignKey('highlights.id'),
                          primary_key=True)
    hltag_id = Column(Integer, ForeignKey('hltags.id'),
                      primary_key=True)


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
