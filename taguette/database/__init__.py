import alembic.command
import alembic.config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
import contextlib
import logging
import opentelemetry.trace
import os
import shutil
from sqlalchemy import engine_from_config
import sqlalchemy.engine
import sqlalchemy.event
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import sessionmaker
import sys

import taguette
from .base import PROM_DATABASE_VERSION
from .copy import copy_project  # noqa: F401
from .models import Base, JSON, User, Project, Privileges, ProjectMember, \
    TextDirection, Document, Command, Highlight, Tag, \
    HighlightTag  # noqa: F401


logger = logging.getLogger(__name__)
tracer = opentelemetry.trace.get_tracer(__name__)


class UnknownVersion(ValueError):
    """Unknown database version"""


def set_sqlite_pragma(dbapi_connection, connection_record):
    if set_sqlite_pragma.enabled:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


set_sqlite_pragma.enabled = True


@contextlib.contextmanager
def no_sqlite_pragma_check():
    taguette.database.set_sqlite_pragma.enabled = False
    try:
        yield
    finally:
        taguette.database.set_sqlite_pragma.enabled = True


def connect(db_url, *, external=False, create_tables=None):
    """Connect to the database using an environment variable.
    """
    if create_tables is None:
        create_tables = not external

    if isinstance(db_url, dict):
        db_dict = db_url
        db_url = db_dict['url']
    else:
        db_dict = {'url': db_url}

    logger.info("Connecting to SQL database %r", db_url)
    if db_url.startswith('sqlite:'):
        db_dict['connect_args'] = {'check_same_thread': False}
    engine = engine_from_config(db_dict, prefix='')
    # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    if db_url.startswith('sqlite:'):
        sqlalchemy.event.listen(
            engine,
            "connect",
            set_sqlite_pragma,
        )

        # https://www.sqlite.org/security.html#untrusted_sqlite_database_files
        if external:
            logger.info("Database is not trusted")

            @sqlalchemy.event.listens_for(engine, "connect")
            def secure(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA trusted_schema=OFF")
                cursor.execute('PRAGMA cell_size_check=ON')
                cursor.execute('PRAGMA mmap_size=0')
                cursor.close()

            conn = engine.connect()
            conn.exec_driver_sql('PRAGMA quick_check')
            conn.close()

    alembic_cfg = alembic.config.Config()
    alembic_cfg.set_main_option('script_location', 'taguette:migrations')
    alembic_cfg.set_main_option('sqlalchemy.url', db_url)

    with engine.connect() as conn:
        if engine.dialect.has_table(conn, Project.__tablename__):
            # Check that alembic version is there
            if not engine.dialect.has_table(conn, 'alembic_version'):
                raise NoSuchTableError('alembic_version')

            # Perform Alembic migrations if needed
            _auto_upgrade_db(db_url, conn, alembic_cfg, external)

            # Check that all tables are here
            for table in Base.metadata.sorted_tables:
                if not engine.dialect.has_table(conn, table.name):
                    raise NoSuchTableError(table.name)
        elif create_tables:
            logger.warning("The tables don't seem to exist; creating")
            Base.metadata.create_all(bind=engine)

            # Mark this as the most recent Alembic version
            alembic.command.stamp(alembic_cfg, "head")

            # Set SQLite's "application ID"
            if db_url.startswith('sqlite:'):
                conn.exec_driver_sql(
                    "PRAGMA application_id=0x54677474;"  # 'Tgtt'
                )
        else:
            raise NoSuchTableError('projects')

    # Record to Prometheus
    conn = engine.connect()
    revision = MigrationContext.configure(conn).get_current_revision()
    PROM_DATABASE_VERSION.labels(revision).set(1)

    DBSession = sessionmaker(bind=engine)

    return DBSession


def _auto_upgrade_db(db_url, conn, alembic_cfg, external):
    context = MigrationContext.configure(conn)
    current_rev = context.get_current_revision()
    scripts = ScriptDirectory.from_config(alembic_cfg)
    if [current_rev] != scripts.get_heads():
        logger.warning("Database schema is out of date: %s", current_rev)
        _ = taguette.trans.gettext
        if db_url.startswith('sqlite:'):
            if not external:
                print(_(
                    "\n    The database schema used by Taguette has "
                    "changed! We will try to\n    update your workspace "
                    "automatically.\n"), file=sys.stderr, flush=True)
                assert db_url.startswith('sqlite:///')
                assert os.path.exists(db_url[10:])
                backup = db_url[10:] + '.bak'
                shutil.copy2(db_url[10:], backup)
                logger.warning(
                    "Performing automated update, backup file: %s", backup,
                )
                print(
                    _("\n    A backup copy of your database file has been "
                      "created. If the update\n    goes horribly wrong, "
                      "make sure to keep that file, and let us know:\n    "
                      "%(backup)s\n") % dict(backup=backup),
                    file=sys.stderr, flush=True,
                )
            try:
                scripts.get_revision(current_rev)
            except alembic.util.exc.CommandError as e:
                raise UnknownVersion from e
            alembic.command.upgrade(alembic_cfg, 'head')
        else:
            print(_("\n    The database schema used by Taguette has "
                    "changed! Because you are not using\n    SQLite, we "
                    "will not attempt a migration automatically; back up "
                    "your data and\n    use `taguette --database=%(url)s "
                    "migrate` if you want to proceed.") % dict(url=db_url),
                  file=sys.stderr, flush=True)
            sys.exit(3)
    else:
        logger.info("Database is up to date: %s", current_rev)


def migrate(db_url, revision):
    alembic_cfg = alembic.config.Config()
    alembic_cfg.set_main_option('script_location', 'taguette:migrations')
    alembic_cfg.set_main_option('sqlalchemy.url', db_url)

    logger.warning("Performing database upgrade")
    alembic.command.upgrade(alembic_cfg, revision)
