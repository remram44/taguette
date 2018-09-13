import logging
import os
from sqlalchemy import Column, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import functions
from sqlalchemy.types import DateTime, Integer, String, Text


logger = logging.getLogger(__name__)


Base = declarative_base()


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created = Column(DateTime, nullable=False,
                     server_default=functions.now())


class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created = Column(DateTime, nullable=False,
                     server_default=functions.now())
    project_id = Column(Integer, ForeignKey('projects.id'),
                        ondelete='CASCADE')
    project = relationship('Project', back_populates='documents')
    contents = Column(Text, nullable=False)


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
            fname = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
        url = 'sqlite3://%s' % fname

    engine = create_engine(url, echo=False)

    if not engine.dialect.has_table(engine.connect(), Project.__tablename__):
        logger.warning("The tables don't seem to exist; creating")
        Base.metadata.create_all(bind=engine)

    return engine, sessionmaker(bind=engine)
