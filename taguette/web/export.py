from datetime import datetime
import logging
import os
import prometheus_client
import shutil
import string
import tempfile
from tornado.web import authenticated

from .. import convert
from .. import database
from .. import export
from .base import BaseHandler

logger = logging.getLogger(__name__)


class WriteAdapter(object):
    def __init__(self, write_func):
        self.write = write_func

    def flush(self):
        pass


PROM_EXPORT = prometheus_client.Counter(
    'export_total',
    "Export",
    ['what', 'extension'],
)


def init_PROM_EXPORT(w):
    for e in convert.html_to_extensions:
        PROM_EXPORT.labels(w, e).inc(0)


def return_doc(wrapped):
    """Decorator for returning a file, or a conversion error.
    """
    async def wrapper(self, *args):
        ext = args[-1].lower()
        try:
            name, mimetype, contents = await wrapped(self, *args)
        except convert.UnsupportedFormat:
            self.set_status(404)
            self.set_header('Content-Type', 'text/plain')
            return await self.finish("Unsupported format: %s" % ext)
        except convert.ConversionError as e:
            self.set_status(500)
            self.set_header('Content-Type', 'text/plain')
            return await self.finish("Conversion error: %s" % e)

        # Return document
        self.set_header('Content-Type', mimetype)
        if name:
            self.set_header('Content-Disposition',
                            'attachment; filename="%s.%s"' % (name, ext))
        else:
            self.set_header('Content-Disposition', 'attachment')

        for chunk in contents:
            self.write(chunk)
        return await self.finish()

    return wrapper


class ExportHighlightsCsv(BaseHandler):
    PROM_EXPORT.labels('highlights_doc', 'csv').inc(0)

    @authenticated
    def get(self, project_id, path):
        PROM_EXPORT.labels('highlights_doc', 'csv').inc()

        project, _ = self.get_project(project_id)

        name = export.get_filename_for_highlights_export(path)
        self.set_header('Content-Type', 'text/csv; charset=utf-8')
        if name:
            self.set_header('Content-Disposition',
                            'attachment; filename="%s.csv"' % name)
        else:
            self.set_header('Content-Disposition', 'attachment')

        export.highlights_csv(
            self.db,
            project.id,
            path,
            WriteAdapter(self.write),
        )
        return self.finish()


class ExportHighlightsXlsx(BaseHandler):
    PROM_EXPORT.labels('highlights_doc', 'xls').inc(0)

    @authenticated
    def get(self, project_id, path):
        PROM_EXPORT.labels('highlights_doc', 'xls').inc()

        project, _ = self.get_project(project_id)

        name = export.get_filename_for_highlights_export(path)
        self.set_header('Content-Type',
                        ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'))
        if name:
            self.set_header('Content-Disposition',
                            'attachment; filename="%s.xlsx"' % name)
        else:
            self.set_header('Content-Disposition', 'attachment')

        tmp = tempfile.mkdtemp(prefix='taguette_xlsx_')
        try:
            filename = os.path.join(tmp, 'highlights.xlsx')
            export.highlights_xslx(self.db, project.id, path, filename)
            with open(filename, 'rb') as fp:
                chunk = fp.read(4096)
                self.write(chunk)
                while len(chunk) == 4096:
                    chunk = fp.read(4096)
                    if chunk:
                        self.write(chunk)
            return self.finish()
        finally:
            shutil.rmtree(tmp)


class ExportHighlightsDoc(BaseHandler):
    init_PROM_EXPORT('highlights_doc')

    @authenticated
    @return_doc
    async def get(self, project_id, path, ext):
        ext = ext.lower()
        PROM_EXPORT.labels('highlights_doc', ext).inc()

        project, _ = self.get_project(project_id)

        name = export.get_filename_for_highlights_export(path)
        mimetype, contents = export.highlights_doc(
            self.db,
            project.id,
            path,
            ext,
            config=self.application.config,
            locale=self.locale,
        )
        contents = await contents
        return name, mimetype, contents


_safe_filename_chars = set(
    string.ascii_letters
    + string.digits
    + ' ()+,-.=@[]_{}~'
)


def safe_filename(name):
    return ''.join(c for c in name if c in _safe_filename_chars)


class ExportDocument(BaseHandler):
    init_PROM_EXPORT('document')

    @authenticated
    @return_doc
    async def get(self, project_id, document_id, ext):
        PROM_EXPORT.labels('document', ext.lower()).inc()
        doc, _ = self.get_document(project_id, document_id, True)

        name = safe_filename(doc.name)

        mimetype, contents = await export.highlighted_document(
            self.db,
            doc,
            ext,
            config=self.application.config,
            locale=self.locale,
        )
        return name, mimetype, contents


class ExportCodebookXml(BaseHandler):
    PROM_EXPORT.labels('codebook', 'qdc').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'qdc').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type', 'text/xml; charset=utf-8')
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.qdc"')

        export.codebook_xml(tags, WriteAdapter(self.write))
        return self.finish()


class ExportCodebookCsv(BaseHandler):
    PROM_EXPORT.labels('codebook', 'csv').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'csv').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type', 'text/csv; charset=utf-8')
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.csv"')
        export.codebook_csv(tags, WriteAdapter(self.write))
        return self.finish()


class ExportCodebookXlsx(BaseHandler):
    PROM_EXPORT.labels('codebook', 'xls').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'xls').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type',
                        ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'))
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.xlsx"')
        tmp = tempfile.mkdtemp(prefix='taguette_xlsx_')
        try:
            filename = os.path.join(tmp, 'codebook.xlsx')

            export.codebook_xlsx(tags, filename)

            with open(filename, 'rb') as fp:
                chunk = fp.read(4096)
                self.write(chunk)
                while len(chunk) == 4096:
                    chunk = fp.read(4096)
                    if chunk:
                        self.write(chunk)
            return self.finish()
        finally:
            shutil.rmtree(tmp)


class ExportCodebookDoc(BaseHandler):
    init_PROM_EXPORT('codebook')

    @authenticated
    @return_doc
    async def get(self, project_id, ext):
        ext = ext.lower()
        PROM_EXPORT.labels('codebook', ext).inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)

        mimetype, contents = await export.codebook_document(
            tags,
            ext,
            config=self.application.config,
            locale=self.locale,
        )
        return 'codebook', mimetype, contents


class ExportSqlite(BaseHandler):
    PROM_EXPORT.labels('project', 'sqlite3').inc(0)

    @authenticated
    async def get(self, project_id):
        PROM_EXPORT.labels('project', 'sqlite3').inc()
        project, _ = self.get_project(project_id)

        # Result filename
        export_name = '%s_%s.sqlite3' % (
            datetime.utcnow().strftime('%Y-%m-%d'),
            safe_filename(project.name),
        )

        with tempfile.TemporaryDirectory(
            prefix='taguette_export_',
        ) as tmp_dir:
            filename = os.path.join(tmp_dir, 'db.sqlite3')

            # Connect to database
            dest_db = database.connect('sqlite:///%s' % filename)()

            # Create user
            admin = database.User(login='admin')
            dest_db.add(admin)
            dest_db.commit()

            # Copy data
            database.copy_project(
                self.db, dest_db,
                project.id, 'admin',
            )
            dest_db.commit()

            # Send the file
            self.set_header('Content-Type', 'application/vnd.sqlite3')
            self.set_header('Content-Disposition',
                            'attachment; filename="%s"' % export_name)
            with open(filename, 'rb') as fp:
                while True:
                    chunk = fp.read(4096)
                    self.write(chunk)
                    if len(chunk) != 4096:
                        break
                    await self.flush()
                return await self.finish()
