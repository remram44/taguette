"""remove commands.document_id fk

Revision ID: e4e090a5b511
Revises:
Create Date: 2018-10-29 09:50:21.331882

"""
from alembic import op
from sqlalchemy import Column, ForeignKey, Index, column, select, table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import functions
from sqlalchemy.types import DateTime, Integer, String, Text


# revision identifiers, used by Alembic.
revision = 'e4e090a5b511'
down_revision = None
branch_labels = None
depends_on = None


Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    login = Column(String, primary_key=True)
    created = Column(DateTime, nullable=False,
                     server_default=functions.now())
    hashed_password = Column(String, nullable=True)
    projects = relationship('Project', secondary='project_members')


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created = Column(DateTime, nullable=False,
                     server_default=functions.now())


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
    payload = Column(String, nullable=False)

    __table_args__ = (
        Index('idx_project_document', 'project_id', 'document_id'),
    )


def upgrade():
    bind = op.get_bind()

    # Drop old indexes
    op.drop_index('idx_project_document')
    op.drop_index('ix_commands_date')
    op.drop_index('ix_commands_project_id')

    # Rename old table
    op.rename_table('commands', 'commands_old')

    # Create new table
    Command.__table__.create(bind)

    # Copy data over
    session = Session(bind=bind)
    session.execute(Command.__table__.insert().from_select(
        ['id', 'date', 'user_login', 'project_id', 'document_id', 'payload'],
        select([
            column('id'), column('date'), column('user_login'),
            column('project_id'), column('document_id'), column('payload'),
        ]).select_from(table('commands_old')),
    ))
    session.commit()

    # Drop old table
    op.drop_table('commands_old')


def downgrade():
    with op.batch_alter_table('commands', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_commands_document_id',
                                    'documents', ['document_id'], ['id'])
